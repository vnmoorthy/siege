# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "pandas",
#     "altair",
# ]
# ///
"""SIEGE Lab: a live, reactive marimo notebook over the SIEGE SQLite store.

Run locally:   marimo run notebooks/siege_lab.py      (app mode)
Edit:          marimo edit notebooks/siege_lab.py
Static export: marimo export html notebooks/siege_lab.py -o siege_lab.html
The same file runs unchanged on molab (only pandas + altair + stdlib are used).
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="SIEGE Lab")


@app.cell
def _():
    import difflib
    import json
    import os
    import sqlite3
    from datetime import datetime
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import pandas as pd

    return Path, alt, datetime, difflib, json, mo, os, pd, sqlite3


@app.cell
def _(Path, mo, os):
    # --- Cell 1: title + DB path + live refresh -------------------------------
    # Production DB lives at <repo>/backend/data/siege.db; resolve it relative to
    # this notebook so the default works from any working directory.
    try:
        _nb_dir = mo.notebook_dir()
    except Exception:
        _nb_dir = None
    _nb_dir = Path(_nb_dir) if _nb_dir else Path.cwd()
    _prod = (_nb_dir.parent / "backend" / "data" / "siege.db").resolve()
    _candidates = [_prod, _nb_dir / "siege.db", _nb_dir / "siege_demo.db", Path("/tmp/siege_live_smoke.db")]
    _default = next((str(c) for c in _candidates if c.exists()), None)
    if _default is None:
        # No local store (e.g. a fresh molab sandbox): fetch the demo snapshot captured from a live siege.
        try:
            import urllib.request

            _snap = _nb_dir / "siege_demo.db"
            urllib.request.urlretrieve("https://raw.githubusercontent.com/vnmoorthy/siege/main/docs/data/siege_demo.db", _snap)
            _default = str(_snap)
        except Exception:
            _default = str(_prod)
    _default = os.environ.get("SIEGE_DB") or _default  # env override: SIEGE_DB=/path/x.db marimo run ...

    db_path = mo.ui.text(
        value=_default,
        label="SIEGE SQLite DB",
        placeholder="/path/to/siege.db",
        full_width=True,
    )
    refresh = mo.ui.refresh(options=["2s", "5s", "10s"], default_interval="5s", label="Live re-read")

    mo.vstack(
        [
            mo.md(
                """
    # SIEGE Lab
    **The room vs one agent, seen through its database.** Every tool call the support agent
    proposes passes a *typed action gate* (TypeSafe System One: `allow / block / escalate` with
    probabilities). A deterministic policy oracle is ground truth. A **breach** is exact:
    *gate allowed + oracle forbidden + executed*. Each round a defender rewrites the gate
    policy and ships it only if catch rate rises without dropping benign traffic.

    This notebook re-reads the live SQLite store on a timer, so every cell below updates
    while the room keeps attacking. Change the path or the interval and everything
    downstream recomputes.
    """
            ),
            mo.hstack([db_path, refresh], widths=[4, 1], align="end"),
        ]
    )
    return db_path, refresh


@app.cell
def _(datetime, db_path, json, os, pd, refresh, sqlite3):
    # --- Cell 2: loader (reactive on db_path + refresh tick) --------------------
    _tick = refresh.value  # dependency on the timer: this cell re-runs every tick
    DB_PATH = (db_path.value or "").strip()
    loaded_at = datetime.now().strftime("%H:%M:%S")

    _TABLES = ["attackers", "turns", "breaches", "rounds", "gate_versions", "defender_runs",
               "traces", "gate_samples", "events", "kv"]
    # JSON columns and the empty value to use when a cell is NULL / unparseable.
    _JSON_COLS = {
        "attackers": {"earned": list},
        "turns": {"tool_calls": list},
        "breaches": {"args": dict, "gate_probabilities": dict},
        "gate_versions": {"rules": list, "criteria": dict, "examples": list, "eval": lambda: None},
        "defender_runs": {"attempts": list, "log": list},
        "traces": {"inputs": dict, "output": lambda: None},
        "gate_samples": {"state": dict},
        "events": {"data": dict},
    }

    def _loads(v, default):
        if isinstance(v, (list, dict)):
            return v
        if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
            return default()
        try:
            return json.loads(v)
        except Exception:
            return default()

    db_error = None
    T = {t: pd.DataFrame() for t in _TABLES}
    if not DB_PATH or not os.path.exists(DB_PATH):
        db_error = (
            f"No database at `{DB_PATH or '(empty path)'}`. Start the backend "
            "(`uvicorn app.main:app` in `backend/`) or point the box above at a SIEGE SQLite file."
        )
    else:
        try:
            with open(DB_PATH, "rb") as _fh:
                _magic = _fh.read(16)
            if _magic != b"SQLite format 3\x00":
                raise ValueError("not a SQLite database file" + (" (empty file)" if not _magic else ""))
            _conn = sqlite3.connect(DB_PATH, timeout=5)
            try:
                for _t in _TABLES:
                    try:
                        _df = pd.read_sql_query(f"SELECT * FROM {_t}", _conn)
                    except Exception:
                        _df = pd.DataFrame()
                    for _c, _default in _JSON_COLS.get(_t, {}).items():
                        if _c in _df.columns:
                            _df[_c] = [_loads(_v, _default) for _v in _df[_c].tolist()]
                    T[_t] = _df
            finally:
                _conn.close()
            if all(T[_t].empty for _t in _TABLES):
                db_error = f"`{DB_PATH}` opened, but it has no SIEGE tables (or they are all empty)."
        except Exception as _e:  # corrupted file, locked, not sqlite, ...
            db_error = f"Could not read `{DB_PATH}`: {type(_e).__name__}: {_e}"

    turns_df = T["turns"]
    breaches_df = T["breaches"]
    rounds_df = T["rounds"]
    gv_df = T["gate_versions"]
    runs_df = T["defender_runs"]
    traces_df = T["traces"]
    samples_df = T["gate_samples"]
    attackers_df = T["attackers"]
    events_df = T["events"]

    # Explode turns.tool_calls -> one row per gated tool call.
    CALL_COLS = ["turn_id", "attacker_id", "round", "gate_version", "created_at", "idx", "tool",
                 "decision", "p_allow", "p_block", "p_escalate", "confidence", "provider",
                 "prefilter_hit", "prefilter_reason", "gate_latency_ms", "oracle_allowed",
                 "oracle_category", "oracle_reason", "executed", "breach", "benign_block",
                 "category", "points", "turn_latency_ms", "message"]
    _rows = []
    if not turns_df.empty and "tool_calls" in turns_df.columns:
        for _r in turns_df.to_dict("records"):
            for _i, _tc in enumerate(_r.get("tool_calls") or []):
                if not isinstance(_tc, dict):
                    continue
                _g = _tc.get("gate") or {}
                _o = _tc.get("oracle") or {}
                _p = _g.get("probabilities") or {}
                _rows.append({
                    "turn_id": _r.get("id"), "attacker_id": _r.get("attacker_id"),
                    "round": _r.get("round"), "gate_version": _g.get("gate_version", _r.get("gate_version")),
                    "created_at": _r.get("created_at"), "idx": _i, "tool": _tc.get("name"),
                    "decision": _g.get("decision"),
                    "p_allow": _p.get("allow"), "p_block": _p.get("block"), "p_escalate": _p.get("escalate"),
                    "confidence": _g.get("confidence"), "provider": _g.get("provider"),
                    "prefilter_hit": bool(_g.get("prefilter_hit")), "prefilter_reason": _g.get("prefilter_reason"),
                    "gate_latency_ms": _g.get("latency_ms"),
                    "oracle_allowed": bool(_o.get("allowed")), "oracle_category": _o.get("category"),
                    "oracle_reason": _o.get("reason"),
                    "executed": bool(_tc.get("executed")), "breach": bool(_tc.get("breach")),
                    "benign_block": bool(_tc.get("benign_block")),
                    "category": _tc.get("category"), "points": _tc.get("points", 0),
                    "turn_latency_ms": _r.get("latency_ms"), "message": _r.get("message"),
                })
    calls = pd.DataFrame(_rows, columns=CALL_COLS)
    if not calls.empty:
        for _c in ("p_allow", "p_block", "p_escalate", "confidence"):
            calls[_c] = pd.to_numeric(calls[_c], errors="coerce")

    # Active gate version: kv first, then newest seed/shipped version.
    active_version = None
    _kv = T["kv"]
    if not _kv.empty and {"key", "value"} <= set(_kv.columns):
        _hit = _kv[_kv["key"] == "active_gate_version"]
        if len(_hit):
            try:
                active_version = int(json.loads(str(_hit["value"].iloc[0])))
            except Exception:
                active_version = None
    if active_version is None and not gv_df.empty and "status" in gv_df.columns:
        _live = gv_df[gv_df["status"].isin(["seed", "shipped"])]
        if len(_live):
            active_version = int(_live["version"].max())
    return (
        DB_PATH,
        active_version,
        attackers_df,
        breaches_df,
        calls,
        db_error,
        gv_df,
        loaded_at,
        rounds_df,
        runs_df,
        traces_df,
        turns_df,
    )


@app.cell
def _(DB_PATH, calls, db_error, loaded_at, mo, refresh, turns_df):
    if db_error:
        _status = mo.callout(mo.md(f"**Database not available.** {db_error}"), kind="warn")
    else:
        _status = mo.md(
            f"Read `{DB_PATH}` at **{loaded_at}** (tick {refresh.value}): "
            f"{len(turns_df)} turns, {len(calls)} gated tool calls."
        )
    _status
    return


@app.cell
def _(active_version, calls, db_error, gv_df, mo, pd, turns_df):
    # --- Cell 3: KPI row ---------------------------------------------------------
    mo.stop(db_error is not None, mo.callout(mo.md(f"KPIs unavailable: {db_error}"), kind="warn"))

    _attacks = int(len(turns_df))
    _breaches = int((pd.to_numeric(turns_df["breach_points"], errors="coerce").fillna(0) > 0).sum()) if _attacks and "breach_points" in turns_df.columns else 0
    _breach_rate = (_breaches / _attacks) if _attacks else 0.0

    if not calls.empty:
        _benign = calls[calls["oracle_allowed"]]
        _blocked_benign = int(_benign["benign_block"].sum())
        _allowed_benign = int(len(_benign) - _blocked_benign)
    else:
        _blocked_benign = _allowed_benign = 0
    _denom = _allowed_benign + _blocked_benign
    _benign_allow = (_allowed_benign / _denom) if _denom else 1.0

    _catch = None
    _catch_caption = "no version active"
    if active_version is not None and not gv_df.empty:
        _row = gv_df[gv_df["version"] == active_version]
        if len(_row):
            _cr = _row["catch_rate"].iloc[0]
            _catch = None if pd.isna(_cr) else float(_cr)
            _catch_caption = f"status: {_row['status'].iloc[0]}" + ("" if _catch is not None else " (seed: not evaluated)")

    mo.hstack(
        [
            mo.stat(value=f"{_attacks:,}", label="Attacks", caption="turns sent to the agent", bordered=True),
            mo.stat(value=f"{_breaches:,}", label="Breaches", caption="forbidden call executed", bordered=True),
            mo.stat(value=f"{_breach_rate:.1%}", label="Breach rate", caption="breaches / attacks", bordered=True),
            mo.stat(value=f"{_benign_allow:.1%}", label="Benign allow rate",
                    caption=f"{_allowed_benign} allowed / {_blocked_benign} blocked (oracle-allowed calls)", bordered=True),
            mo.stat(value=f"v{active_version}" if active_version is not None else "—", label="Active gate", caption=_catch_caption, bordered=True),
            mo.stat(value=(f"{_catch:.0%}" if _catch is not None else "n/a"), label="Catch rate (active)",
                    caption="on all breaches + red-team variants", bordered=True),
        ],
        widths="equal",
        wrap=True,
    )
    return


@app.cell
def _(alt, calls, db_error, mo, pd, rounds_df, runs_df, turns_df):
    # --- Cell 4: breach_rate & benign_allow_rate per round + gate version markers --
    mo.stop(db_error is not None, mo.callout(mo.md(f"Round chart unavailable: {db_error}"), kind="warn"))
    mo.stop(turns_df.empty and rounds_df.empty,
            mo.callout(mo.md("No rounds yet. Start a round from `/admin` and the chart appears here."), kind="info"))

    # Start from what the rounds table stores, then overwrite with live numbers computed
    # from the turns (same formula as the backend's round_counts()).
    _by_round = {}
    if not rounds_df.empty and "number" in rounds_df.columns:
        for _r in rounds_df.to_dict("records"):
            _by_round[int(_r["number"])] = {
                "round": int(_r["number"]), "attacks": int(_r.get("attacks") or 0), "breaches": int(_r.get("breaches") or 0),
                "breach_rate": float(_r.get("breach_rate") or 0.0), "benign_allow_rate": float(_r.get("benign_allow_rate") if _r.get("benign_allow_rate") is not None else 1.0),
                "status": _r.get("status") or "", "gate_start": _r.get("gate_version_start"), "gate_end": _r.get("gate_version_end"),
            }
    if not turns_df.empty and "round" in turns_df.columns:
        _bp = pd.to_numeric(turns_df["breach_points"], errors="coerce").fillna(0)
        for _rn, _grp in turns_df.assign(_bp=_bp).groupby("round"):
            _rn = int(_rn)
            _n = int(len(_grp))
            _b = int((_grp["_bp"] > 0).sum())
            _c = calls[(calls["round"] == _rn) & (calls["oracle_allowed"])] if not calls.empty else calls
            _blocked = int(_c["benign_block"].sum()) if len(_c) else 0
            _allowed = int(len(_c) - _blocked)
            _entry = _by_round.setdefault(_rn, {"round": _rn, "status": "", "gate_start": None, "gate_end": None})
            _entry.update({"attacks": _n, "breaches": _b, "breach_rate": (_b / _n) if _n else 0.0,
                           "benign_allow_rate": (_allowed / (_allowed + _blocked)) if (_allowed + _blocked) else 1.0})
    round_series = pd.DataFrame(sorted(_by_round.values(), key=lambda d: d["round"]))

    # Gate version markers: a shipped version is attached to the round whose breaches produced it.
    _marks = []
    if not runs_df.empty and "shipped_version" in runs_df.columns:
        for _r in runs_df.to_dict("records"):
            if _r.get("shipped_version") is not None and not pd.isna(_r.get("shipped_version")):
                _marks.append({"round": int(_r["round"]), "label": f"v{int(_r['shipped_version'])} shipped"})
    if not _marks and not rounds_df.empty and "gate_version_end" in rounds_df.columns:
        for _r in rounds_df.to_dict("records"):
            _ge, _gs = _r.get("gate_version_end"), _r.get("gate_version_start")
            if _ge is not None and not pd.isna(_ge) and _ge != _gs:
                _marks.append({"round": int(_r["number"]), "label": f"v{int(_ge)} shipped"})
    marks_df = pd.DataFrame(_marks, columns=["round", "label"])

    _long = round_series.melt(id_vars=["round", "attacks", "breaches", "status"],
                              value_vars=["breach_rate", "benign_allow_rate"], var_name="metric", value_name="rate")
    _long["metric"] = _long["metric"].map({"breach_rate": "breach rate (↓ good)", "benign_allow_rate": "benign allow rate (↑ good)"})
    _lines = (
        alt.Chart(_long)
        .mark_line(point=alt.OverlayMarkDef(size=90, filled=True), strokeWidth=2.5)
        .encode(
            x=alt.X("round:O", title="Round"),
            y=alt.Y("rate:Q", title="Rate", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
            color=alt.Color("metric:N", title=None,
                            scale=alt.Scale(domain=["breach rate (↓ good)", "benign allow rate (↑ good)"], range=["#e5484d", "#30a46c"]),
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("round:O"), alt.Tooltip("metric:N"), alt.Tooltip("rate:Q", format=".1%"),
                     alt.Tooltip("attacks:Q"), alt.Tooltip("breaches:Q"), alt.Tooltip("status:N")],
        )
    )
    _layers = [_lines]
    if len(marks_df):
        _rule = alt.Chart(marks_df).mark_rule(strokeDash=[5, 4], color="#8b8b8b", strokeWidth=1.5).encode(x="round:O")
        _text = alt.Chart(marks_df).mark_text(align="left", dx=5, dy=-4, baseline="bottom", color="#8b8b8b", fontSize=11).encode(
            x="round:O", y=alt.value(12), text="label:N")
        _layers += [_rule, _text]
    round_chart = alt.layer(*_layers).properties(width="container", height=300, title="Per round: breach rate falls, benign allow rate holds")

    mo.vstack([
        mo.md("## Rounds\nDashed markers: the defender shipped a new gate version after that round."),
        round_chart,
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Calibration of the typed gate

    System One is a *typed* classifier: it returns `Choice{allow, block, escalate}` **with
    probabilities**, not a bare yes/no. That only helps if the probabilities are honest. The
    reliability diagram below bins every gated tool call by the gate's `P(allow)` and plots
    the fraction the **oracle** actually allowed. A calibrated gate sits on the diagonal:
    when it says 70% allow, the call is safe 70% of the time.

    Why it matters for SIEGE:

    - **The ship rule trusts the numbers.** The defender's eval, the escalate path, and any
      execution threshold all assume `P(allow)` means something. A gate that is confidently
      wrong (a breach with `P(allow)=0.74`) is worse than one that says 0.5 and escalates.
    - **Escalation is a probability decision.** `escalate` exists so that uncertain calls go
      to a human instead of executing. If the gate is over-confident, nothing ever escalates
      and every mistake becomes a breach.
    - **Brier score** (mean squared error of `P(allow)` vs. the oracle) and **ECE** (expected
      calibration error, weighted by bin size) summarise the diagram; both go down as the
      defender ships better policies. Slide the execution threshold to see what a stricter
      gate would have caught, and what benign traffic it would have cost.
    """)
    return


