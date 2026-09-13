"""Tracing: Weave when a W&B key is present, always a local trace store for the UI."""
from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
import json
import os
import time
from typing import Any, Callable

from .config import CONFIG
from .db import Store, new_id, now_iso

_parent: contextvars.ContextVar[str | None] = contextvars.ContextVar("siege_trace_parent", default=None)
_turn: contextvars.ContextVar[str | None] = contextvars.ContextVar("siege_trace_turn", default=None)

_store: Store | None = None
_weave_live = False
_weave_url: str | None = None
_weave_client = None


def init(store: Store) -> None:
    global _store, _weave_live, _weave_url, _weave_client
    _store = store
    if CONFIG.wandb_key and CONFIG.mode == "live":
        try:
            os.environ.setdefault("WANDB_API_KEY", CONFIG.wandb_key)
            os.environ.setdefault("WANDB_SILENT", "true")
            import weave

            _weave_client = weave.init(CONFIG.weave_project)
            entity = getattr(_weave_client, "entity", None)
            project = getattr(_weave_client, "project", CONFIG.weave_project)
            _weave_url = f"https://wandb.ai/{entity}/{project}/weave" if entity else None
            _weave_live = True
        except Exception as e:  # noqa: BLE001
            print(f"[tracing] weave init failed, local traces only: {e}")
            _weave_live = False


def weave_live() -> bool:
    return _weave_live


def weave_url() -> str | None:
    return _weave_url


def set_turn(turn_id: str | None) -> None:
    _turn.set(turn_id)


def _safe(v: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "…"
    if isinstance(v, (str,)):
        return v if len(v) <= 800 else v[:800] + "…"
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, dict):
        return {str(k): _safe(x, depth + 1) for k, x in list(v.items())[:40]}
    if isinstance(v, (list, tuple)):
        return [_safe(x, depth + 1) for x in list(v)[:40]]
    try:
        json.dumps(v)
        return v
    except TypeError:
        return repr(v)[:200]


def traced(name: str) -> Callable:
    """Decorator: records a local trace (with parent/turn context) and a Weave call when live."""

    def deco(fn: Callable) -> Callable:
        is_coro = inspect.iscoroutinefunction(fn)
        weave_op = None
        if _weave_live or (CONFIG.wandb_key and CONFIG.mode == "live"):
            try:
                import weave

                weave_op = weave.op(fn, name=name)
            except Exception:  # noqa: BLE001
                weave_op = None

        def _record(tid: str, parent: str | None, turn: str | None, started: str, t0: float, inputs: dict, output: Any, url: str | None) -> None:
            if _store is None:
                return
            try:
                _store.add_trace({"id": tid, "name": name, "parent_id": parent, "turn_id": turn, "started_at": started,
                                  "duration_ms": int((time.perf_counter() - t0) * 1000), "inputs": _safe(inputs), "output": _safe(output), "weave_url": url})
            except Exception as e:  # noqa: BLE001
                print(f"[tracing] local record failed: {e}")

        def _inputs(args, kwargs) -> dict:
            try:
                bound = inspect.signature(fn).bind_partial(*args, **kwargs)
                return {k: v for k, v in bound.arguments.items() if k not in ("self", "store", "state_obj")}
            except (TypeError, ValueError):
                return {"args": args, "kwargs": kwargs}

        @functools.wraps(fn)
        async def a_inner(*args, **kwargs):
            tid, parent, turn, started, t0 = new_id("t"), _parent.get(), _turn.get(), now_iso(), time.perf_counter()
            token = _parent.set(tid)
            url = None
            try:
                if weave_op is not None and _weave_live:
                    try:
                        out, call = await weave_op.call(*args, **kwargs)
                        url = getattr(call, "ui_url", None)
                    except Exception:  # noqa: BLE001
                        out = await fn(*args, **kwargs)
                else:
                    out = await fn(*args, **kwargs)
                _record(tid, parent, turn, started, t0, _inputs(args, kwargs), out, url)
                return out
            except Exception as e:
                _record(tid, parent, turn, started, t0, _inputs(args, kwargs), {"error": repr(e)}, url)
                raise
            finally:
                _parent.reset(token)

        @functools.wraps(fn)
        def s_inner(*args, **kwargs):
            tid, parent, turn, started, t0 = new_id("t"), _parent.get(), _turn.get(), now_iso(), time.perf_counter()
            token = _parent.set(tid)
            url = None
            try:
                if weave_op is not None and _weave_live:
                    try:
                        out, call = weave_op.call(*args, **kwargs)
                        url = getattr(call, "ui_url", None)
                    except Exception:  # noqa: BLE001
                        out = fn(*args, **kwargs)
                else:
                    out = fn(*args, **kwargs)
                _record(tid, parent, turn, started, t0, _inputs(args, kwargs), out, url)
                return out
            except Exception as e:
                _record(tid, parent, turn, started, t0, _inputs(args, kwargs), {"error": repr(e)}, url)
                raise
            finally:
                _parent.reset(token)

        return a_inner if is_coro else s_inner

    return deco


async def run_weave_evaluation(name: str, rows: list[dict], predict: Callable, scorer: Callable) -> dict | None:
    """Log an eval to Weave (dataset rows + scorer). Returns {'url':..., 'summary':...} or None when Weave is off."""
    if not _weave_live:
        return None
    try:
        import weave

        @weave.op(name=f"{name}.predict")
        async def model(sample_id: str, message: str, tool: str, kind: str) -> str:
            # weave passes dataset columns by parameter name
            return await predict({"sample_id": sample_id, "message": message, "tool": tool, "kind": kind})

        @weave.op(name=f"{name}.scorer")
        def score(output: str, expected: str) -> dict:
            return scorer(output, expected)

        ev = weave.Evaluation(name=name, dataset=rows, scorers=[score])
        url = _weave_url
        try:
            res, call = await ev.evaluate.call(ev, model)
            url = getattr(call, "ui_url", None) or url
        except Exception:  # noqa: BLE001
            res = ev.evaluate(model)
            if asyncio.iscoroutine(res):
                res = await res
        return {"url": url, "summary": _safe(res)}
    except Exception as e:  # noqa: BLE001
        print(f"[tracing] weave evaluation failed: {e}")
        return None
