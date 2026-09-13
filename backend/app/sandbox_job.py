"""Runs one prefilter job inside a W&B Serverless Sandbox. Executed as a subprocess so the sandbox client
owns the main thread (it installs signal handlers). stdin: {"code":..., "items":[...], "timeout":...}; stdout: result JSON."""
from __future__ import annotations

import json
import os
import sys


def main() -> None:
    job = json.load(sys.stdin)
    from wandb.sandbox import Sandbox

    from .sandbox import RUNNER, _op, _parse, _text

    timeout = float(job.get("timeout", 60))
    with Sandbox.run(max_lifetime_seconds=int(timeout) + 90) as sb:
        _op(sb.write_file("/tmp/prefilter.py", job["code"].encode()))
        _op(sb.write_file("/tmp/runner.py", RUNNER.encode()))
        _op(sb.write_file("/tmp/input.json", json.dumps({"items": job["items"]}).encode()))
        proc = sb.exec(["python3", "/tmp/runner.py", "/tmp/input.json", "/tmp/prefilter.py"], timeout_seconds=timeout)
        res = proc.result(timeout=timeout + 15)
        out = _parse(_text(getattr(res, "stdout", "")), _text(getattr(res, "stderr", "")))
        out["sandbox_id"] = getattr(sb, "sandbox_id", None)
    print(json.dumps(out))


if __name__ == "__main__":
    os.environ.setdefault("WANDB_SILENT", "true")
    main()