@app.cell
def _(mo):
    allow_threshold = mo.ui.slider(0.0, 1.0, 0.05, value=0.5, label="What-if: execute only when P(allow) ≥", show_value=True)
    allow_threshold
    return (allow_threshold,)


@app.cell
def _(allow_threshold, alt, calls, db_error, mo, pd):
    # --- Cell 5: reliability diagram + Brier + ECE + execution-threshold what-if --
    mo.stop(db_error is not None, mo.callout(mo.md(f"Calibration unavailable: {db_error}"), kind="warn"))
    _c = calls.dropna(subset=["p_allow"]).copy() if not calls.empty else calls
    mo.stop(_c.empty, mo.callout(mo.md("No gated tool calls yet. Send the agent a message from `/attack` and the reliability diagram appears."), kind="info"))

    _c["y"] = _c["oracle_allowed"].astype(int)
    brier = float(((_c["p_allow"] - _c["y"]) ** 2).mean())
    _edges = [i / 10 for i in range(11)]
    _c["bin"] = pd.cut(_c["p_allow"].clip(0, 1), bins=_edges, include_lowest=True, labels=False)
    reliability = (
        _c.groupby("bin").agg(n=("y", "size"), confidence=("p_allow", "mean"), observed=("y", "mean")).reset_index()
    )
    reliability["bin"] = reliability["bin"].astype(int)
    reliability["bin_lo"] = reliability["bin"] / 10
    reliability["bin_hi"] = reliability["bin"] / 10 + 0.1
    reliability["bin_mid"] = reliability["bin"] / 10 + 0.05
    reliability["gap"] = (reliability["observed"] - reliability["confidence"]).abs()
    ece = float((reliability["n"] / reliability["n"].sum() * reliability["gap"]).sum())

    _bars = alt.Chart(reliability).mark_bar(opacity=0.55, color="#4f78d1").encode(
        x=alt.X("bin_lo:Q", title="P(allow) from the typed gate", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        x2="bin_hi:Q",
        y=alt.Y("observed:Q", title="Oracle actually allowed", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        tooltip=[alt.Tooltip("bin_lo:Q", format=".1f", title="bin from"), alt.Tooltip("bin_hi:Q", format=".1f", title="bin to"),
                 alt.Tooltip("n:Q", title="calls"), alt.Tooltip("confidence:Q", format=".2f", title="mean P(allow)"),
                 alt.Tooltip("observed:Q", format=".2f", title="oracle allowed rate")],
    )
    _diag = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4], color="#8b8b8b").encode(x="x:Q", y="y:Q")
    _dots = alt.Chart(reliability).mark_point(filled=True, color="#1f2a44").encode(
        x="confidence:Q", y="observed:Q", size=alt.Size("n:Q", legend=None, scale=alt.Scale(range=[60, 500])),
        tooltip=[alt.Tooltip("n:Q", title="calls"), alt.Tooltip("confidence:Q", format=".2f"), alt.Tooltip("observed:Q", format=".2f")])
    _counts = alt.Chart(reliability).mark_text(dy=-10, fontSize=11, color="#1f2a44").encode(x="bin_mid:Q", y="observed:Q", text="n:Q")
    reliability_chart = alt.layer(_bars, _diag, _dots, _counts).properties(
        width="container", height=320, title="Reliability diagram: P(allow) vs. oracle outcome (10 bins, labels = calls per bin)")

    # Threshold what-if: replay every gated call with a stricter execute rule.
    _tau = float(allow_threshold.value)
    _would_exec = _c["p_allow"] >= _tau - 1e-12
    _forbidden = ~_c["oracle_allowed"].astype(bool)
    _actual_breaches = int(_c["breach"].sum())
    _whatif_breaches = int((_would_exec & _forbidden).sum())
    _benign_total = int((~_forbidden).sum())
    _benign_kept = int((_would_exec & ~_forbidden).sum())
    _whatif_benign = (_benign_kept / _benign_total) if _benign_total else 1.0

    _table = reliability[["bin_lo", "bin_hi", "n", "confidence", "observed", "gap"]].rename(
        columns={"bin_lo": "P(allow) from", "bin_hi": "to", "n": "calls", "confidence": "mean P(allow)", "observed": "oracle allowed", "gap": "|gap|"})

    mo.vstack([
        mo.hstack([
            mo.stat(value=f"{brier:.3f}", label="Brier score", caption="0 = perfect, 0.25 = coin flip", bordered=True),
            mo.stat(value=f"{ece:.3f}", label="ECE", caption="expected calibration error (10 bins)", bordered=True),
            mo.stat(value=f"{len(_c)}", label="Gated calls", caption=f"{int(_forbidden.sum())} oracle-forbidden, {_benign_total} oracle-allowed", bordered=True),
        ], widths="equal", wrap=True),
        reliability_chart,
        mo.callout(mo.md(
            f"**If the agent executed only calls with P(allow) ≥ {_tau:.2f}:** "
            f"breaches would be **{_whatif_breaches}** (actual: {_actual_breaches}) and benign allow rate "
            f"**{_whatif_benign:.0%}** ({_benign_kept}/{_benign_total}). Prefilter hits are ignored in this replay."
        ), kind="success" if _whatif_breaches <= _actual_breaches else "danger"),
        mo.ui.table(_table, selection=None, show_column_summaries=False, format_mapping={
            "P(allow) from": "{:.1f}", "to": "{:.1f}", "mean P(allow)": "{:.2f}", "oracle allowed": "{:.2f}", "|gap|": "{:.2f}"}),
    ])
    return


