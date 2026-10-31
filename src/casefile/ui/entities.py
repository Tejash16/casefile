"""Entities tab (b2): how every vendor and staff member resolved against Crustdata.

Reads only `out_dir/entities.json` (written by the pipeline after the resolve stage), plus
`findings.json` to know which staff the allegations name and `log.jsonl` as a fallback for the
credit count. Names arrive already redacted under --redact; this panel never redacts or edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

STATUS_BG = {
    "resolved": "#d1fae5",
    "ambiguous": "#fef3c7",
    "unresolved": "#fee2e2",
    "not_attempted": "#e5e7eb",
}
STATUS_HELP = (
    "**resolved**: one Crustdata record confirmed (domain, exact unique name, or LinkedIn URL) · "
    "**ambiguous**: several candidates, none confirmable · **unresolved**: no plausible record "
    "(a legal state: it only voids evidence that would rest on that record)"
)


# ---------------------------------------------------------------- reading (pure, testable)


def load_entities(out_dir: Path) -> dict[str, Any] | None:
    """entities.json as {"vendors": [...], "staff": [...], ...}, or None if not written yet."""
    p = Path(out_dir) / "entities.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, list):  # tolerate a bare list of records
        data = {
            "vendors": [x for x in data if isinstance(x, dict) and "vendor_id" in x],
            "staff": [x for x in data if isinstance(x, dict) and "staff_id" in x],
        }
    return data if isinstance(data, dict) else None


def log_crustdata_totals(out_dir: Path) -> tuple[float, int, int]:
    """(credits, calls, cache hits) for Crustdata tool calls in log.jsonl (it grows live)."""
    credits, calls, hits = 0.0, 0, 0
    p = Path(out_dir) / "log.jsonl"
    if not p.exists():
        return credits, calls, hits
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return credits, calls, hits
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # a line being written right now
        if rec.get("action_type") != "tool_call":
            continue
        if rec.get("record_phase") == "pre_execution":
            calls += 1
            hits += bool((rec.get("action_detail") or {}).get("cache_hit"))
        else:
            try:
                credits += float((rec.get("outcome") or {}).get("credits_used") or 0)
            except (TypeError, ValueError):
                pass
    return credits, calls, hits


def named_subjects(out_dir: Path) -> set[str]:
    """Staff ids any hypothesis or finding names (every `subjects` list in findings.json)."""
    p = Path(out_dir) / "findings.json"
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    found: set[str] = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("subjects", "subject_ids") and isinstance(v, list):
                    found.update(str(x) for x in v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    return found


def _res(rec: dict[str, Any]) -> dict[str, Any]:
    return rec.get("resolution") or {}


def _conf(r: dict[str, Any]) -> str:
    c = r.get("confidence")
    return "" if c is None else f"{float(c):.2f}"


def _cite(kind: str, facts: dict[str, Any] | None, id_key: str) -> str:
    if not facts:
        return ""
    return f"crustdata:{kind}:{facts.get(id_key)}@{facts.get('updated_at')}"


def vendor_rows(vendors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for v in vendors:
        r, cf = _res(v), v.get("crustdata") or {}
        rows.append(
            {
                "Vendor": v.get("vendor_id", ""),
                "Name as given": v.get("name_raw", ""),
                "Status": r.get("status", "not_attempted"),
                "Method": r.get("method") or "",
                "Confidence": _conf(r),
                "Candidates": r.get("candidates_considered", 0),
                "Crustdata id": cf.get("crustdata_company_id") or "",
                "Crustdata name": cf.get("name") or "",
                "Headcount": cf.get("headcount_total"),
                "Founded": cf.get("year_founded"),
                "Website": cf.get("website") or cf.get("primary_domain") or "",
                "Citation": _cite("company", cf, "crustdata_company_id"),
            }
        )
    return rows


def staff_rows(staff: list[dict[str, Any]], subjects: set[str]) -> list[dict[str, Any]]:
    rows = []
    for s in staff:
        r, pf = _res(s), s.get("crustdata") or {}
        rows.append(
            {
                "Staff": s.get("staff_id", ""),
                "Name as given": s.get("name_raw", ""),
                "Title": s.get("title") or "",
                "Named in allegation": "yes" if s.get("staff_id") in subjects else "",
                "Status": r.get("status", "not_attempted"),
                "Method": r.get("method") or "",
                "Confidence": _conf(r),
                "Candidates": r.get("candidates_considered", 0),
                "Crustdata id": pf.get("crustdata_person_id") or "",
                "Current role": " at ".join(
                    x for x in (pf.get("current_title"), pf.get("current_company")) if x
                ),
                "Citation": _cite("person", pf, "crustdata_person_id"),
            }
        )
    return rows


def employment_rows(person: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Company": e.get("company_name", ""),
            "Crustdata company id": e.get("crustdata_company_id") or "",
            "Title": e.get("title") or "",
            "From": e.get("start_date") or "",
            "To": e.get("end_date") or ("present" if e.get("is_current") else ""),
        }
        for e in person.get("employment") or []
    ]


# ---------------------------------------------------------------- drawing


def _table(rows: list[dict[str, Any]], key: str) -> None:
    if not rows:
        st.caption("none")
        return
    df = pd.DataFrame(rows)
    styled = df.style.map(
        lambda v: f"background-color: {STATUS_BG.get(v, '')}" if v in STATUS_BG else "",
        subset=["Status"],
    )
    st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        key=key,
        column_config={
            "Website": st.column_config.LinkColumn("Website"),
            "Headcount": st.column_config.NumberColumn("Headcount", format="%d"),
            "Founded": st.column_config.NumberColumn("Founded", format="%d"),
        },
    )


def _count(records: list[dict[str, Any]], status: str = "resolved") -> int:
    return sum(_res(r).get("status") == status for r in records)


def _draw(out_dir: Path, inputs: dict[str, Any]) -> None:
    data = load_entities(out_dir)
    if data is None:
        msg = (
            "Resolving vendors and staff against Crustdata..."
            if inputs.get("running")
            else ("No entities yet: run an investigation to see how vendors and staff resolve.")
        )
        st.info(msg)
        return
    vendors = [v for v in data.get("vendors") or [] if isinstance(v, dict)]
    staff = [s for s in data.get("staff") or [] if isinstance(s, dict)]
    credits, calls, hits = log_crustdata_totals(out_dir)
    if not calls:  # log not readable: fall back to the totals the pipeline wrote
        credits = float(data.get("credits_used") or 0)
        calls = int(data.get("crustdata_calls") or 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Crustdata credits used", f"{credits:g}")
    c2.metric("Crustdata calls", calls, help=f"{hits} served from the disk cache")
    c3.metric("Vendors resolved", f"{_count(vendors)}/{len(vendors)}")
    c4.metric("Staff resolved", f"{_count(staff)}/{len(staff)}")
    st.caption(STATUS_HELP)

    st.subheader("Vendors")
    _table(vendor_rows(vendors), key="b2_vendors")

    subjects = named_subjects(out_dir)
    st.subheader("Staff")
    _table(staff_rows(staff, subjects), key="b2_staff")

    people = [s for s in staff if (s.get("crustdata") or {}).get("employment")]
    if people:
        st.subheader("Employment history (Crustdata)")
        for s in sorted(people, key=lambda s: s.get("staff_id") not in subjects):
            pf = s["crustdata"]
            label = (
                f"{s.get('staff_id')} {s.get('name_raw', '')}: "
                f"{_cite('person', pf, 'crustdata_person_id')}"
            )
            with st.expander(label, expanded=s.get("staff_id") in subjects):
                st.dataframe(pd.DataFrame(employment_rows(pf)), hide_index=True, width="stretch")


def render(out_dir: Path, inputs: dict[str, Any]) -> None:
    """Entities tab. Polls every second while the pipeline thread is alive."""
    live = bool(inputs.get("running"))

    @st.fragment(run_every=1 if live else None)
    def _panel() -> None:
        _draw(Path(out_dir), inputs)

    _panel()
