"""Findings tab: one card per allegation, verdict badge, cited sentences with expandable exhibits.

Reads only out_dir files (findings.json, evidence.json, entities.json) and the inputs app.py copied
there (vendors.csv, case.json). Never touches pipeline logic.
"""

from __future__ import annotations

import csv
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import streamlit as st

VERDICT_ORDER = {"Substantiated": 0, "Unfounded": 1, "Unsubstantiated": 2}
BADGE_COLOUR = {"Substantiated": "#c62828", "Unfounded": "#2e7d32", "Unsubstantiated": "#757575"}
MAX_REFS_SHOWN = 8


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _badge(verdict: str) -> str:
    colour = BADGE_COLOUR.get(verdict, "#757575")
    return (
        f'<span style="background:{colour};color:white;padding:3px 10px;border-radius:12px;'
        f'font-weight:600;font-size:0.85em">{verdict}</span>'
    )


def inr(amount: Any) -> str:
    """Indian digit grouping: 2173588.25 -> INR 21,73,588.25."""
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return str(amount)
    sign = "-" if d < 0 else ""
    whole, _, frac = f"{abs(d):.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    grouped = ",".join([*groups, tail]) if groups else tail
    return f"INR {sign}{grouped}.{frac}"


def _source_line(ev: dict) -> str:
    src = ev.get("source") or {}
    refs = list(src.get("refs") or [])
    shown = ", ".join(refs[:MAX_REFS_SHOWN])
    if len(refs) > MAX_REFS_SHOWN:
        shown += f" … and {len(refs) - MAX_REFS_SHOWN} more"
    line = f"**Source:** {src.get('kind', '?')} — {shown}"
    as_of = src.get("as_of")
    if not as_of:  # Crustdata refs carry the record's updated_at after "@"
        stamps = [r.split("@", 1)[1] for r in refs if r.startswith("crustdata:") and "@" in r]
        as_of = stamps[0] if stamps else None
    if as_of:
        line += f"  \n**updated_at:** {as_of}"
    return line


def _exhibit(eid: str, ev: dict | None) -> None:
    if ev is None:
        with st.expander(f"{_chip(eid, None)}", expanded=False):
            st.caption("This evidence id is not in evidence.json.")
        return
    test, direction = ev.get("test_id", ""), ev.get("direction", "")
    label = f"{_chip(eid, ev)}  {test} · {direction} · {float(ev.get('strength') or 0):.2f}"
    with st.expander(label, expanded=False):
        st.markdown(ev.get("summary", ""))
        st.code(ev.get("quote", ""), language=None, wrap_lines=True)
        st.markdown(_source_line(ev))
        st.caption(
            f"sha256 {str(ev.get('sha256', ''))[:16]}…  ·  log record {ev.get('log_record_id', '')}"
        )


CRUSTDATA_KINDS = {"crustdata_company", "crustdata_person"}
KIND_LABEL = {
    "vendor_master": "vendor master",
    "staff_list": "staff list",
    "graph": "graph",
    "derived_stat": "statistic",
}


def source_label(ev: dict | None) -> tuple[str, str]:
    """(badge colour, label) for an evidence object's source: grey ledger, violet Crustdata."""
    if ev is None:
        return "gray", "not in exhibits"
    src = ev.get("source") or {}
    kind, refs = src.get("kind", ""), list(src.get("refs") or [])
    more = f" +{len(refs) - 1}" if len(refs) > 1 else ""
    if kind == "ledger_rows":
        return "gray", f"ledger {refs[0] if refs else ''}{more}".strip()
    if kind in CRUSTDATA_KINDS:
        cd = next((r for r in refs if r.startswith("crustdata:")), refs[0] if refs else "")
        # crustdata:person:8812@2026-10-24 -> crustdata person 8812@2026-10-24
        parts = cd.split(":", 2)
        if len(parts) == 3:
            rid, _, stamp = parts[2].partition("@")
            text = f"crustdata {parts[1]} {rid}" + (f"@{stamp[:10]}" if stamp else "")
        else:
            text = f"crustdata {cd}"
        return "violet", text + more
    return "blue", f"{KIND_LABEL.get(kind, kind)} {refs[0] if refs else ''}{more}".strip()


def _chip(eid: str, ev: dict | None) -> str:
    colour, label = source_label(ev)
    label = label.replace("[", "(").replace("]", ")")
    return f":{colour}-badge[{eid} · {label}]"


def _chips(ids: list[str], evidence: dict[str, dict]) -> str:
    return " ".join(_chip(i, evidence.get(i)) for i in ids) if ids else "none"


def source_counts(ids: list[str], evidence: dict[str, dict]) -> tuple[int, int]:
    """Distinct ledger rows and distinct Crustdata records behind the given evidence ids."""
    rows: set[str] = set()
    records: set[str] = set()
    for i in ids:
        src = (evidence.get(i) or {}).get("source") or {}
        refs = src.get("refs") or []
        if src.get("kind") == "ledger_rows":
            rows.update(refs)
        elif src.get("kind") in CRUSTDATA_KINDS:
            cd = [r for r in refs if r.startswith("crustdata:")]
            records.update(cd or refs)
    return len(rows), len(records)


