"""Synthetic attackers for demos without a room. Clearly labeled `synthetic` everywhere."""
from __future__ import annotations

import asyncio
import random

from .db import Store
from .hub import HUB
from .seeds import ATTACK_TEMPLATES, BENIGN_TEMPLATES

NAMES = ["koala", "otter", "lynx", "heron", "ibex", "manta", "gecko", "raven", "yak", "puma", "civet", "tapir", "eider", "kite", "moth", "newt"]


class Simulator:
    def __init__(self, store: Store, agent, rounds):
        self.store = store
        self.agent = agent
        self.rounds = rounds
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return any(not t.done() for t in self._tasks)

    async def start(self, count: int, seconds: int) -> None:
        await self.stop()
        self._stop = asyncio.Event()
        count = max(1, min(count, 60))
        for i in range(count):
            nick = f"bot-{random.choice(NAMES)}-{random.randint(10, 99)}"
            a = self.store.create_attacker(nick, self.store.next_persona_customer(), synthetic=True)
            HUB.emit(self.store.add_event("join", f"{nick} joined (synthetic)", (self.store.current_round() or {}).get("number", 0), a))
            self._tasks.append(asyncio.ensure_future(self._loop(a, seconds, i)))

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    async def _loop(self, attacker: dict, seconds: int, i: int) -> None:
        deadline = asyncio.get_event_loop().time() + seconds
        rng = random.Random(i * 7919)
        await asyncio.sleep(rng.uniform(0.2, 3.0))
        while not self._stop.is_set() and asyncio.get_event_loop().time() < deadline:
            try:
                r = self.rounds.ensure_round()
                msg = self._message(attacker, rng)
                a = self.store.attacker(attacker["id"])
                await self.agent.handle_message(a, msg, r["number"])
            except Exception as e:  # noqa: BLE001
                print(f"[simulate] {attacker['nickname']}: {e!r}")
            await asyncio.sleep(rng.uniform(3.0, 9.0))

    def _message(self, attacker: dict, rng: random.Random) -> str:
        from .agent import persona_for

        p = persona_for(self.store, attacker)
        o = p["order"]
        others = [c for c in self.store.customers() if c["id"] != p["customer_id"]]
        oc = rng.choice(others)
        oo = self.store.order_for_customer(oc["id"]) or o
        if rng.random() < 0.3:
            tpls = [t for t in BENIGN_TEMPLATES if t["needs"] == "any" or (t["needs"] == "processing" and o["status"] == "processing")
                    or (t["needs"] == "processing_nodiscount" and o["status"] == "processing" and o["discount_pct"] == 0)
                    or (t["needs"] == "delivered_recent" and o["status"] == "delivered") or t["needs"] == "no_credit"]
            t = rng.choice(tpls)
            item = o["items"][0]
            return t["message"].format(item=item["name"], order_id=o["id"], amount=f"{min(item['price'], o['total']):.2f}" if t.get("amount") == "item_price" else t.get("amount", 10),
                                       new_address=f"{rng.randint(100, 999)} Bryant St, San Francisco, CA 94107", name=p["name"])
        t = rng.choice(ATTACK_TEMPLATES)
        return t["message"].format(order_id=o["id"], other_order=oo["id"], other_name=oc["name"], other_customer_id=oc["id"],
                                   attacker_address=f"{rng.randint(100, 999)} Attacker Way, Oakland, CA 94612", big_amount=f"{o['total'] * 2:.0f}")
