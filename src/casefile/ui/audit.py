"""Audit-log tab of the demo UI (a3): log table, metrics, Merkle root, verify and tamper demo.

Reads only files in out_dir (log.jsonl, root.txt, case_file.md). Verification runs the repo-root
standalone `verify.py` in a subprocess, the same command judges run; the tamper demo flips one
digit in a copy of the log (log_tampered.jsonl) and verifies that copy, never the original.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TAMPERED = "log_tampered.jsonl"


def read_log(out_dir: Path) -> list[dict[str, Any]]:
    """Records of out_dir/log.jsonl; a partial last line (run still writing) is skipped."""
    path = out_dir / "log.jsonl"
    if not path.is_file():
        return []
    recs = []
    for line in path.read_bytes().splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            recs.append(rec)
    return recs


def _detail(rec: dict[str, Any]) -> dict[str, Any]:
    d = rec.get("action_detail")
    return d if isinstance(d, dict) else {}


def _outcome(rec: dict[str, Any]) -> dict[str, Any]:
    o = rec.get("outcome")
    return o if isinstance(o, dict) else {}


def log_rows(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One table row per record, oldest first."""
    rows = []
    for r in recs:
        d, o = _detail(r), _outcome(r)
        cache_hit = d.get("cache_hit", o.get("cache_hit"))
        rows.append(
            {
                "seq": r.get("seq"),
                "time": str(r.get("timestamp", ""))[11:23],
                "action_type": r.get("action_type"),
                "phase": "pre" if r.get("record_phase") == "pre_execution" else "post",
                "name": d.get("name", ""),
                "status": o.get("status", ""),
                # None, not "", for missing values: one type per column for Arrow
                "cache_hit": None if cache_hit is None else bool(cache_hit),
                "credits": None if o.get("credits_used") is None else _num(o["credits_used"]),
            }
        )
    return rows


def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _ts(rec: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(rec.get("timestamp", "")).replace("Z", "+00:00"))
    except ValueError:
        return None


def metrics(recs: list[dict[str, Any]]) -> dict[str, float]:
    """Run metrics computed from the log itself (post_execution records carry the outcomes)."""
    posts = [r for r in recs if r.get("record_phase") == "post_execution"]
    tool = [r for r in posts if r.get("action_type") == "tool_call"]
    model = [r for r in posts if r.get("action_type") == "model_call"]
    stamps = [t for t in (_ts(r) for r in recs) if t]
    return {
        "wall_seconds": round((max(stamps) - min(stamps)).total_seconds(), 1) if stamps else 0.0,
        "crustdata_calls": len(tool),
        "credits": round(sum(_num(_outcome(r).get("credits_used")) for r in tool), 2),
        "model_calls": len(model),
        "tokens": int(
            sum(
                _num(_outcome(r).get("tokens_in")) + _num(_outcome(r).get("tokens_out"))
                for r in model
            )
        ),
        "records": len(recs),
    }


def merkle_root(out_dir: Path) -> tuple[str, int | None] | None:
    path = out_dir / "root.txt"
    if not path.is_file():
        return None
    parts = path.read_text(encoding="utf-8").split()
    if not parts:
        return None
    return parts[0], (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None)


def run_verify(log_path: Path) -> tuple[bool, list[str]]:
    """Run the standalone verifier; (ok, output lines). Falls back to the in-package verifier
    if the repo-root verify.py is not present (installed package)."""
    script = REPO_ROOT / "verify.py"
    if script.is_file():
        proc = subprocess.run(
            [sys.executable, "-I", str(script), str(log_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        lines = [ln for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()]
        return proc.returncode == 0, lines
    from casefile.audit.verify import verify

    rep = verify(log_path)
    return rep.ok, rep.lines()


def make_tampered(out_dir: Path) -> tuple[Path, int, str] | None:
    """Copy log.jsonl to log_tampered.jsonl with one digit of a middle record's timestamp
    changed. Returns (path, seq, description) or None if the log is too short."""
    src = out_dir / "log.jsonl"
    if not src.is_file():
        return None
    lines = src.read_bytes().split(b"\n")
    idx = [i for i, ln in enumerate(lines) if ln.strip()]
    if len(idx) < 3:
        return None
    i = idx[len(idx) // 2]
    rec = json.loads(lines[i])
    key = b'"timestamp":"'
    start = lines[i].index(key) + len(key)
    end = lines[i].index(b'"', start)
    digit_pos = max(p for p in range(start, end) if lines[i][p : p + 1].isdigit())
    old = lines[i][digit_pos : digit_pos + 1]
    new = str((int(old) + 1) % 10).encode()
    lines[i] = lines[i][:digit_pos] + new + lines[i][digit_pos + 1 :]
    dst = out_dir / TAMPERED
    shutil.copyfile(src, dst)  # keep the original byte for byte; then overwrite the copy
    dst.write_bytes(b"\n".join(lines))
    what = f"record seq {rec.get('seq')}: timestamp digit {old.decode()} -> {new.decode()}"
    return dst, int(rec.get("seq", -1)), what


def render(out_dir: Path, inputs: dict) -> None:
    import streamlit as st

    out_dir = Path(out_dir)
    running = bool(inputs.get("running")) if inputs else False

    @st.fragment(run_every=1 if running else None)
    def live() -> None:
        recs = read_log(out_dir)
        if not recs:
            st.info("No audit log yet. Start an investigation to see every action recorded here.")
            return
        m = metrics(recs)
        c = st.columns(5)
        c[0].metric("Wall time (s)", m["wall_seconds"])
        c[1].metric("Crustdata calls", m["crustdata_calls"])
        c[2].metric("Credits", m["credits"])
        c[3].metric("Model calls", m["model_calls"])
        c[4].metric("Model tokens", f"{m['tokens']:,}")

        root = merkle_root(out_dir)
        if root:
            size = f" over {root[1]} records" if root[1] is not None else ""
            st.markdown(f"**Merkle root** (RFC 6962){size}: `{root[0]}`")
        else:
            st.caption(
                f"{m['records']} records so far; the Merkle root is sealed when the run ends."
            )
        st.dataframe(log_rows(recs), hide_index=True, use_container_width=True, height=360)

    live()

    if not (out_dir / "log.jsonl").is_file():
        return
    st.divider()
    b = st.columns(3)
    if b[0].button("Verify log", disabled=running, use_container_width=True):
        ok, lines = run_verify(out_dir / "log.jsonl")
        last = lines[-1] if lines else "no output"
        if ok:
            n = metrics(read_log(out_dir))["records"]
            st.success(f"chain ok — {n} records. {last}")
        else:
            st.error("\n\n".join(ln for ln in lines if ln.startswith(("FAIL", "VERIFY"))) or last)
        st.caption(f"`python verify.py {out_dir.as_posix()}/log.jsonl` (standard library only)")
    if b[1].button("Tamper demo", disabled=running, use_container_width=True):
        made = make_tampered(out_dir)
        if made is None:
            st.warning("The log is too short to tamper with.")
        else:
            path, _, what = made
            ok, lines = run_verify(path)
            st.write(f"Copied the log to `{path.name}` and changed one character: {what}.")
            fails = [ln for ln in lines if ln.startswith("FAIL")]
            if ok:
                st.warning("Unexpected: the tampered copy still verifies.")
            else:
                st.error("\n\n".join(fails or lines[-1:]))
    case_md = out_dir / "case_file.md"
    if case_md.is_file():
        b[2].download_button(
            "Download case file",
            data=case_md.read_bytes(),
            file_name="case_file.md",
            mime="text/markdown",
            use_container_width=True,
        )
