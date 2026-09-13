"""SQLite store for SIEGE. Synchronous sqlite3 behind a lock; every op is small."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import seeds

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY, name TEXT, email TEXT, tier TEXT, address TEXT, phone TEXT, credit_granted INTEGER DEFAULT 0, store_credit REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, customer_id TEXT, items TEXT, total REAL, status TEXT, placed_at TEXT, delivered_at TEXT, refunded_amount REAL DEFAULT 0, discount_pct REAL DEFAULT 0, shipping_address TEXT);
CREATE TABLE IF NOT EXISTS attackers(id TEXT PRIMARY KEY, nickname TEXT, customer_id TEXT, score INTEGER DEFAULT 0, breaches INTEGER DEFAULT 0, attacks INTEGER DEFAULT 0, joined_at TEXT, synthetic INTEGER DEFAULT 0, earned TEXT DEFAULT '[]', last_seen TEXT);
CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY, attacker_id TEXT, round INTEGER, message TEXT, reply TEXT, tool_calls TEXT, breach_points INTEGER DEFAULT 0, created_at TEXT, latency_ms INTEGER, gate_version INTEGER);
CREATE TABLE IF NOT EXISTS breaches(id TEXT PRIMARY KEY, turn_id TEXT, attacker_id TEXT, round INTEGER, category TEXT, tool TEXT, args TEXT, reason TEXT, points INTEGER, message TEXT, created_at TEXT, gate_version INTEGER, gate_probabilities TEXT, patched_in INTEGER);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, seq INTEGER, type TEXT, at TEXT, round INTEGER, attacker_id TEXT, nickname TEXT, text TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS rounds(number INTEGER PRIMARY KEY, started_at TEXT, ended_at TEXT, seconds INTEGER, attacks INTEGER DEFAULT 0, breaches INTEGER DEFAULT 0, breach_rate REAL DEFAULT 0, benign_allow_rate REAL DEFAULT 1, gate_version_start INTEGER, gate_version_end INTEGER, status TEXT);
CREATE TABLE IF NOT EXISTS gate_versions(version INTEGER PRIMARY KEY, created_at TEXT, status TEXT, parent_version INTEGER, changelog TEXT, rules TEXT, criteria TEXT, examples TEXT, prefilter_code TEXT, eval TEXT, catch_rate REAL, benign_allow_rate REAL);
CREATE TABLE IF NOT EXISTS defender_runs(id TEXT PRIMARY KEY, round INTEGER, started_at TEXT, ended_at TEXT, stage TEXT, breaches_considered INTEGER DEFAULT 0, variants_generated INTEGER DEFAULT 0, attempts TEXT DEFAULT '[]', shipped_version INTEGER, log TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS traces(id TEXT PRIMARY KEY, seq INTEGER, name TEXT, parent_id TEXT, turn_id TEXT, started_at TEXT, duration_ms INTEGER, inputs TEXT, output TEXT, weave_url TEXT);
CREATE TABLE IF NOT EXISTS gate_samples(id TEXT PRIMARY KEY, kind TEXT, state TEXT, expected TEXT, tool TEXT, message TEXT, source TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _j(v: Any) -> str:
    return json.dumps(v, default=str)


def _row(r: sqlite3.Row | None, json_cols: tuple[str, ...] = ()) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for c in json_cols:
        if c in d and isinstance(d[c], str):
            try:
                d[c] = json.loads(d[c])
            except json.JSONDecodeError:
                pass
    return d


ORDER_J = ("items",)
ATT_J = ("earned",)
TURN_J = ("tool_calls",)
BREACH_J = ("args", "gate_probabilities")
EVENT_J = ("data",)
GV_J = ("rules", "criteria", "examples", "eval")
RUN_J = ("attempts", "log")
TRACE_J = ("inputs", "output")
SAMPLE_J = ("state",)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self._seq = 0
        self._ensure_seeded()

    # ---------- seeding / reset ----------
    def _ensure_seeded(self) -> None:
        with self.lock:
            n = self.conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            if n == 0:
                self.reseed_store()
            if self.conn.execute("SELECT COUNT(*) FROM gate_versions").fetchone()[0] == 0:
                from .gate import seed_gate_version  # local import to avoid cycle
                self.insert_gate_version(seed_gate_version())
            self._seq = self.conn.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]

    def reseed_store(self) -> None:
        customers, orders = seeds.build_store()
        with self.lock:
            self.conn.execute("DELETE FROM customers")
            self.conn.execute("DELETE FROM orders")
            for c in customers:
                self.conn.execute("INSERT INTO customers VALUES(?,?,?,?,?,?,?,?)",
                                  (c["id"], c["name"], c["email"], c["tier"], c["address"], c["phone"], 0, 0.0))
            for o in orders:
                self.conn.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?)",
                                  (o["id"], o["customer_id"], _j(o["items"]), o["total"], o["status"], o["placed_at"],
                                   o["delivered_at"], o["refunded_amount"], o["discount_pct"], o["shipping_address"]))
            self.conn.commit()

    def reset(self) -> None:
        with self.lock:
            for t in ("attackers", "turns", "breaches", "events", "rounds", "defender_runs", "traces"):
                self.conn.execute(f"DELETE FROM {t}")
            self.conn.execute("DELETE FROM gate_samples WHERE source != 'seed'")
            self.conn.execute("DELETE FROM gate_versions WHERE version > 1")
            self.conn.execute("DELETE FROM kv")
            self.conn.commit()
            self.reseed_store()
            self._seq = 0

    # ---------- kv ----------
    def get_kv(self, key: str, default: Any = None) -> Any:
        with self.lock:
            r = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_kv(self, key: str, value: Any) -> None:
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (key, _j(value)))
            self.conn.commit()

    # ---------- store data ----------
    def customers(self) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM customers ORDER BY id")]

    def orders(self) -> list[dict]:
        with self.lock:
            return [_row(r, ORDER_J) for r in self.conn.execute("SELECT * FROM orders ORDER BY id")]

    def customer(self, cid: str) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone())

    def find_customer(self, query: str) -> dict | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self.lock:
            r = self.conn.execute("SELECT * FROM customers WHERE lower(id)=? OR lower(email)=?", (q, q)).fetchone()
            if r:
                return dict(r)
            r = self.conn.execute("SELECT * FROM customers WHERE lower(name) LIKE ? ORDER BY id LIMIT 1", (f"%{q}%",)).fetchone()
            return dict(r) if r else None

    def order(self, oid: str) -> dict | None:
        key = (oid or "").strip().upper().replace(" ", "")
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM orders WHERE upper(id)=?", (key,)).fetchone(), ORDER_J)

    def order_for_customer(self, cid: str) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY id LIMIT 1", (cid,)).fetchone(), ORDER_J)

    def update_order(self, oid: str, **fields: Any) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.lock:
            self.conn.execute(f"UPDATE orders SET {sets} WHERE id=?", (*fields.values(), oid))
            self.conn.commit()

    def update_customer(self, cid: str, **fields: Any) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.lock:
            self.conn.execute(f"UPDATE customers SET {sets} WHERE id=?", (*fields.values(), cid))
            self.conn.commit()

    # ---------- attackers ----------
    def next_persona_customer(self) -> str:
        """Round-robin personas across customers, least-used first."""
        with self.lock:
            rows = self.conn.execute(
                "SELECT c.id, (SELECT COUNT(*) FROM attackers a WHERE a.customer_id=c.id) AS n FROM customers c ORDER BY n, c.id"
            ).fetchall()
        return rows[0][0]

    def create_attacker(self, nickname: str, customer_id: str, synthetic: bool = False) -> dict:
        aid = new_id("a")
        with self.lock:
            self.conn.execute("INSERT INTO attackers VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (aid, nickname[:24], customer_id, 0, 0, 0, now_iso(), int(synthetic), "[]", now_iso()))
            self.conn.commit()
        return self.attacker(aid)

    def attacker(self, aid: str) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM attackers WHERE id=?", (aid,)).fetchone(), ATT_J)

    def attackers(self) -> list[dict]:
        with self.lock:
            return [_row(r, ATT_J) for r in self.conn.execute("SELECT * FROM attackers ORDER BY score DESC, breaches DESC, joined_at")]

    def touch_attacker(self, aid: str) -> None:
        with self.lock:
            self.conn.execute("UPDATE attackers SET last_seen=? WHERE id=?", (now_iso(), aid))
            self.conn.commit()

    def bump_attacker(self, aid: str, points: int, breaches: int, earned: list[str]) -> None:
        with self.lock:
            self.conn.execute("UPDATE attackers SET score=score+?, breaches=breaches+?, attacks=attacks+1, earned=?, last_seen=? WHERE id=?",
                              (points, breaches, _j(earned), now_iso(), aid))
            self.conn.commit()

    def online_count(self, seconds: int = 120) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - seconds
        with self.lock:
            rows = self.conn.execute("SELECT last_seen FROM attackers").fetchall()
        n = 0
        for (ls,) in rows:
            try:
                if datetime.fromisoformat(ls).timestamp() >= cutoff:
                    n += 1
            except (TypeError, ValueError):
                pass
        return n

    # ---------- turns / breaches ----------
    def insert_turn(self, t: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT INTO turns VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (t["id"], t["attacker_id"], t["round"], t["message"], t["reply"], _j(t["tool_calls"]),
                               t["breach_points"], t["created_at"], t["latency_ms"], t["gate_version"]))
            self.conn.commit()

    def turns_for(self, aid: str) -> list[dict]:
        with self.lock:
            return [_row(r, TURN_J) for r in self.conn.execute("SELECT * FROM turns WHERE attacker_id=? ORDER BY created_at", (aid,))]

    def turn(self, tid: str) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM turns WHERE id=?", (tid,)).fetchone(), TURN_J)

    def insert_breach(self, b: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT INTO breaches VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (b["id"], b["turn_id"], b["attacker_id"], b["round"], b["category"], b["tool"], _j(b["args"]),
                               b["reason"], b["points"], b["message"], b["created_at"], b["gate_version"], _j(b["gate_probabilities"]), None))
            self.conn.commit()

    def breaches(self, limit: int = 100, unpatched_only: bool = False) -> list[dict]:
        q = "SELECT b.*, a.nickname FROM breaches b LEFT JOIN attackers a ON a.id=b.attacker_id"
        if unpatched_only:
            q += " WHERE b.patched_in IS NULL"
        q += " ORDER BY b.created_at DESC LIMIT ?"
        with self.lock:
            return [_row(r, BREACH_J) for r in self.conn.execute(q, (limit,))]

    def mark_breaches_patched(self, ids: list[str], version: int) -> None:
        if not ids:
            return
        with self.lock:
            self.conn.executemany("UPDATE breaches SET patched_in=? WHERE id=?", [(version, i) for i in ids])
            self.conn.commit()

    def category_first_in_round(self, category: str, round_no: int) -> bool:
        with self.lock:
            n = self.conn.execute("SELECT COUNT(*) FROM breaches WHERE category=? AND round=?", (category, round_no)).fetchone()[0]
        return n == 0

    def round_counts(self, round_no: int) -> dict:
        with self.lock:
            turns = [_row(r, TURN_J) for r in self.conn.execute("SELECT * FROM turns WHERE round=?", (round_no,))]
        attacks = len(turns)
        breaches = sum(1 for t in turns if t["breach_points"] > 0)
        allowed_benign = blocked_benign = 0
        for t in turns:
            for tc in t["tool_calls"]:
                if tc["oracle"]["allowed"]:
                    if tc["benign_block"]:
                        blocked_benign += 1
                    else:
                        allowed_benign += 1
        denom = allowed_benign + blocked_benign
        return {
            "attacks": attacks, "breaches": breaches,
            "breach_rate": (breaches / attacks) if attacks else 0.0,
            "benign_allow_rate": (allowed_benign / denom) if denom else 1.0,
        }

    def totals(self) -> dict:
        with self.lock:
            turns = [_row(r, TURN_J) for r in self.conn.execute("SELECT tool_calls, breach_points FROM turns")]
            attackers = self.conn.execute("SELECT COUNT(*) FROM attackers").fetchone()[0]
        blocks = benign_blocks = 0
        for t in turns:
            for tc in t["tool_calls"]:
                if tc["gate"]["decision"] in ("block", "escalate") or tc["gate"].get("prefilter_hit"):
                    blocks += 1
                if tc["benign_block"]:
                    benign_blocks += 1
        return {"attacks": len(turns), "breaches": sum(1 for t in turns if t["breach_points"] > 0), "blocks": blocks,
                "benign_blocks": benign_blocks, "attackers": attackers, "online": self.online_count()}

    # ---------- events ----------
    def add_event(self, type_: str, text: str, round_no: int, attacker: dict | None = None, data: dict | None = None) -> dict:
        with self.lock:
            self._seq += 1
            event_data = dict(data or {})
            if attacker:
                event_data["synthetic"] = bool(attacker.get("synthetic", False))
            ev = {"id": new_id("e"), "seq": self._seq, "type": type_, "at": now_iso(), "round": round_no,
                  "attacker": ({"id": attacker["id"], "nickname": attacker["nickname"]} if attacker else None),
                  "text": text, "data": event_data}
            self.conn.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",
                              (ev["id"], ev["seq"], type_, ev["at"], round_no, attacker["id"] if attacker else None,
                               attacker["nickname"] if attacker else None, text, _j(ev["data"])))
            self.conn.commit()
        return ev

    def events(self, limit: int = 50) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT e.*, a.synthetic AS attacker_synthetic FROM events e LEFT JOIN attackers a ON a.id=e.attacker_id ORDER BY e.seq DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = _row(r, EVENT_J)
            synthetic = d.pop("attacker_synthetic")
            if d.get("attacker_id") and synthetic is not None:
                d["data"]["synthetic"] = bool(synthetic)
            d["attacker"] = {"id": d.pop("attacker_id"), "nickname": d.pop("nickname")} if d.get("attacker_id") else None
            d.pop("seq", None)
            out.append(d)
        return out

    # ---------- rounds ----------
    def current_round(self) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM rounds WHERE status='live' ORDER BY number DESC LIMIT 1").fetchone())

    def last_round(self) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM rounds ORDER BY number DESC LIMIT 1").fetchone())

    def rounds(self) -> list[dict]:
        with self.lock:
            return [_row(r) for r in self.conn.execute("SELECT * FROM rounds ORDER BY number")]

    def start_round(self, seconds: int, gate_version: int) -> dict:
        with self.lock:
            n = (self.conn.execute("SELECT COALESCE(MAX(number),0) FROM rounds").fetchone()[0] or 0) + 1
            self.conn.execute("INSERT INTO rounds VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                              (n, now_iso(), None, seconds, 0, 0, 0.0, 1.0, gate_version, None, "live"))
            self.conn.commit()
        return self.round(n)

    def round(self, n: int) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM rounds WHERE number=?", (n,)).fetchone())

    def update_round(self, n: int, **fields: Any) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.lock:
            self.conn.execute(f"UPDATE rounds SET {sets} WHERE number=?", (*fields.values(), n))
            self.conn.commit()

    # ---------- gate versions ----------
    def insert_gate_version(self, gv: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO gate_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                              (gv["version"], gv["created_at"], gv["status"], gv.get("parent_version"), gv["changelog"],
                               _j(gv["rules"]), _j(gv["criteria"]), _j(gv["examples"]), gv.get("prefilter_code") or "",
                               _j(gv.get("eval")), gv.get("catch_rate"), gv.get("benign_allow_rate")))
            self.conn.commit()

    def next_gate_version_number(self) -> int:
        with self.lock:
            return (self.conn.execute("SELECT COALESCE(MAX(version),0) FROM gate_versions").fetchone()[0] or 0) + 1

    def gate_version(self, v: int) -> dict | None:
        with self.lock:
            return _row(self.conn.execute("SELECT * FROM gate_versions WHERE version=?", (v,)).fetchone(), GV_J)

    def gate_versions(self) -> list[dict]:
        with self.lock:
            return [_row(r, GV_J) for r in self.conn.execute("SELECT * FROM gate_versions ORDER BY version")]

    def active_gate_version(self) -> int:
        v = self.get_kv("active_gate_version")
        if v is None:
            with self.lock:
                v = self.conn.execute("SELECT MAX(version) FROM gate_versions WHERE status IN ('seed','shipped')").fetchone()[0] or 1
        return int(v)

    def set_active_gate_version(self, v: int) -> None:
        self.set_kv("active_gate_version", int(v))

    # ---------- defender runs ----------
    def upsert_run(self, run: dict) -> None:
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO defender_runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (run["id"], run["round"], run["started_at"], run.get("ended_at"), run["stage"],
                               run["breaches_considered"], run["variants_generated"], _j(run["attempts"]),
                               run.get("shipped_version"), _j(run["log"])))
            self.conn.commit()

    def runs(self, limit: int = 20) -> list[dict]:
        with self.lock:
            return [_row(r, RUN_J) for r in self.conn.execute("SELECT * FROM defender_runs ORDER BY started_at DESC LIMIT ?", (limit,))]

    # ---------- traces ----------
    def add_trace(self, tr: dict) -> None:
        with self.lock:
            self._seq += 1
            self.conn.execute("INSERT INTO traces VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (tr["id"], self._seq, tr["name"], tr.get("parent_id"), tr.get("turn_id"), tr["started_at"],
                               tr["duration_ms"], _j(tr.get("inputs", {})), _j(tr.get("output")), tr.get("weave_url")))
            self.conn.commit()

    def traces(self, limit: int = 100, turn_id: str | None = None) -> list[dict]:
        with self.lock:
            if turn_id:
                rows = self.conn.execute("SELECT * FROM traces WHERE turn_id=? ORDER BY seq DESC LIMIT ?", (turn_id, limit)).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM traces ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = _row(r, TRACE_J)
            d.pop("seq", None)
            out.append(d)
        return out

    # ---------- gate samples (eval datasets) ----------
    def add_sample(self, kind: str, state: dict, expected: str, tool: str, message: str, source: str) -> str:
        sid = new_id("s")
        with self.lock:
            self.conn.execute("INSERT INTO gate_samples VALUES(?,?,?,?,?,?,?,?)",
                              (sid, kind, _j(state), expected, tool, message, source, now_iso()))
            self.conn.commit()
        return sid

    def samples(self, kind: str | None = None, limit: int = 2000) -> list[dict]:
        with self.lock:
            if kind:
                rows = self.conn.execute("SELECT * FROM gate_samples WHERE kind=? ORDER BY created_at DESC LIMIT ?", (kind, limit)).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM gate_samples ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [_row(r, SAMPLE_J) for r in rows]

    def sample_count(self, source: str) -> int:
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM gate_samples WHERE source=?", (source,)).fetchone()[0]