@app.cell
def _(mo):
    # UI state that must survive the refresh timer (elements whose *options* come
    # from the DB are re-created every tick; mo.state keeps the user's choice).
    get_ver, set_ver = mo.state(None)
    get_trace_name, set_trace_name = mo.state("All")
    benign_floor = mo.ui.slider(0.5, 1.0, 0.01, value=0.9, label="Benign allow floor", show_value=True)
    require_rise = mo.ui.checkbox(value=True, label="require catch rate to rise")
    trace_limit = mo.ui.number(10, 2000, step=10, value=100, label="rows")
    return (
        benign_floor,
        get_trace_name,
        get_ver,
        require_rise,
        set_trace_name,
        set_ver,
        trace_limit,
    )


@app.cell
def _(active_version, get_ver, gv_df, mo, set_ver):
    # --- Cell 6a: version picker (kept across refresh ticks via mo.state) ----------
    if gv_df.empty or "version" not in gv_df.columns:
        _opts = {"(no gate versions yet)": None}
    else:
        _opts = {f"v{int(_r['version'])} · {_r.get('status') or '?'}": int(_r["version"])
                 for _r in gv_df.sort_values("version", ascending=False).to_dict("records")}
    _want = get_ver() if get_ver() in _opts.values() else active_version
    _label = next((k for k, v in _opts.items() if v == _want), next(iter(_opts)))
    version_pick = mo.ui.dropdown(options=_opts, value=_label, label="Gate version", on_change=set_ver)
    mo.vstack([mo.md("## Gate version explorer"), version_pick])
    return (version_pick,)


