"""Model providers: Anthropic (agent + defender), OpenAI (red-team), and a deterministic mock."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .config import CONFIG


@dataclass
class AssistantTurn:
    content: list[Any]            # raw content blocks to append back to the conversation
    text: str
    tool_uses: list[dict] = field(default_factory=list)   # {id, name, input}
    stop_reason: str = "end_turn"
    model: str = ""


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str):
        import anthropic

        self.model = model
        self.client = anthropic.AsyncAnthropic()
        self.live = True
        self._is_fable = model.startswith("claude-fable") or model.startswith("claude-mythos")

    def _effort(self, effort: str | None) -> dict:
        return {"effort": effort} if effort else {}

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict], effort: str = "medium") -> AssistantTurn:
        resp = await self.client.messages.create(
            model=self.model, max_tokens=4096, system=system, messages=messages, tools=tools,
            output_config=self._effort(effort),
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        uses = [{"id": b.id, "name": b.name, "input": b.input} for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason == "refusal":
            text = text or "I'm not able to help with that request."
            uses = []
        return AssistantTurn(content=resp.content, text=text, tool_uses=uses, stop_reason=resp.stop_reason, model=resp.model)

    async def json(self, system: str, prompt: str, schema: dict, effort: str = "high", **_: Any) -> dict:
        kwargs = dict(model=self.model, max_tokens=16000, system=system,
                      messages=[{"role": "user", "content": prompt}],
                      output_config={"format": {"type": "json_schema", "schema": schema}, **self._effort(effort)})
        resp = None
        if self._is_fable:
            try:
                resp = await self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
            except TypeError:
                resp = None
            except Exception as e:  # noqa: BLE001
                if "fallback" not in str(e).lower() and "beta" not in str(e).lower():
                    raise
        if resp is None:
            resp = await self.client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError("model refused the request")
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(text)

    async def text(self, system: str, prompt: str, effort: str = "medium") -> str:
        resp = await self.client.messages.create(model=self.model, max_tokens=4096, system=system,
                                                 messages=[{"role": "user", "content": prompt}], output_config=self._effort(effort))
        return "".join(b.text for b in resp.content if b.type == "text")




class OpenAICompatProvider:
    """OpenAI-compatible chat provider: W&B Inference (open models hosted on CoreWeave) or OpenAI itself.

    Speaks the same internal conversation format as AnthropicProvider (Anthropic-style content blocks) and
    translates to/from the OpenAI wire format.
    """

    def __init__(self, name: str, model: str, base_url: str | None = None, api_key: str | None = None, project: str | None = None):
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        if project:
            kwargs["project"] = project
        self.name = name
        self.model = model
        self.client = AsyncOpenAI(**kwargs)
        self.live = True

    @staticmethod
    def _to_openai(messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            role, content = m.get("role", "user"), m.get("content")
            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue
            blocks = list(content or [])
            if role == "assistant":
                text = "".join(_blk(b, "text") or "" for b in blocks if _btype(b) == "text")
                calls = []
                for b in blocks:
                    if _btype(b) == "tool_use":
                        calls.append({"id": _blk(b, "id"), "type": "function",
                                      "function": {"name": _blk(b, "name"), "arguments": json.dumps(_blk(b, "input") or {})}})
                msg: dict[str, Any] = {"role": "assistant", "content": text or None}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
            else:
                texts = []
                for b in blocks:
                    if _btype(b) == "tool_result":
                        c = _blk(b, "content")
                        out.append({"role": "tool", "tool_call_id": _blk(b, "tool_use_id"), "content": c if isinstance(c, str) else json.dumps(c)})
                    elif _btype(b) == "text":
                        texts.append(_blk(b, "text") or "")
                if texts:
                    out.append({"role": "user", "content": " ".join(texts)})
        return out

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict], effort: str = "medium") -> AssistantTurn:
        oai_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools]
        resp = await self.client.chat.completions.create(
            model=self.model, max_tokens=1024, temperature=0.4, tools=oai_tools, tool_choice="auto",
            messages=[{"role": "system", "content": system}] + self._to_openai(messages))
        m = resp.choices[0].message
        text = (m.content or "").strip()
        content: list[Any] = [{"type": "text", "text": text}] if text else []
        uses = []
        for tc in (m.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            uses.append({"id": tc.id, "name": tc.function.name, "input": args})
            content.append({"type": "tool_use", "id": tc.id, "name": tc.function.name, "input": args})
        return AssistantTurn(content=content, text=text, tool_uses=uses, stop_reason="tool_use" if uses else "end_turn", model=self.model)

    async def json(self, system: str, prompt: str, schema: dict, effort: str = "high", **_: Any) -> dict:
        sys_msg = system + "\n\nRespond with ONLY a JSON object that matches this JSON schema exactly (no prose, no code fences):\n" + json.dumps(schema)
        try:
            resp = await self.client.chat.completions.create(
                model=self.model, max_tokens=8000, temperature=0.2,
                response_format={"type": "json_schema", "json_schema": {"name": "out", "schema": schema}},
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}])
        except Exception:  # noqa: BLE001  (backend may not support json_schema)
            resp = await self.client.chat.completions.create(
                model=self.model, max_tokens=8000, temperature=0.2, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}])
        return _parse_json(resp.choices[0].message.content or "{}")

    async def text(self, system: str, prompt: str, effort: str = "medium") -> str:
        resp = await self.client.chat.completions.create(model=self.model, max_tokens=2048, temperature=0.4,
                                                         messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        return resp.choices[0].message.content or ""


def _btype(b: Any) -> str | None:
    return b.get("type") if isinstance(b, dict) else getattr(b, "type", None)


def _blk(b: Any, k: str) -> Any:
    return b.get(k) if isinstance(b, dict) else getattr(b, k, None)


def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.lower().startswith("json") else t
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i:j + 1])
        raise

# ------------------------------------------------------------------ mock ------
_ORDER_RE = re.compile(r"\bNB-?\s?(\d{4})\b", re.I)
_CUST_RE = re.compile(r"\bC(1\d{3})\b")
_MONEY_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
_PCT_RE = re.compile(r"(\d{1,3})\s?%")
_CODE_RE = re.compile(r"\b([A-Z]{3,}\d{1,2})\b")


class MockProvider:
    """Deterministic stand-in used when no API key is configured (tests, offline dev).

    The mock support agent is deliberately naive: it does what the message asks, which is exactly the
    failure mode the gate must catch. It is never used to fake breaches: every tool call still goes
    through the gate and the oracle for real.
    """
    name = "mock"
    live = False

    def __init__(self, model: str = "mock"):
        self.model = model
        self._n = 0

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict], effort: str = "medium") -> AssistantTurn:
        persona = _extract_persona(system)
        last = messages[-1]
        if isinstance(last.get("content"), list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in last["content"]):
            results = [b for b in last["content"] if b.get("type") == "tool_result"]
            texts = []
            for r in results:
                try:
                    d = json.loads(r.get("content") or "{}")
                except json.JSONDecodeError:
                    d = {"raw": r.get("content")}
                if d.get("blocked"):
                    texts.append("I'm not able to do that: it was blocked by our action policy. I can escalate to a human if you like.")
                elif d.get("error"):
                    texts.append(f"I couldn't complete that: {d['error']}.")
                elif "refund_id" in d:
                    texts.append(f"Done. I've refunded ${d['amount']:.2f} on {d['order_id']}.")
                elif "shipping_address" in d and d.get("ok"):
                    texts.append(f"Done. {d['order_id']} will now ship to {d['shipping_address']}.")
                elif "new_total" in d:
                    texts.append(f"Applied {d['percent']:g}% with {d['code']}. New total ${d['new_total']:.2f}.")
                elif "credited" in d:
                    texts.append(f"I've added ${d['credited']:.2f} of store credit to {d['customer_id']}.")
                elif "ticket" in d:
                    texts.append(f"I've escalated this to a human (ticket {d['ticket']}).")
                elif "status" in d and "items" in d:
                    texts.append(f"Order {d['id']}: {d['status']}, total ${d['total']:.2f}, shipping to {d['shipping_address']}.")
                elif "email" in d:
                    texts.append(f"{d['name']} ({d['email']}), {d['tier']} tier, {d['address']}, {d['phone']}.")
                else:
                    texts.append("Done.")
            return AssistantTurn(content=[{"type": "text", "text": " ".join(texts)}], text=" ".join(texts))

        user_msg = last["content"] if isinstance(last["content"], str) else " ".join(b.get("text", "") for b in last["content"] if isinstance(b, dict))
        m = user_msg
        low = m.lower()
        orders = [f"NB-{x}" for x in _ORDER_RE.findall(m)]
        order_id = orders[0] if orders else persona.get("order_id", "")
        custs = _CUST_RE.findall(m)
        cust_id = f"C{custs[0]}" if custs else persona.get("customer_id", "")
        money = [float(x) for x in _MONEY_RE.findall(m)]
        pct = [float(x) for x in _PCT_RE.findall(m)]
        codes = [c for c in _CODE_RE.findall(m)]
        self._n += 1
        tid = f"toolu_mock_{self._n}"

        def use(name: str, inp: dict) -> AssistantTurn:
            block = {"type": "tool_use", "id": tid, "name": name, "input": inp}
            return AssistantTurn(content=[{"type": "text", "text": "Let me take care of that."}, block], text="Let me take care of that.",
                                 tool_uses=[{"id": tid, "name": name, "input": inp}], stop_reason="tool_use")

        if "refund" in low or "money back" in low or "return " in low:
            amount = money[0] if money else float(persona.get("order_total", 0) or 0)
            return use("issue_refund", {"order_id": order_id, "amount": amount, "reason": "customer request"})
        if "address" in low and ("change" in low or "ship" in low or "update" in low or "deliver" in low or "send" in low):
            addr = _after(m, ["to "]) or "1 Attacker Way, San Francisco, CA 94110"
            return use("change_shipping_address", {"order_id": order_id, "new_address": addr})
        if "discount" in low or "code" in low or "% off" in low or pct:
            p = pct[0] if pct else (10.0 if "WELCOME10" in m else 15.0)
            return use("apply_discount", {"order_id": order_id, "percent": p, "code": codes[0] if codes else "LOYAL15"})
        if "credit" in low:
            amount = money[0] if money else 20.0
            return use("grant_store_credit", {"customer_id": cust_id, "amount": amount, "reason": "goodwill"})
        if "human" in low or "supervisor" in low and "override" not in low:
            return use("escalate_to_human", {"summary": m[:120]})
        if "profile" in low or "email" in low or "phone" in low or "look up" in low and not orders:
            q = cust_id if custs else (_after(m, ["i'm ", "i am ", "name is "]) or persona.get("name", ""))
            return use("lookup_customer", {"query": q.strip(" ,.")})
        if orders or "order" in low or "where" in low or "status" in low:
            return use("lookup_order", {"order_id": order_id})
        return AssistantTurn(content=[{"type": "text", "text": "Happy to help. What would you like me to do with your order?"}],
                             text="Happy to help. What would you like me to do with your order?")

    async def json(self, system: str, prompt: str, schema: dict, effort: str = "high", mock_task: str | None = None, mock_ctx: dict | None = None) -> dict:
        from . import mockbrains

        return mockbrains.answer(mock_task or "", mock_ctx or {}, schema)

    async def text(self, system: str, prompt: str, effort: str = "medium") -> str:
        return "mock"


def _after(text: str, markers: list[str]) -> str:
    low = text.lower()
    for mk in markers:
        i = low.rfind(mk)
        if i >= 0:
            frag = text[i + len(mk):].strip()
            frag = re.split(r"[.!?\n]| instead| right now| before", frag)[0]
            if len(frag) > 6:
                return frag.strip()
    return ""


def _extract_persona(system: str) -> dict:
    m = re.search(r"PERSONA_JSON=(\{.*?\})\s*$", system, re.S | re.M)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


# ------------------------------------------------------------ factory -------
_cache: dict[str, Any] = {}
WANDB_INFERENCE_URL = "https://api.inference.wandb.ai/v1"


def _wandb_inference(model: str) -> OpenAICompatProvider:
    project = f"{CONFIG.wandb_entity}/{CONFIG.weave_project}" if CONFIG.wandb_entity else None
    return OpenAICompatProvider("wandb-inference", model, base_url=WANDB_INFERENCE_URL, api_key=CONFIG.wandb_key, project=project)


def _pick(role: str, claude_model: str, wandb_model: str):
    if CONFIG.mode != "live":
        return MockProvider(wandb_model)
    if CONFIG.anthropic_key:
        return AnthropicProvider(claude_model)
    if CONFIG.wandb_key:
        return _wandb_inference(wandb_model)
    return MockProvider(wandb_model)


def agent_llm():
    if "agent" not in _cache:
        _cache["agent"] = _pick("agent", CONFIG.agent_model, CONFIG.wandb_agent_model)
    return _cache["agent"]


def defender_llm():
    if "defender" not in _cache:
        _cache["defender"] = _pick("defender", CONFIG.defender_model, CONFIG.wandb_defender_model)
    return _cache["defender"]


def redteam_llm():
    """GPT-6 Astra (OpenAI) when configured; else a second W&B-hosted model family; else the defender model; else mock."""
    if "redteam" not in _cache:
        if CONFIG.mode == "live" and CONFIG.openai_key:
            try:
                _cache["redteam"] = OpenAICompatProvider("openai", CONFIG.redteam_model, api_key=CONFIG.openai_key)
            except Exception:  # noqa: BLE001
                _cache["redteam"] = defender_llm()
        elif CONFIG.mode == "live" and CONFIG.wandb_key:
            _cache["redteam"] = _wandb_inference(CONFIG.wandb_redteam_model)
        else:
            _cache["redteam"] = defender_llm()
    return _cache["redteam"]


def provider_status() -> dict:
    a, d, r = agent_llm(), defender_llm(), redteam_llm()
    return {
        "agent": {"provider": a.name, "model": a.model, "live": bool(a.live)},
        "defender": {"provider": d.name, "model": d.model, "live": bool(d.live)},
        "redteam": {"provider": r.name, "model": r.model, "live": bool(r.live)},
    }
