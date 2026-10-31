"""Casefile UI: pick a case, run pipeline.run in a background thread, show each panel.

Run with `uv run casefile ui`. The page never changes pipeline logic; it copies the inputs into
the case's out_dir, starts the run, and every panel reads files from out_dir only.
"""

from __future__ import annotations

import importlib
import json
import shutil
import threading
import traceback
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[3]  # repo root (src/casefile/ui/app.py)
CASES = ROOT / "cases"
OUT = ROOT / "out"

TABS = [  # (tab label, panel module, owner)
    ("Findings", "findings", "a2"),
    ("Entities (Crustdata)", "entities", "b2"),
    ("Evidence", "evidence", "b3"),
    ("Inputs", "inputs", "b1"),
    ("Audit log", "audit", "a3"),
]
STAGES = [
    "Ingest",
    "Hypotheses",
    "Crustdata: resolve vendors & staff",
    "Rules",
    "Gate",
    "Case file",
]


@st.cache_resource
def _runs() -> dict[str, dict[str, Any]]:
    """Run state shared across reruns of this Streamlit process: out_dir -> thread, error."""
    return {}


def _case_dirs() -> list[str]:
    return sorted(p.name for p in CASES.iterdir() if (p / "case.json").exists())


def _stage_index(log: Path) -> int:
    """Furthest stage reached, from the action types in log.jsonl (-1 before the run)."""
    if not log.exists():
        return -1
    idx = -1
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = rec.get("action_type")
        name = str((rec.get("action_detail") or {}).get("name", ""))
        if kind == "file_read":
            i = 0
        elif kind == "model_call" and "propose" in name:
            i = 1
        elif kind == "tool_call":
            i = 2
        elif kind == "rule_test":
            i = 3
        elif kind == "gate" or (kind == "model_call" and "critique" in name):
            i = 4
        elif kind == "render":
            i = 5
        else:
            continue
        idx = max(idx, i)
    return idx


def _crustdata_strip(out_dir: Path) -> None:
    """Live counters: Crustdata calls and credits from log.jsonl; resolved companies and people
    from entities.json (written right after the resolve stage)."""
    calls, credits = 0, 0.0
    log = out_dir / "log.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("action_type") != "tool_call":
                continue
            if rec.get("record_phase") == "pre_execution":
                calls += 1
            else:
                credits += float((rec.get("outcome") or {}).get("credits_used") or 0)
    companies = people = "—"
    ent = out_dir / "entities.json"
    if ent.exists():
        try:
            data = json.loads(ent.read_text(encoding="utf-8"))
            companies = sum(v["resolution"]["status"] == "resolved" for v in data["vendors"])
            companies = f"{companies}/{len(data['vendors'])}"
            people = sum(s["resolution"]["status"] == "resolved" for s in data["staff"])
            people = f"{people}/{len(data['staff'])}"
        except (OSError, ValueError, KeyError, TypeError):
            pass
    st.markdown("**Powered by Crustdata identity graph**")
    c = st.columns(4)
    c[0].metric("Crustdata calls", calls)
    c[1].metric("Companies resolved", companies)
    c[2].metric("People resolved", people)
    c[3].metric("Crustdata credits used", f"{credits:.2f}")


def _stage_bar(out_dir: Path, running: bool, error: str | None) -> None:
    reached = _stage_index(out_dir / "log.jsonl")
    done = (out_dir / "root.txt").exists() and not running
    cols = st.columns(len(STAGES))
    for i, (col, name) in enumerate(zip(cols, STAGES, strict=True)):
        if done or i < reached:
            col.success(f"✓ {name}")
        elif i == reached and running:
            col.warning(f"… {name}")
        else:
            col.info(name)
    if error:
        st.error(f"Run failed: {error}")


