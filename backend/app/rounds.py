"""Rounds, metrics series, the state snapshot, and the background ticker."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from .config import CONFIG
from .db import Store, now_iso
from .hub import HUB


class RoundManager:
    def __init__(self, store: Store, gate, defender):
        self.store = store
        self.gate = gate
        self.defender = defender
        self.settings = CONFIG.settings
        self._task: asyncio.Task | None = None
        self._defend_lock = asyncio.Lock()

    # ---- lifecycle
    def start_round(self) -> dict:
        cur = self.store.current_round()
        if cur:
            return cur
        r = self.store.start_round(self.settings.round_seconds, self.store.active_gate_version())
        ev = self.store.add_event("round_start", f"Round {r['number']} started ({r['seconds']}s) on gate v{r['gate_version_start']}", r["number"])
        HUB.emit(ev)
        return r

    def ensure_round(self) -> dict:
        return self.store.current_round() or self.start_round()

    async def end_round(self, trigger_defender: bool | None = None) -> dict | None:
        cur = self.store.current_round()
        if not cur:
            return None
        m = self.store.round_counts(cur["number"])
        self.store.update_round(cur["number"], ended_at=now_iso(), status="ended", attacks=m["attacks"], breaches=m["breaches"],
                                breach_rate=m["breach_rate"], benign_allow_rate=m["benign_allow_rate"], gate_version_end=self.store.active_gate_version())
        r = self.store.round(cur["number"])
        ev = self.store.add_event("round_end", f"Round {r['number']} ended: {m['breaches']}/{m['attacks']} breached ({m['breach_rate']:.0%})", r["number"],
                                  data={"breach_rate": m["breach_rate"], "benign_allow_rate": m["benign_allow_rate"]})
        HUB.emit(ev)
        do_defend = self.settings.auto_defend if trigger_defender is None else trigger_defender
        if do_defend:
            asyncio.ensure_future(self.run_defender(r["number"]))
        return r

    async def run_defender(self, round_no: int) -> dict:
        async with self._defend_lock:
            run = await self.defender.run(round_no)
        # start the next round automatically so the loop keeps going
        if not self.store.current_round():
            self.start_round()
        return run

    async def ticker(self) -> None:
        while True:
            try:
                cur = self.store.current_round()
                if cur:
                    started = datetime.fromisoformat(cur["started_at"])
                    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                    if elapsed >= cur["seconds"]:
                        await self.end_round()
                    else:
                        # live metrics on the round row for the state snapshot
                        pass
                await HUB.broadcast({"type": "state", "state": self.state()})
            except Exception as e:  # noqa: BLE001
                print(f"[rounds] ticker error: {e!r}")
            await asyncio.sleep(2)

    def start_ticker(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self.ticker())

    # ---- views
    def seconds_left(self, cur: dict | None) -> int:
        if not cur:
            return 0
        started = datetime.fromisoformat(cur["started_at"])
        return max(0, int(cur["seconds"] - (datetime.now(timezone.utc) - started).total_seconds()))

    def series(self) -> list[dict]:
        out = []
        for r in self.store.rounds():
            if r["status"] != "ended":
                continue
            gv = self.store.gate_version(r.get("gate_version_end") or r["gate_version_start"])
            out.append({"round": r["number"], "breach_rate": r["breach_rate"], "benign_allow_rate": r["benign_allow_rate"],
                        "catch_rate": gv.get("catch_rate") if gv else None, "gate_version": r.get("gate_version_end") or r["gate_version_start"]})
        cur = self.store.current_round()
        if cur:
            m = self.store.round_counts(cur["number"])
            gv = self.store.gate_version(self.store.active_gate_version())
            out.append({"round": cur["number"], "breach_rate": m["breach_rate"], "benign_allow_rate": m["benign_allow_rate"],
                        "catch_rate": gv.get("catch_rate") if gv else None, "gate_version": self.store.active_gate_version(), "live": True})
        return out

    def state(self) -> dict:
        from . import sandbox as sbx
        from . import tracing
        from .llm import provider_status

        cur = self.store.current_round()
        m = self.store.round_counts(cur["number"]) if cur else {"attacks": 0, "breaches": 0, "breach_rate": 0.0, "benign_allow_rate": 1.0}
        runs = self.store.runs(limit=1)
        providers = provider_status()
        providers["gate"] = self.gate.status()
        providers["weave"] = {"live": tracing.weave_live(), "project": CONFIG.weave_project, "url": tracing.weave_url()}
        providers["sandbox"] = sbx.status()
        return {
            "mode": CONFIG.mode,
            "round": cur or self.store.last_round(),
            "gate_version": self.store.active_gate_version(),
            "totals": self.store.totals(),
            "current_round": {**m, "seconds_left": self.seconds_left(cur)},
            "series": self.series(),
            "defender": runs[0] if runs else None,
            "settings": self.settings.to_dict(),
            "providers": providers,
            "join_url": f"{CONFIG.public_base_url.rstrip('/')}/attack",
        }