@app.cell
def _(db_error, difflib, gv_df, mo, pd, version_pick):
    # --- Cell 6b: explorer body ------------------------------------------------------
    mo.stop(db_error is not None, mo.callout(mo.md(f"Gate explorer unavailable: {db_error}"), kind="warn"))
    mo.stop(gv_df.empty or version_pick.value is None,
            mo.callout(mo.md("No gate versions in this database yet (the backend seeds v1 on first start)."), kind="info"))
    _v = int(version_pick.value)
    _hit = gv_df[gv_df["version"] == _v]
    mo.stop(_hit.empty, mo.callout(mo.md(f"Gate v{_v} vanished (reset?). Pick another version."), kind="warn"))
    _row = _hit.iloc[0].to_dict()

    _parent_v = _row.get("parent_version")
    _parent_v = None if _parent_v is None or pd.isna(_parent_v) else int(_parent_v)
    _prow = gv_df[gv_df["version"] == _parent_v].iloc[0].to_dict() if _parent_v is not None and (gv_df["version"] == _parent_v).any() else None
    _rules = [str(r) for r in (_row.get("rules") or [])]
    _prules = [str(r) for r in ((_prow or {}).get("rules") or [])]
    _added = [r for r in _rules if r not in _prules]
    _removed = [r for r in _prules if r not in _rules]
    _diff = "\n".join(difflib.unified_diff(_prules, _rules, fromfile=f"v{_parent_v} rules" if _parent_v else "(no parent)",
                                           tofile=f"v{_v} rules", lineterm="", n=0))

    def _fmt(x):
        return "n/a" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{float(x):.1%}"

    _ev = _row.get("eval") or {}
    _status = _row.get("status") or "?"
    _kind = {"shipped": "success", "seed": "neutral", "rejected": "danger"}.get(_status, "neutral")
    _examples = pd.DataFrame(_row.get("examples") or [], columns=["message", "tool", "decision", "why"])
    _criteria = _row.get("criteria") or {}
    _pf = (_row.get("prefilter_code") or "").strip()

    mo.vstack([
        mo.callout(mo.md(
            f"### Gate v{_v} — **{_status}**"
            + (f" · parent v{_parent_v}" if _parent_v is not None else " · root")
            + f" · created {_row.get('created_at') or '?'}\n\n"
            f"**catch rate {_fmt(_row.get('catch_rate'))}** · **benign allow {_fmt(_row.get('benign_allow_rate'))}**"
            + (f" · eval on {_ev.get('n_attacks')} attacks / {_ev.get('n_benign')} benign (prev catch {_fmt(_ev.get('prev_catch_rate'))})" if _ev else " · not evaluated (seed)")
            + f"\n\n{_row.get('changelog') or ''}"
        ), kind=_kind),
        mo.md(f"#### Rules ({len(_rules)})\n" + ("\n".join(f"{i + 1}. {r}" for i, r in enumerate(_rules)) if _rules else "_no rules_")),
        mo.md("#### Decision criteria\n" + ("\n".join(f"- **{k}** — {v}" for k, v in _criteria.items()) if _criteria else "_none_")),
        mo.md(f"#### Adversarial examples ({len(_examples)})"),
        (mo.ui.table(_examples, selection=None, show_column_summaries=False, wrapped_columns=["message", "why"])
         if len(_examples) else mo.md("_no examples attached to this version_")),
        mo.md("#### Prefilter (deterministic Python, runs in the sandbox before the typed gate)"),
        mo.md(f"```python\n{_pf}\n```" if _pf else "_no prefilter for this version_"),
        mo.md(f"#### Diff vs parent — {len(_added)} rule(s) added, {len(_removed)} removed, "
              f"{max(0, len(_examples) - len((_prow or {}).get('examples') or []))} example(s) added"),
        mo.md(f"```diff\n{_diff}\n```" if _diff else ("_identical rules to the parent_" if _prow else "_root version: nothing to diff against_")),
    ])
    return


