# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo>=0.24.2"]
# ///
"""A bounded, opt-in GPU render preview for SIEGE's public Blender scene.

Run: marimo run notebooks/siege_render_studio.py
Requires an installed Blender 5.2+ executable with Cycles CUDA/OptiX support.
Opening this notebook neither downloads code nor starts a render.
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="SIEGE Render Studio")


@app.cell
def _():
    import hashlib
    import json
    import shutil
    import subprocess
    import tempfile
    import time
    import urllib.request
    from pathlib import Path

    import marimo as mo

    return Path, hashlib, json, mo, shutil, subprocess, tempfile, time, urllib


@app.cell
def _(mo):
    mo.md("""
    # SIEGE Render Studio

    **Use an attached NVIDIA GPU to render a sharper action-boundary visual.**
    This companion leaves the live SIEGE app and its attack-map notebook untouched.

    The preview is fixed at **one frame · 960 × 540 · 16 Cycles samples**.
    It starts only when you press **Render one GPU frame**. The render has a
    **180-second timeout** and never falls back to CPU. No cloud machine is
    provisioned, no credits are purchased, and no animation batch is launched.

    Attach your GPU environment first. It must already have **Blender 5.2 or
    newer**, its matching NVIDIA driver, and a working Cycles CUDA or OptiX
    device. GPU availability is verified from Blender itself. If the environment
    only has Python/torch, install Blender in that environment before continuing.
    """)
    return


@app.cell
def _(Path, mo, shutil):
    _discovered = shutil.which("blender") or ""
    if not _discovered and Path("/Applications/Blender.app/Contents/MacOS/Blender").is_file():
        _discovered = "/Applications/Blender.app/Contents/MacOS/Blender"
    blender_path = mo.ui.text(value=_discovered, label="Blender executable", full_width=True)
    prepare_button = mo.ui.run_button(label="Prepare pinned public scene")
    render_button = mo.ui.run_button(label="Render one GPU frame")
    mo.vstack([
        blender_path,
        mo.md("The first button downloads only the public scene generator below, verifies its SHA-256, and saves it to a temporary directory. The second button checks the GPU and renders the single preview frame."),
        mo.hstack([prepare_button, render_button], justify="start", gap=1),
    ])
    return blender_path, prepare_button, render_button


@app.cell
def _(Path, hashlib, mo, prepare_button, tempfile, urllib):
    mo.stop(not prepare_button.value, mo.md("**Ready when you are.** Prepare the scene to enable a render."))

    # Immutable source, not a branch tip. No external assets or add-ons are fetched.
    source_commit = "91b47c20ff2f505400bca3fa5629f8692a92993c"
    source_sha256 = "975a4c2b89e1952126fd62fb4a08db3708ae820bef968aea7371a5ed41a7f186"
    source_url = f"https://raw.githubusercontent.com/vnmoorthy/siege/{source_commit}/blender/siege_scene_astra.py"
    preparation_error = None
    studio_dir = None
    generator_path = None
    try:
        _request = urllib.request.Request(source_url, headers={"User-Agent": "SIEGE-Render-Studio/1.0"})
        with urllib.request.urlopen(_request, timeout=25) as _response:
            _source = _response.read(500_001)
        if len(_source) > 500_000:
            raise ValueError("The generator exceeded the expected size limit.")
        if hashlib.sha256(_source).hexdigest() != source_sha256:
            raise ValueError("Source integrity check failed; nothing was executed.")
        studio_dir = Path(tempfile.mkdtemp(prefix="siege-render-studio-"))
        generator_path = studio_dir / "siege_scene_astra.py"
        generator_path.write_bytes(_source)
    except Exception as _error:
        preparation_error = f"{type(_error).__name__}: {_error}"
    mo.stop(preparation_error is not None, mo.callout(mo.md(f"**Scene unavailable.** {preparation_error}\n\nNo render was started. Check that the pinned public source is reachable, then press Prepare again."), kind="warn"))
    mo.md(f"**Scene verified.** [View the pinned public generator]({source_url})  \nCommit: `{source_commit}`  \nSHA-256: `{source_sha256}`  \nTemporary output directory: `{studio_dir}`")
    return generator_path, studio_dir


@app.cell
def _(Path, blender_path, generator_path, json, mo, render_button, shutil, studio_dir, subprocess, time):
    mo.stop(not render_button.value, mo.md("**No render running.** One preview starts only after you press Render."))
    _entered = blender_path.value.strip()
    _executable = shutil.which(_entered) or (_entered if Path(_entered).is_file() else None)
    mo.stop(not _executable, mo.callout("Blender executable not found. This notebook does not install software or substitute CPU rendering. Set the installed Blender 5.2+ executable path and try again.", kind="warn"))

    # A separate short preflight reports real device names and exits before any
    # scene rendering when CUDA/OptiX is missing. The generator also enforces GPU.
    _probe = '''
import bpy, json
if bpy.app.version < (5, 2, 0):
    raise RuntimeError("Blender 5.2 or newer is required by this scene.")
prefs = bpy.context.preferences.addons["cycles"].preferences
found = []
for backend in ["OPTIX", "CUDA"]:
    try:
        prefs.compute_device_type = backend
        prefs.get_devices()
        found = [{"name": d.name, "type": d.type} for d in prefs.devices if d.type != "CPU"]
        if found:
            print("SIEGE_GPU_INFO " + json.dumps({"blender": bpy.app.version_string, "backend": backend, "devices": found}), flush=True)
            break
    except Exception:
        continue
if not found:
    raise RuntimeError("No Cycles CUDA/OptiX GPU detected. No CPU render will run.")
'''
    render_error = None
    gpu_details = None
    preview_path = None
    render_log = ""
    elapsed = None
    try:
        _preflight = subprocess.run(
            [_executable, "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr", _probe],
            capture_output=True, text=True, timeout=60, check=False,
        )
        _probe_log = _preflight.stdout + _preflight.stderr
        _info = next((_line.removeprefix("SIEGE_GPU_INFO ") for _line in _probe_log.splitlines() if _line.startswith("SIEGE_GPU_INFO ")), None)
        if _preflight.returncode != 0 or _info is None:
            raise RuntimeError("GPU preflight failed. " + _probe_log[-3500:])
        gpu_details = json.loads(_info)
        _out = studio_dir / "preview"
        _command = [
            _executable, "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(generator_path), "--", "--out", str(_out),
            "--res", "960", "540", "--start", "28", "--end", "28",
            "--samples", "16", "--engine", "CYCLES", "--device", "GPU",
        ]
        _started = time.perf_counter()
        _result = subprocess.run(_command, capture_output=True, text=True, timeout=180, check=False)
        elapsed = time.perf_counter() - _started
        render_log = (_result.stdout + _result.stderr)[-8000:]
        _image = _out / "frame_0028.png"
        if _result.returncode != 0 or not _image.is_file() or "ASTRA_CYCLES_GPU" not in render_log:
            raise RuntimeError("The GPU preview did not finish successfully. " + render_log[-3500:])
        preview_path = _image
    except subprocess.TimeoutExpired:
        render_error = "The bounded GPU check/render reached its timeout and its process was stopped. No automatic retry or CPU fallback was started."
    except Exception as _error:
        render_error = f"{type(_error).__name__}: {_error}"

    mo.stop(render_error is not None, mo.callout(mo.md(f"**Preview unavailable.**\n\n```text\n{render_error}\n```"), kind="warn"))
    mo.vstack([
        mo.md(f"**Rendered one GPU frame in {elapsed:.1f}s.**  \nBlender `{gpu_details['blender']}` · `{gpu_details['backend']}` · " + ", ".join(_gpu["name"] for _gpu in gpu_details["devices"]) + "  \nConceptual Blender artwork; this is not live attack activity."),
        mo.image(src=str(preview_path)),
        mo.download(preview_path.read_bytes(), filename="siege_gpu_preview.png", mimetype="image/png", label="Download preview PNG"),
        mo.accordion({"Render log": mo.md(f"```text\n{render_log}\n```")}),
    ])
    return


if __name__ == "__main__":
    app.run()
