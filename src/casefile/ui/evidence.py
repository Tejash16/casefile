"""Evidence tab (b3): the rule tests that ran, the evidence filtered by hypothesis, and every T16
relationship path drawn as a left-to-right chain. Reads only files in out_dir."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

DIRECTION_COLOUR = {"supports": "red", "refutes": "green", "neutral": "gray"}
# where each test's facts come from: in-house files, Crustdata records, or both
DATA_SOURCE = {
    **{f"T{i:02d}": "Ledger" for i in range(1, 18)},
    "T13": "Crustdata",
    "T15": "Crustdata",
    "T17": "Crustdata",
    "T01": "Both",
    "T03": "Both",
    "T16": "Both",
}
STAFF, VENDOR, CRUSTDATA, SHARED = "#dbeafe", "#fee2e2", "#7c3aed", "#fef3c7"
NODE_STYLE = {  # graph node kind -> (label, fill colour)
    "staff": ("staff", STAFF),
    "vendor": ("vendor", VENDOR),
    "cdco": ("Crustdata company", CRUSTDATA),
    "cdperson": ("Crustdata person", CRUSTDATA),
    "person": ("LinkedIn profile", SHARED),
    "addr": ("address", SHARED),
    "phone": ("phone", SHARED),
    "bank": ("bank account", SHARED),
    "taxid": ("tax id", SHARED),
    "email": ("email", SHARED),
}
LEGEND = "🟦 staff · 🟥 vendor · 🟪 Crustdata record (company / person) · 🟨 shared identifier"
PERSONAL = {"addr", "phone", "bank", "email", "person"}  # masked under --redact
HOP = re.compile(r" -\[(\w+): ")


def _json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def _test_names() -> dict[str, str]:
    try:
        from casefile.rules.registry import TESTS

        return {tid: t.name for tid, t in TESTS.items()}
    except Exception:  # noqa: BLE001 - names are cosmetic
        return {}


def tests_run(log_path: Path) -> list[dict[str, Any]]:
    """One row per rule test that ran, from the audit log's rule_test records (live)."""
    pre: dict[str, str] = {}
    rows: dict[str, dict[str, Any]] = {}
    names = _test_names()
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # a line still being written
        if rec.get("action_type") != "rule_test":
            continue
        if rec.get("record_phase") == "pre_execution":
            tid = (rec.get("action_detail") or {}).get("name", "?")
            pre[rec["record_id"]] = tid
            row = rows.setdefault(
                tid,
                {
                    "test": tid,
                    "name": names.get(tid, ""),
                    "data source": DATA_SOURCE.get(tid, ""),
                    "runs": 0,
                    "hits": 0,
                    "errors": 0,
                },
            )
            row["runs"] += 1
        else:
            tid = pre.get(rec.get("parent_record_id"))
            if tid is None:
                continue
            out = rec.get("outcome") or {}
            rows[tid]["hits"] += len(out.get("evidence_ids") or [])
            rows[tid]["errors"] += out.get("status") == "error"
    return sorted(rows.values(), key=lambda r: r["test"])


def path_dot(evidence: dict[str, Any], redact: bool = False) -> str | None:
    """Graphviz DOT for a T16 path: nodes from source.refs, edge labels from the quote's hops."""
    if evidence.get("test_id") != "T16":
        return None
    nodes = list((evidence.get("source") or {}).get("refs") or [])
    if len(nodes) < 2:
        return None
    kinds = HOP.findall(" " + evidence.get("quote", ""))
    if len(kinds) != len(nodes) - 1:
        kinds = [""] * (len(nodes) - 1)
    lines = [
        "digraph {",
        "  rankdir=LR;",
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=10, color="#64748b"];',
    ]
    for i, node in enumerate(nodes):
        kind, _, value = node.partition(":")
        label, fill = NODE_STYLE.get(kind, (kind, "#f1f5f9"))
        if redact and kind in PERSONAL:
            value = "…" + value[-4:] if len(value) > 4 else "…"
        value = value if len(value) <= 32 else value[:30] + "…"
        text = f"{value}\\n({label})" if kind in ("staff", "vendor") else f"{label}\\n{value}"
        font = ', fontcolor="white"' if fill == CRUSTDATA else ""
        lines.append(f'  n{i} [label="{_esc(text)}", fillcolor="{fill}"{font}];')
    for i, kind in enumerate(kinds):
        lines.append(f'  n{i} -> n{i + 1} [label="{_esc(kind)}"];')
    lines.append("}")
    return "\n".join(lines)