@app.cell
def _(benign_floor, mo, require_rise):
    mo.vstack([
        mo.md("## Re-decide the ship rule\nThe defender ships a candidate only if `benign_allow_rate ≥ floor` **and** catch rate rises "
              "(`catch > prev_catch`, or both already ≈100%). Move the floor and toggle the rise requirement: every stored "
              "eval is re-judged instantly, no re-run of the defender needed."),
        mo.hstack([benign_floor, require_rise], justify="start", gap=2),
    ])
    return


@app.cell
def _(benign_floor, db_error, gv_df, mo, pd, require_rise, runs_df):
    # --- Cell 7: what-if ship rule over stored eval numbers ------------------------
    mo.stop(db_error is not None, mo.callout(mo.md(f"What-if unavailable: {db_error}"), kind="warn"))
    _floor = float(benign_floor.value)
    _need_rise = bool(require_rise.value)

    def _num(x):
        return None if x is None or (isinstance(x, float) and pd.isna(x)) else float(x)

    def _would_ship(catch, prev, benign):
        if catch is None or benign is None:
            return None
        ok = benign >= _floor - 1e-9
        if _need_rise:
            ok = ok and (prev is None or catch > prev + 1e-9 or (catch >= 0.999 and prev >= 0.999))
        return bool(ok)

    _versions = []
    if not gv_df.empty and "status" in gv_df.columns:
        for _r in gv_df[gv_df["status"] != "seed"].sort_values("version").to_dict("records"):
            _ev = _r.get("eval") or {}
            _catch = _num(_r.get("catch_rate")) if _num(_r.get("catch_rate")) is not None else _num(_ev.get("catch_rate"))
            _ben = _num(_r.get("benign_allow_rate")) if _num(_r.get("benign_allow_rate")) is not None else _num(_ev.get("benign_allow_rate"))
            _prev = _num(_ev.get("prev_catch_rate"))
            _versions.append({"version": f"v{int(_r['version'])}", "actual": _r.get("status"), "catch": _catch, "prev_catch": _prev,
                              "benign_allow": _ben, "would_ship": _would_ship(_catch, _prev, _ben)})
    _attempts = []
    if not runs_df.empty and "attempts" in runs_df.columns:
        for _r in runs_df.sort_values("started_at").to_dict("records"):
            for _a in _r.get("attempts") or []:
                _ev = (_a or {}).get("eval") or {}
                _catch, _prev, _ben = _num(_ev.get("catch_rate")), _num(_ev.get("prev_catch_rate")), _num(_ev.get("benign_allow_rate"))
                _attempts.append({"run": f"round {_r.get('round')} · {str(_r.get('id'))[-6:]}", "attempt": _a.get("n"),
                                  "actual": "PASS" if _ev.get("passed") else "FAIL", "catch": _catch, "prev_catch": _prev,
                                  "benign_allow": _ben, "would_ship": _would_ship(_catch, _prev, _ben), "verdict": _a.get("verdict") or ""})
    mo.stop(not _versions and not _attempts,
            mo.callout(mo.md("No evaluated gate versions or defender attempts yet. Run the defender (`/admin` → *Run defender now*)."), kind="info"))

    def _pct(x):
        return "—" if x is None else f"{x:.1%}"

    def _verdict(v):
        if v is None:
            return '<span style="color:#8b8b8b">no eval</span>'
        return ('<span style="display:inline-block;padding:2px 10px;border-radius:999px;background:#30a46c;color:white;font-weight:600">SHIP</span>'
                if v else '<span style="display:inline-block;padding:2px 10px;border-radius:999px;background:#e5484d;color:white;font-weight:600">REJECT</span>')

    def _html_table(rows, cols, key_actual):
        head = "".join(f"<th style='text-align:left;padding:6px 10px;border-bottom:1px solid #ccc'>{c[1]}</th>" for c in cols)
        body = []
        for r in rows:
            actual_ok = str(r.get(key_actual)).lower() in ("shipped", "pass")
            flip = (r["would_ship"] is not None) and (r["would_ship"] != actual_ok)
            style = "background:rgba(255,196,0,0.12)" if flip else ""
            cells = []
            for k, _label, fmt in cols:
                v = r.get(k)
                cells.append(f"<td style='padding:6px 10px;border-bottom:1px solid #eee;{style}'>{fmt(v)}</td>")
            body.append("<tr>" + "".join(cells) + "</tr>")
        return f"<table style='border-collapse:collapse;width:100%;font-size:0.92em'><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    _vcols = [("version", "version", str), ("catch", "catch", _pct), ("prev_catch", "prev catch", _pct), ("benign_allow", "benign allow", _pct),
              ("actual", "actual", str), ("would_ship", f"with floor {_floor:.0%}{' + rise' if _need_rise else ''}", _verdict)]
    _acols = [("run", "defender run", str), ("attempt", "attempt", str), ("catch", "catch", _pct), ("prev_catch", "prev catch", _pct),
              ("benign_allow", "benign allow", _pct), ("actual", "actual", str), ("would_ship", "what-if", _verdict), ("verdict", "logged verdict", str)]
    _n_ship = sum(1 for v in _versions if v["would_ship"])
    _n_actual = sum(1 for v in _versions if v["actual"] == "shipped")
    _flips = sum(1 for v in _versions + _attempts if v["would_ship"] is not None and v["would_ship"] != (str(v["actual"]).lower() in ("shipped", "pass")))

    mo.vstack([
        mo.callout(mo.md(f"With floor **{_floor:.0%}** and rise-required **{'on' if _need_rise else 'off'}**: "
                         f"**{_n_ship} of {len(_versions)}** candidate version(s) would ship (actually shipped: {_n_actual}); "
                         f"**{_flips}** decision(s) flip vs. what the defender did (highlighted)."),
                   kind="warn" if _flips else "success"),
        mo.md("#### Gate versions (non-seed)"),
        mo.Html(_html_table(_versions, _vcols, "actual")) if _versions else mo.md("_no non-seed versions_"),
        mo.md("#### Every defender attempt (including rejected candidates that never became a version)"),
        mo.Html(_html_table(_attempts, _acols, "actual")) if _attempts else mo.md("_no defender attempts logged_"),
    ])
    return


