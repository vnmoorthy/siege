"""Isolated execution for defender-written prefilter code: W&B Serverless Sandboxes, or a local subprocess."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import CONFIG

RUNNER = r'''
import json, sys, importlib.util
payload = json.load(open(sys.argv[1]))
spec = importlib.util.spec_from_file_location("prefilter", sys.argv[2])
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    fn = getattr(mod, "check")
except Exception as e:
    print(json.dumps({"error": f"prefilter failed to load: {e!r}"})); sys.exit(0)
out = []
for item in payload["items"]:
    try:
        r = fn(item) or {}
        out.append({"hit": bool(r.get("hit")), "reason": str(r.get("reason", ""))[:200]})
    except Exception as e:
        out.append({"hit": False, "reason": f"error: {e!r}"})
print(json.dumps({"results": out}))
'''


class LocalSandbox:
    provider = "local"
    live = True

    def run_prefilter(self, code: str, items: list[dict], timeout: float = 20.0) -> dict:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "prefilter.py").write_text(code)
            (p / "runner.py").write_text(RUNNER)
            (p / "input.json").write_text(json.dumps({"items": items}))
            try:
                proc = subprocess.run([sys.executable, "-I", "-S", str(p / "runner.py"), str(p / "input.json"), str(p / "prefilter.py")],
                                      capture_output=True, text=True, timeout=timeout, cwd=d, env={"PATH": os.environ.get("PATH", "")})
            except subprocess.TimeoutExpired:
                return {"error": "prefilter timed out"}
            return _parse(proc.stdout, proc.stderr)


class WandbSandbox:
    """W&B Serverless Sandbox (CoreWeave). The client library needs the main thread, so each job runs in a
    short-lived subprocess (see sandbox_job.py) and never blocks the API event loop."""
    provider = "wandb"

    def __init__(self):
        os.environ.setdefault("WANDB_API_KEY", CONFIG.wandb_key)
        import importlib.util

        if importlib.util.find_spec("cwsandbox") is None and importlib.util.find_spec("wandb.sandbox") is None:
            raise RuntimeError("wandb[sandbox] is not installed")
        self.live = True
        self.last_error: str | None = None
        self.last_sandbox_id: str | None = None

    def run_prefilter(self, code: str, items: list[dict], timeout: float = 60.0) -> dict:
        job = json.dumps({"code": code, "items": items, "timeout": timeout})
        env = dict(os.environ, WANDB_API_KEY=CONFIG.wandb_key, WANDB_SILENT="true", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        try:
            proc = subprocess.run([sys.executable, "-m", "app.sandbox_job"], input=job, capture_output=True, text=True, timeout=timeout + 120,
                                  cwd=str(Path(__file__).resolve().parents[1]), env=env)
        except subprocess.TimeoutExpired:
            self.last_error = "sandbox job timed out"
            return LocalSandbox().run_prefilter(code, items) | {"sandbox_fallback": "timeout"}
        line = (proc.stdout or "").strip().splitlines()[-1] if (proc.stdout or "").strip() else ""
        try:
            out = json.loads(line)
            self.last_sandbox_id = out.get("sandbox_id")
            out["provider"] = "wandb"
            return out
        except json.JSONDecodeError:
            self.last_error = (proc.stderr or "")[-400:]
            print(f"[sandbox] wandb job failed, falling back to local: {self.last_error[-200:]}")
            return LocalSandbox().run_prefilter(code, items) | {"sandbox_fallback": "error"}


def _op(ref):
    """OperationRef objects resolve with .result(); plain values pass through."""
    return ref.result() if hasattr(ref, "result") else ref


def _text(v) -> str:
    if callable(v):
        v = v()
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    return str(v or "")


def _parse(stdout: str, stderr: str) -> dict:
    line = (stdout or "").strip().splitlines()[-1] if (stdout or "").strip() else ""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"error": f"prefilter produced no JSON. stderr: {(stderr or '')[-300:]}"}


_sb = None


def sandbox():
    global _sb
    if _sb is None:
        if CONFIG.mode == "live" and CONFIG.wandb_key:
            try:
                _sb = WandbSandbox()
            except Exception as e:  # noqa: BLE001
                print(f"[sandbox] wandb sandbox unavailable, using local subprocess: {e}")
                _sb = LocalSandbox()
        else:
            _sb = LocalSandbox()
    return _sb


def local() -> LocalSandbox:
    return LocalSandbox()


def status() -> dict:
    s = sandbox()
    return {"provider": s.provider, "live": bool(s.live)}