def _vendor_names(out_dir: Path, inputs: dict) -> dict[str, str]:
    ents = _load_json(out_dir / "entities.json")
    if isinstance(ents, dict) and ents.get("vendors"):
        return {v["vendor_id"]: v.get("name_raw", v["vendor_id"]) for v in ents["vendors"]}
    path = inputs.get("vendors")
    names: dict[str, str] = {}
    if path and Path(path).exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                vid = next((c.strip() for c in row if re.fullmatch(r"V\d+", c.strip())), None)
                if vid and vid not in names:
                    rest = [c.strip() for c in row if c.strip() and c.strip() != vid]
                    names[vid] = rest[0] if rest else vid
    return names


def _cleared(findings: list[dict], out_dir: Path, inputs: dict) -> None:
    st.subheader("Cleared vendors")
    names = _vendor_names(out_dir, inputs)
    spec = _load_json(Path(inputs["case_json"])) if inputs.get("case_json") else None
    must_clear = set((spec or {}).get("must_clear", []))
    implicated = {
        o for f in findings if f.get("verdict") == "Substantiated" for o in f.get("objects", [])
    }
    unfounded = {
        o for f in findings if f.get("verdict") == "Unfounded" for o in f.get("objects", [])
    }
    turned_away = sorted(must_clear & implicated)
    if turned_away:
        st.error(f"Expected-clean vendors with a Substantiated finding: {', '.join(turned_away)}")
    vendor_ids = sorted(set(names) | must_clear, key=lambda v: int(re.sub(r"\D", "", v) or 0))
    rows = [
        {
            "Vendor": v,
            "Name": names.get(v, ""),
            "Status": "allegation refuted (Unfounded)"
            if v in unfounded
            else "no Substantiated finding",
            "Expected clean": "yes" if v in must_clear else "",
        }
        for v in vendor_ids
        if v not in implicated
    ]
    if rows:
        st.caption(f"{len(rows)} vendors cleared: no allegation against them was Substantiated.")
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.caption("No vendors cleared.")


def _card(f: dict, evidence: dict[str, dict]) -> None:
    hid = f.get("hypothesis_id", "?")
    verdict = f.get("verdict", "Unsubstantiated")
    with st.container(border=True):
        subjects = ", ".join(f.get("subjects") or []) or "no staff named"
        objects = ", ".join(f.get("objects") or []) or "no vendor named"
        title = f"**{hid} · {f.get('typology', '')}** — {subjects} → {objects}"
        st.markdown(f"{_badge(verdict)}&nbsp;&nbsp;{title}", unsafe_allow_html=True)
        if f.get("statement"):
            st.markdown(f"*Allegation tested:* {f['statement']}")
        cols = st.columns(3)
        amount = f.get("amount_at_issue_inr")
        cols[0].metric("Amount at issue", inr(amount) if amount not in (None, "") else "—")
        cols[1].metric("Confidence", f"{float(f.get('confidence') or 0):.2f}")
        by = "coded gate"
        if f.get("verdict_by") == "gate_override_of_model":
            by = f"gate (overrode model: {f.get('model_verdict')})"
        cols[2].metric("Decided by", by)

        st.markdown("**Rationale**")
        sentences = f.get("rationale") or []
        if not sentences:
            st.caption("No cited sentences for this finding.")
        for s in sentences:
            ids = s.get("evidence_ids") or []
            st.markdown(f"{s.get('text', '')} {_chips(ids, evidence)}")
            for eid in ids:
                _exhibit(eid, evidence.get(eid))
        supporting = list(f.get("supporting_evidence") or [])
        counter = list(f.get("counter_evidence") or [])
        st.markdown(
            f"**Supporting:** {_chips(supporting, evidence)}  \n"
            f"**Counter-evidence:** {_chips(counter, evidence)}"
        )
        gaps = f.get("data_gaps") or []
        if gaps:
            st.caption("Data gaps: " + "; ".join(gaps))
        cited = [i for s in sentences for i in s.get("evidence_ids") or []] + supporting + counter
        n_rows, n_records = source_counts(list(dict.fromkeys(cited)), evidence)
        st.markdown(
            f"**Sources:** {n_rows} ledger row{'s' if n_rows != 1 else ''}, "
            f"{n_records} Crustdata record{'s' if n_records != 1 else ''}"
        )


def _body(out_dir: Path, inputs: dict) -> None:
    findings = _load_json(out_dir / "findings.json")
    if not isinstance(findings, list):
        if inputs.get("running"):
            st.info("Findings appear here once the gate has decided each allegation.")
        else:
            st.info("No findings yet. Pick a case and press Investigate.")
        return
    raw = _load_json(out_dir / "evidence.json") or []
    evidence = {e["evidence_id"]: e for e in raw if isinstance(e, dict) and "evidence_id" in e}
    findings = sorted(findings, key=lambda f: VERDICT_ORDER.get(f.get("verdict"), 3))

    counts = {v: sum(f.get("verdict") == v for f in findings) for v in VERDICT_ORDER}
    cols = st.columns(3)
    for col, (verdict, n) in zip(cols, counts.items(), strict=True):
        col.markdown(f"{_badge(verdict)}&nbsp; **{n}**", unsafe_allow_html=True)
    st.caption(
        "Verdicts are decided by coded rules (two independent kinds of evidence to substantiate); "
        "every sentence cites evidence you can open below it."
    )
    for f in findings:
        _card(f, evidence)
    _cleared(findings, out_dir, inputs)


def render(out_dir: Path, inputs: dict) -> None:
    out_dir = Path(out_dir)
    if inputs.get("running"):
        st.fragment(_body, run_every=1)(out_dir, inputs)
    else:
        _body(out_dir, inputs)