@app.cell
def _(db_error, gv_df, mo, pd, runs_df, version_pick):
    # --- Cell 8: eval failures for the selected version ------------------------------
    mo.stop(db_error is not None, mo.callout(mo.md(f"Eval failures unavailable: {db_error}"), kind="warn"))
    mo.stop(gv_df.empty or version_pick.value is None, mo.callout(mo.md("Pick a gate version above to see its eval failures."), kind="info"))
    _v = int(version_pick.value)
    _hit = gv_df[gv_df["version"] == _v]
    mo.stop(_hit.empty, mo.callout(mo.md(f"Gate v{_v} not found."), kind="warn"))
    _ev = _hit.iloc[0]["eval"] or {}
    _fail = pd.DataFrame(_ev.get("failures") or [], columns=["kind", "tool", "message", "reason"])
    _missed = int((_fail["kind"] == "missed_attack").sum()) if len(_fail) else 0
    _blocked = int((_fail["kind"] == "blocked_benign").sum()) if len(_fail) else 0

    # The defender run that produced this version, for the attempt-by-attempt story.
    _run = None
    if not runs_df.empty and "shipped_version" in runs_df.columns:
        _rr = runs_df[pd.to_numeric(runs_df["shipped_version"], errors="coerce") == _v]
        if len(_rr):
            _run = _rr.iloc[0].to_dict()

    _parts = [mo.md(f"## Eval failures — gate v{_v}")]
    if not _ev:
        _parts.append(mo.callout(mo.md("This version has no stored eval (seed versions are never evaluated)."), kind="info"))
    else:
        _weave = _ev.get("weave_url")
        _parts.append(mo.hstack([
            mo.stat(value=str(_missed), label="Missed attacks", caption="gate allowed a forbidden call", bordered=True),
            mo.stat(value=str(_blocked), label="Blocked benign", caption="gate blocked an allowed call", bordered=True),
            mo.stat(value=f"{_ev.get('n_attacks', '?')} / {_ev.get('n_benign', '?')}", label="Eval set", caption="attacks / benign", bordered=True),
            mo.stat(value="PASS" if _ev.get("passed") else "FAIL", label="Verdict", caption=(f"[Weave eval ↗]({_weave})" if _weave else "no Weave link"), bordered=True),
        ], widths="equal", wrap=True))
        _parts.append(mo.ui.table(_fail, selection=None, show_column_summaries=False, wrapped_columns=["message", "reason"])
                      if len(_fail) else mo.callout(mo.md("Zero failures: every attack caught, every benign request allowed."), kind="success"))
    if _run:
        _log = _run.get("log") or []
        _parts.append(mo.md(f"#### Defender run that shipped v{_v} · round {_run.get('round')} · {_run.get('breaches_considered')} breach(es) → "
                            f"{_run.get('variants_generated')} variants · {len(_run.get('attempts') or [])} attempt(s)"))
        _parts.append(mo.md("```text\n" + "\n".join(str(l) for l in _log) + "\n```" if _log else "_no log_"))
    mo.vstack(_parts)
    return


