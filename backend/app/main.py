"""SIEGE API + static frontend."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import SupportAgent, attacker_view
from .config import CONFIG, ROOT
from .db import Store
from .defender import Defender
from .gate import Gate
from .hub import HUB
from .policy import bounties
from .rounds import RoundManager
from .simulate import Simulator
from . import tracing


class App:
    store: Store
    gate: Gate
    agent: SupportAgent
    defender: Defender
    rounds: RoundManager
    sim: Simulator


S = App()


@asynccontextmanager
async def lifespan(app: FastAPI):
    S.store = Store(CONFIG.db_path)
    tracing.init(S.store)
    S.gate = Gate()
    S.agent = SupportAgent(S.store, S.gate)
    S.defender = Defender(S.store, S.gate)
    n = S.defender.ensure_benign_seed()
    if n:
        print(f"[siege] seeded {n} benign gate samples")
    S.rounds = RoundManager(S.store, S.gate, S.defender)
    S.sim = Simulator(S.store, S.agent, S.rounds)
    HUB.loop = asyncio.get_running_loop()
    S.rounds.start_ticker()
    from .llm import provider_status
    ps = provider_status()
    print(f"[siege] mode={CONFIG.mode} agent={ps['agent']['provider']}:{ps['agent']['model']} defender={ps['defender']['provider']}:{ps['defender']['model']} redteam={ps['redteam']['model']} gate={S.gate.status()}")
    yield
    await S.sim.stop()


app = FastAPI(title="SIEGE", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ models --
class JoinBody(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)


class ChatBody(BaseModel):
    attacker_id: str
    message: str = Field(min_length=1, max_length=2000)


class SettingsBody(BaseModel):
    round_seconds: int | None = Field(default=None, ge=15, le=3600)
    auto_defend: bool | None = None
    benign_floor: float | None = Field(default=None, ge=0, le=1)
    max_attempts: int | None = Field(default=None, ge=1, le=6)
    variants_per_breach: int | None = Field(default=None, ge=0, le=10)


class SimulateBody(BaseModel):
    count: int = Field(default=8, ge=1, le=60)
    seconds: int = Field(default=120, ge=5, le=3600)


class RollbackBody(BaseModel):
    version: int


# ---------------------------------------------------------------- attacker --
@app.post("/api/join")
async def join(body: JoinBody):
    a = S.store.create_attacker(body.nickname.strip(), S.store.next_persona_customer())
    r = S.store.current_round()
    HUB.emit(S.store.add_event("join", f"{a['nickname']} joined the siege", r["number"] if r else 0, a))
    return attacker_view(S.store, a)


@app.get("/api/attackers/{aid}")
async def get_attacker(aid: str):
    a = S.store.attacker(aid)
    if not a:
        raise HTTPException(404, "attacker not found")
    S.store.touch_attacker(aid)
    return attacker_view(S.store, a)


@app.get("/api/attackers/{aid}/history")
async def history(aid: str):
    if not S.store.attacker(aid):
        raise HTTPException(404, "attacker not found")
    return {"turns": S.store.turns_for(aid)}


@app.post("/api/chat")
async def chat(body: ChatBody):
    a = S.store.attacker(body.attacker_id)
    if not a:
        raise HTTPException(404, "attacker not found; join again")
    r = S.rounds.ensure_round()
    S.store.touch_attacker(a["id"])
    return await S.agent.handle_message(a, body.message.strip(), r["number"])


@app.get("/api/bounties")
async def get_bounties():
    return {"bounties": bounties()}


# ---------------------------------------------------------------- war room --
@app.get("/api/state")
async def state():
    return S.rounds.state()


@app.get("/api/feed")
async def feed(limit: int = 50):
    return {"events": S.store.events(min(limit, 200))}


@app.get("/api/leaderboard")
async def leaderboard():
    rows = []
    for i, a in enumerate(S.store.attackers()[:50]):
        rows.append({"rank": i + 1, "attacker_id": a["id"], "nickname": a["nickname"], "score": a["score"], "breaches": a["breaches"],
                     "attacks": a["attacks"], "categories": a.get("earned", []), "synthetic": bool(a.get("synthetic"))})
    return {"rows": rows}


@app.get("/api/rounds")
async def rounds():
    return {"rounds": S.store.rounds()}


def _gv_summary(gv: dict) -> dict:
    return {"version": gv["version"], "created_at": gv["created_at"], "status": gv["status"], "parent_version": gv.get("parent_version"),
            "changelog": gv["changelog"], "catch_rate": gv.get("catch_rate"), "benign_allow_rate": gv.get("benign_allow_rate"),
            "n_rules": len(gv["rules"]), "n_examples": len(gv["examples"]), "has_prefilter": bool((gv.get("prefilter_code") or "").strip()),
            "active": gv["version"] == S.store.active_gate_version()}


@app.get("/api/gate/versions")
async def gate_versions():
    return {"versions": [_gv_summary(g) for g in S.store.gate_versions()]}


@app.get("/api/gate/versions/{v}")
async def gate_version(v: int):
    gv = S.store.gate_version(v)
    if not gv:
        raise HTTPException(404, "no such version")
    parent = S.store.gate_version(gv["parent_version"]) if gv.get("parent_version") else None
    diff = {"added_rules": [r for r in gv["rules"] if not parent or r not in parent["rules"]],
            "removed_rules": [r for r in (parent["rules"] if parent else []) if r not in gv["rules"]],
            "added_examples": len(gv["examples"]) - (len(parent["examples"]) if parent else 0)}
    return {**_gv_summary(gv), "rules": gv["rules"], "criteria": gv["criteria"], "examples": gv["examples"], "prefilter_code": gv.get("prefilter_code") or "",
            "eval": gv.get("eval"), "diff_from_parent": diff}


@app.get("/api/breaches")
async def breaches(limit: int = 100):
    return {"breaches": S.store.breaches(min(limit, 500))}


@app.get("/api/traces")
async def traces(limit: int = 100, attack_id: str | None = None):
    return {"traces": S.store.traces(min(limit, 500), attack_id or None)}


@app.get("/api/defender/runs")
async def defender_runs():
    return {"runs": S.store.runs(limit=20)}


@app.get("/api/providers")
async def providers():
    return S.rounds.state()["providers"] | {"gate_errors": S.gate.errors[-5:]}


# ------------------------------------------------------------------- admin --
@app.post("/api/admin/round/start")
async def round_start():
    return S.rounds.start_round()


@app.post("/api/admin/round/end")
async def round_end():
    r = await S.rounds.end_round()
    if not r:
        raise HTTPException(409, "no live round")
    return r


@app.post("/api/admin/defender/run")
async def defender_run():
    r = S.store.current_round() or S.store.last_round()
    run = await S.rounds.run_defender(r["number"] if r else 0)
    return run


@app.post("/api/admin/settings")
async def settings(body: SettingsBody):
    st = CONFIG.settings
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(st, k, v)
    return st.to_dict()


@app.post("/api/admin/simulate")
async def simulate(body: SimulateBody):
    S.rounds.ensure_round()
    await S.sim.start(body.count, body.seconds)
    return {"started": True, "count": body.count, "seconds": body.seconds}


@app.post("/api/admin/simulate/stop")
async def simulate_stop():
    await S.sim.stop()
    return {"stopped": True}


@app.post("/api/admin/reset")
async def reset():
    await S.sim.stop()
    S.store.reset()
    S.defender.ensure_benign_seed()
    await HUB.broadcast({"type": "state", "state": S.rounds.state()})
    return {"ok": True}


@app.post("/api/admin/gate/rollback")
async def rollback(body: RollbackBody):
    gv = S.store.gate_version(body.version)
    if not gv or gv["status"] not in ("seed", "shipped"):
        raise HTTPException(404, "no shipped version with that number")
    S.store.set_active_gate_version(body.version)
    r = S.store.current_round()
    HUB.emit(S.store.add_event("gate_shipped", f"Rolled back to gate v{body.version}", r["number"] if r else 0, data={"version": body.version, "rollback": True}))
    return _gv_summary(gv)


# ---------------------------------------------------------------- websocket --
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await HUB.connect(websocket)
    try:
        await websocket.send_json({"type": "state", "state": S.rounds.state()})
        for ev in reversed(S.store.events(30)):
            await websocket.send_json(ev)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        HUB.disconnect(websocket)
    except Exception:  # noqa: BLE001
        HUB.disconnect(websocket)


# ------------------------------------------------------------------ static --
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    async def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
else:
    @app.get("/")
    async def root():
        return JSONResponse({"siege": "backend up; build the frontend (cd frontend && npm run build) to serve the UI here", "docs": "/docs"})