def _esc(s: str) -> str:
    return s.replace('"', "'")


def _direction_counts(evidence: list[dict[str, Any]]) -> dict[str, Counter]:
    out: dict[str, Counter] = {}
    for e in evidence:
        out.setdefault(e["test_id"], Counter())[e["direction"]] += 1
    return out


def _hypothesis_label(f: dict[str, Any]) -> str:
    subs = ", ".join(f.get("subjects") or []) or "-"
    objs = ", ".join(f.get("objects") or []) or "-"
    return f"{f['hypothesis_id']} {f.get('typology', '')} {subs} → {objs} ({f.get('verdict', '')})"


def _body(out_dir: Path, inputs: dict[str, Any]) -> None:
    redact = bool(inputs.get("redact"))
    all_ev = _json(out_dir / "evidence_all.json")
    cited = _json(out_dir / "evidence.json")
    evidence: list[dict[str, Any]] = all_ev if isinstance(all_ev, list) else cited or []
    findings = _json(out_dir / "findings.json") or []

    st.subheader("Rule tests run")
    rows = tests_run(out_dir / "log.jsonl")
    if not rows:
        st.info("Rule tests appear here once the Rules stage starts (log.jsonl).")
    else:
        counts = _direction_counts(evidence)
        for r in rows:
            c = counts.get(r["test"], Counter())
            r |= {"supports": c["supports"], "refutes": c["refutes"], "neutral": c["neutral"]}
        st.dataframe(rows, hide_index=True, width="stretch")
        if evidence and all_ev is None:
            st.caption("Supports / refutes count the cited exhibits (evidence.json).")

    st.subheader("Evidence")
    if not evidence:
        st.info("Evidence appears when the run finishes (evidence.json).")
        return
    options = ["All evidence"] + [_hypothesis_label(f) for f in findings]
    choice = st.selectbox("Hypothesis", options, key="b3_evidence_hypothesis")
    shown = evidence
    if choice != "All evidence":
        hid = choice.split(" ", 1)[0]
        f = next((x for x in findings if x["hypothesis_id"] == hid), {})
        linked = set(f.get("supporting_evidence") or []) | set(f.get("counter_evidence") or [])
        shown = [e for e in evidence if hid in (e.get("hypothesis_ids") or [])]
        shown = [e for e in shown if not linked or e["evidence_id"] in linked] or shown
    show_neutral = st.toggle("Show neutral notes", value=False, key="b3_evidence_neutral")
    if not show_neutral:
        shown = [e for e in shown if e["direction"] != "neutral"]
    names = _test_names()

    paths = [e for e in shown if e["test_id"] == "T16"]
    seen: set[tuple[str, ...]] = set()
    if paths:
        st.markdown("**Relationship paths (T16)**")
        st.caption(LEGEND)
    for e in paths:
        key = tuple(e["source"]["refs"])
        if key in seen:
            continue
        seen.add(key)
        dot = path_dot(e, redact=redact)
        if dot:
            st.caption(f"{e['evidence_id']}: {e['summary']}")
            st.graphviz_chart(dot, width="stretch")

    st.markdown(f"**{len(shown)} evidence objects**")
    for e in sorted(shown, key=lambda x: (-x["strength"], x["evidence_id"])):
        colour = DIRECTION_COLOUR.get(e["direction"], "gray")
        st.markdown(
            f"**{e['evidence_id']}** · {e['test_id']} {names.get(e['test_id'], '')} · "
            f":{colour}[{e['direction']} {e['strength']:.2f}] · {e['summary']}"
        )
        with st.expander(f"{e['evidence_id']} quote and source"):
            st.code(e["quote"], language=None, wrap_lines=True)
            src = e.get("source") or {}
            st.caption(
                f"source {src.get('kind')} · refs {', '.join(src.get('refs') or [])}"
                + (f" · updated_at {src['as_of']}" if src.get("as_of") else "")
                + f" · sha256 {e.get('sha256', '')[:16]}… · log {e.get('log_record_id', '')[:8]}"
            )


def render(out_dir: Path, inputs: dict[str, Any]) -> None:
    """Evidence tab; polls every second while the pipeline thread is alive."""
    out_dir = Path(out_dir)

    @st.fragment(run_every=1 if inputs.get("running") else None)
    def panel() -> None:
        _body(out_dir, inputs)

    panel()