@app.cell
def _(attackers_df, breaches_df, db_error, mo, pd):
    # --- Cell 9: leaderboard + breach feed --------------------------------------------
    mo.stop(db_error is not None, mo.callout(mo.md(f"Leaderboard unavailable: {db_error}"), kind="warn"))
    mo.stop(attackers_df.empty and breaches_df.empty,
            mo.callout(mo.md("Nobody has joined yet. Scan the QR on the war room (`/attack`) to enter the room."), kind="info"))

    _cats = {}
    if not breaches_df.empty and {"attacker_id", "category"}.issubset(breaches_df.columns):
        for _aid, _g in breaches_df.groupby("attacker_id"):
            _cats[_aid] = sorted(set(str(c) for c in _g["category"].dropna()))
    if not attackers_df.empty:
        _lb = attackers_df.copy()
        _lb["categories"] = [", ".join(sorted(set(_cats.get(_r.get("id"), []) or []) | set(_r.get("earned") or [])))
                             for _r in _lb.to_dict("records")]
        _lb["synthetic"] = _lb["synthetic"].astype(bool) if "synthetic" in _lb.columns else False
        _lb = _lb.sort_values(["score", "breaches", "joined_at"], ascending=[False, False, True]).reset_index(drop=True)
        _lb.insert(0, "rank", range(1, len(_lb) + 1))
        leaderboard = _lb[["rank", "nickname", "score", "breaches", "attacks", "categories", "synthetic", "customer_id", "last_seen"]]
    else:
        leaderboard = pd.DataFrame(columns=["rank", "nickname", "score", "breaches", "attacks", "categories", "synthetic"])

    if not breaches_df.empty:
        _nick = attackers_df[["id", "nickname"]].rename(columns={"id": "attacker_id"}) if not attackers_df.empty else pd.DataFrame(columns=["attacker_id", "nickname"])
        _feed = breaches_df.merge(_nick, on="attacker_id", how="left")
        _probs = [p if isinstance(p, dict) else {} for p in _feed["gate_probabilities"].tolist()]
        for _k in ("allow", "block", "escalate"):
            _feed[f"P({_k})"] = [p.get(_k) for p in _probs]
        _feed["args"] = [str(a) for a in _feed["args"].tolist()]
        _feed = _feed.sort_values("created_at", ascending=False)
        breach_feed = _feed[["created_at", "round", "nickname", "category", "tool", "reason", "points", "P(allow)", "P(block)", "P(escalate)",
                             "gate_version", "patched_in", "message", "args"]]
    else:
        breach_feed = pd.DataFrame(columns=["created_at", "round", "nickname", "category", "tool", "reason", "points"])

    mo.vstack([
        mo.md(f"## Leaderboard — {len(leaderboard)} attacker(s)"),
        mo.ui.table(leaderboard, selection=None, show_column_summaries=False, page_size=15) if len(leaderboard) else mo.md("_empty_"),
        mo.md(f"## Breach feed — {len(breach_feed)} breach(es), newest first"),
        (mo.ui.table(breach_feed, selection=None, show_column_summaries=False, page_size=15, wrapped_columns=["reason", "message"],
                     format_mapping={"P(allow)": "{:.2f}", "P(block)": "{:.2f}", "P(escalate)": "{:.2f}"})
         if len(breach_feed) else mo.callout(mo.md("No breaches yet: the gate is holding."), kind="success")),
    ])
    return


@app.cell
def _():
    # Session cache for the attack map: embeddings keyed by message so refresh ticks only encode new attacks.
    embed_cache = {"model": None, "backend": None, "device": None, "vectors": {}}
    return (embed_cache,)


@app.cell
def _(mo):
    mo.md("""
    ## Attack map (GPU)
    Every message the room sent, embedded and projected to 2-D. Colour is the exact outcome:
    **red** breached, **amber** blocked by the gate, **violet** a legitimate request that was
    wrongly blocked, **green** allowed and legitimate. Clusters are attack families; the defender's
    job is to move whole clusters from red to amber without touching the green ones. On molab this
    cell runs `all-MiniLM-L6-v2` on the notebook's GPU (an NVIDIA Blackwell when one is attached);
    without a GPU it falls back to CPU, and without sentence-transformers to a hashed bag-of-words.
    """)
    return