def _start(inputs: dict[str, Any], out_dir: Path, offline: bool, redact: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):  # a new run starts from an empty case directory
        if old.is_file():
            old.unlink()
    staged: dict[str, Path] = {}
    for key, name in [
        ("tip", "tip.txt"),
        ("ledger", "ledger.csv"),
        ("vendors", "vendors.csv"),
        ("staff", "staff.csv"),
        ("case_json", "case.json"),
    ]:
        src = inputs.get(key)
        if src:
            shutil.copyfile(src, out_dir / name)
            staged[key] = out_dir / name
    state: dict[str, Any] = {"error": None}

    def work() -> None:
        from casefile import pipeline

        try:
            pipeline.run(
                staged["tip"],
                staged["ledger"],
                staged["vendors"],
                staged["staff"],
                out_dir,
                offline=offline,
                redact=redact,
                case_id=out_dir.name,
            )
        except BaseException as e:  # noqa: BLE001 - shown on the page, CLI stays the fallback
            state["error"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()

    t = threading.Thread(target=work, daemon=True, name=f"casefile-{out_dir.name}")
    state["thread"] = t
    _runs()[str(out_dir)] = state
    t.start()


def _panel(module: str, owner: str, out_dir: Path, inputs: dict[str, Any]) -> None:
    try:
        mod = importlib.import_module(f"casefile.ui.{module}")
    except ModuleNotFoundError:
        st.info(f"This panel ({module}.py, {owner}) has not landed yet.")
        return
    try:
        mod.render(out_dir, inputs)
    except Exception as e:  # noqa: BLE001 - one broken panel must not break the page
        st.error(f"{module}.py failed: {type(e).__name__}: {e}")


def main() -> None:
    st.set_page_config(page_title="Casefile", page_icon="🗂️", layout="wide")
    st.title("Casefile — every fake caught, no honest business turned away")

    with st.sidebar:
        st.header("Case")
        choice = st.selectbox("Planted case", [*_case_dirs(), "Upload tip + 3 CSVs"])
        if choice == "Upload tip + 3 CSVs":
            up = {
                "tip": st.file_uploader("Tip (.txt)", type=["txt"]),
                "ledger": st.file_uploader("Ledger (.csv)", type=["csv"]),
                "vendors": st.file_uploader("Vendor master (.csv)", type=["csv"]),
                "staff": st.file_uploader("Staff list (.csv)", type=["csv"]),
            }
            out_dir = OUT / "upload"
            src: dict[str, Any] = {}
            if all(up.values()):
                tmp = OUT / ".upload-src"
                tmp.mkdir(parents=True, exist_ok=True)
                for key, f in up.items():
                    p = tmp / f.name
                    p.write_bytes(f.getvalue())
                    src[key] = p
        else:
            case = CASES / choice
            out_dir = OUT / choice
            src = {
                "tip": case / "tip.txt",
                "ledger": case / "ledger.csv",
                "vendors": case / "vendors.csv",
                "staff": case / "staff.csv",
                "case_json": case / "case.json",
            }
        offline = st.toggle("Offline (Crustdata cache only)", value=False)
        redact = st.toggle("Redact person names", value=True)
        state = _runs().get(str(out_dir), {})
        running = bool(state.get("thread") and state["thread"].is_alive())
        ready = all(src.get(k) for k in ("tip", "ledger", "vendors", "staff"))
        if st.button(
            "Investigate", type="primary", use_container_width=True, disabled=running or not ready
        ):
            _start(src, out_dir, offline, redact)
            st.rerun()
        st.caption(f"Output: `{out_dir.relative_to(ROOT).as_posix()}/`")

    inputs = {
        "tip": out_dir / "tip.txt",
        "ledger": out_dir / "ledger.csv",
        "vendors": out_dir / "vendors.csv",
        "staff": out_dir / "staff.csv",
        "case_json": (out_dir / "case.json") if (out_dir / "case.json").exists() else None,
        "running": running,
        "redact": redact,
    }
    st.session_state["running"] = running

    @st.fragment(run_every=1)
    def live() -> None:
        s = _runs().get(str(out_dir), {})
        alive = bool(s.get("thread") and s["thread"].is_alive())
        _crustdata_strip(out_dir)
        _stage_bar(out_dir, alive, s.get("error"))
        if running and not alive:  # the run just finished: redraw the panels once
            st.rerun()

    live()

    for tab, (_, module, owner) in zip(st.tabs([t[0] for t in TABS]), TABS, strict=True):
        with tab:
            _panel(module, owner, out_dir, inputs)


main()