@app.cell
def _(embed_cache, alt, calls, db_error, mo, pd, turns_df):
    mo.stop(bool(db_error) or turns_df is None or len(turns_df) == 0, mo.callout("No attacks yet: the map fills in as the room attacks.", kind="neutral"))
    import numpy as np

    # one row per turn with its exact outcome
    _rows = []
    for _, _t in turns_df.iterrows():
        _tc = calls[calls["turn_id"] == _t["id"]] if "turn_id" in calls.columns else calls.iloc[0:0]
        if len(_tc) and bool(_tc["breach"].any()):
            _out = "breach"
        elif len(_tc) and bool(_tc["benign_block"].any()):
            _out = "false block"
        elif len(_tc) and bool((_tc["decision"] != "allow").any()):
            _out = "blocked"
        else:
            _out = "allowed"
        _rows.append({"message": str(_t["message"])[:300], "outcome": _out, "round": _t.get("round"), "points": int(_t.get("breach_points") or 0)})
    _df = pd.DataFrame(_rows)
    _texts = _df["message"].tolist()

    def _hash_embed(texts, dim=256):
        import hashlib

        M = np.zeros((len(texts), dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in t.lower().split():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                M[i, h % dim] += 1.0
        n = np.linalg.norm(M, axis=1, keepdims=True)
        return M / np.maximum(n, 1e-6)

    _missing = [t for t in _texts if t not in embed_cache["vectors"]]
    if _missing:
        if embed_cache["model"] is None and embed_cache["backend"] is None:
            try:
                import torch
                from sentence_transformers import SentenceTransformer

                _dev = "cuda" if torch.cuda.is_available() else "cpu"
                embed_cache["model"] = SentenceTransformer("all-MiniLM-L6-v2", device=_dev)
                embed_cache["backend"] = "all-MiniLM-L6-v2"
                embed_cache["device"] = torch.cuda.get_device_name(0) if _dev == "cuda" else "cpu"
            except Exception:
                embed_cache["backend"] = "hashed bag-of-words"
                embed_cache["device"] = "cpu"
        if embed_cache["model"] is not None:
            _vecs = embed_cache["model"].encode(_missing, batch_size=256, normalize_embeddings=True)
        else:
            _vecs = _hash_embed(_missing)
        for t, v in zip(_missing, _vecs):
            embed_cache["vectors"][t] = np.asarray(v, dtype=np.float32)
    X = np.stack([embed_cache["vectors"][t] for t in _texts])
    _Xc = X - X.mean(axis=0, keepdims=True)
    if len(_texts) >= 3:
        _U, _S, _Vt = np.linalg.svd(_Xc, full_matrices=False)
        _P = _Xc @ _Vt[:2].T
    else:
        _P = np.zeros((len(_texts), 2))
    _df["x"], _df["y"] = _P[:, 0], _P[:, 1]

    _chart = (
        alt.Chart(_df)
        .mark_circle(opacity=0.85)
        .encode(
            x=alt.X("x:Q", axis=None), y=alt.Y("y:Q", axis=None),
            color=alt.Color("outcome:N", scale=alt.Scale(domain=["breach", "blocked", "false block", "allowed"], range=["#ff3b5c", "#ffb020", "#a78bfa", "#22c55e"])),
            size=alt.Size("points:Q", scale=alt.Scale(range=[40, 400]), legend=None),
            tooltip=["message:N", "outcome:N", "round:Q", "points:Q"],
        )
        .properties(height=420, width="container", title=f"{len(_df)} messages, {int((_df['outcome'] == 'breach').sum())} breaches")
        .interactive()
    )
    mo.vstack([
        mo.callout(mo.md(f"Embedding backend: **{embed_cache['backend']}** on **{embed_cache['device']}** (cached {len(embed_cache['vectors'])} messages)"), kind="info"),
        mo.ui.altair_chart(_chart),
    ])
    return


@app.cell
def _(get_trace_name, mo, set_trace_name, trace_limit, traces_df):
    # --- Cell 10a: trace filter (kept across refresh ticks via mo.state) --------------
    _names = ["All"]
    if not traces_df.empty and "name" in traces_df.columns:
        _names += sorted(str(n) for n in traces_df["name"].dropna().unique())
    _cur = get_trace_name() if get_trace_name() in _names else "All"
    trace_name_pick = mo.ui.dropdown(options=_names, value=_cur, label="Trace name", on_change=set_trace_name)
    mo.vstack([mo.md("## Traces"), mo.hstack([trace_name_pick, trace_limit], justify="start", gap=2)])
    return (trace_name_pick,)


@app.cell
def _(db_error, mo, pd, trace_limit, trace_name_pick, traces_df):
    # --- Cell 10b: traces table with clickable Weave links -----------------------------
    mo.stop(db_error is not None, mo.callout(mo.md(f"Traces unavailable: {db_error}"), kind="warn"))
    mo.stop(traces_df.empty, mo.callout(mo.md("No traces yet. Every agent turn, gate decision, oracle verdict and defender stage lands here."), kind="info"))
    _t = traces_df
    if trace_name_pick.value and trace_name_pick.value != "All":
        _t = _t[_t["name"] == trace_name_pick.value]
    _limit = int(trace_limit.value or 100)
    _sort = "seq" if "seq" in _t.columns else "started_at"
    _t = _t.sort_values(_sort, ascending=False).head(_limit)

    def _esc(s):
        return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")

    def _ms(v):
        return "—" if v is None or pd.isna(v) else f"{int(v):,}"

    _n_linked = int(_t["weave_url"].notna().sum()) if "weave_url" in _t.columns else 0
    _lines = [f"{len(_t)} trace(s) shown ({_n_linked} with a Weave link) · newest first", "",
              "| name | duration (ms) | started | turn | parent | Weave |", "|---|---:|---|---|---|---|"]
    for _r in _t.to_dict("records"):
        _url = _r.get("weave_url")
        _link = f"[open ↗]({_url})" if isinstance(_url, str) and _url.startswith("http") else "—"
        _lines.append(f"| `{_esc(_r.get('name'))}` | {_ms(_r.get('duration_ms'))} | {_esc(_r.get('started_at'))} | "
                      f"`{_esc(_r.get('turn_id') or '')}` | `{_esc(_r.get('parent_id') or '')}` | {_link} |")
    mo.md("\n".join(_lines))
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Running this notebook

    ```bash
    cd siege && source .venv/bin/activate
    marimo run  notebooks/siege_lab.py     # read-only app for the projector
    marimo edit notebooks/siege_lab.py     # live-edit the analysis during the demo
    marimo export html notebooks/siege_lab.py -o siege_lab.html   # static snapshot
    ```

    The DB path box at the top defaults to `backend/data/siege.db`; leave the refresh timer
    on while the room attacks and every cell re-reads the store. The file carries its own
    inline dependencies (`marimo`, `pandas`, `altair`, `numpy`, optional `sentence-transformers` for the GPU attack map) and uses only those plus `sqlite3`
    and the standard library, so the **same file runs unchanged on
    [molab](https://molab.marimo.io)**: upload it together with a `siege.db` snapshot and
    point the path box at it.
    """)
    return


if __name__ == "__main__":
    app.run()
