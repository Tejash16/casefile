"""Entities tab (b2): how every vendor and staff member resolved against Crustdata.

Reads only `out_dir/entities.json` (written by the pipeline after the resolve stage), plus
`findings.json` to know which staff the allegations name and `log.jsonl` as a fallback for the
credit count. Names arrive already redacted under --redact; this panel never redacts or edits.
"""

from __future__ import annotations

import json
from functools import lru_cache
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
                "Crustdata: id": cf.get("crustdata_company_id") or "",
                "Crustdata: name": cf.get("name") or "",
                "Crustdata: headcount": cf.get("headcount_total"),
                "Crustdata: founded": cf.get("year_founded"),
                "Crustdata: website": cf.get("website") or cf.get("primary_domain") or "",
                "Crustdata: updated_at": cf.get("updated_at") or "",
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
                "Crustdata: id": pf.get("crustdata_person_id") or "",
                "Crustdata: current role": " at ".join(
                    x for x in (pf.get("current_title"), pf.get("current_company")) if x
                ),
                "Crustdata: updated_at": pf.get("updated_at") or "",
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
            "Crustdata: website": st.column_config.LinkColumn("Crustdata: website"),
            "Crustdata: headcount": st.column_config.NumberColumn(
                "Crustdata: headcount", format="%d"
            ),
            "Crustdata: founded": st.column_config.NumberColumn("Crustdata: founded", format="%d"),
        },
    )


VENDOR_PATH = {
    "domain": "POST /company/identify (by website domain) → POST /company/enrich → "
    "POST /company/search (record updated_at)",
    "identify_exact": "POST /company/identify (exact name) → POST /company/enrich → "
    "POST /company/search (record updated_at)",
    "identify_fuzzy": "POST /company/identify (fuzzy name) → POST /company/enrich → "
    "POST /company/search (record updated_at)",
    "llm_judge": "POST /company/identify → match judge on the tie list → POST /company/enrich → "
    "POST /company/search (record updated_at)",
}
STAFF_PATH = {
    "linkedin_url": "POST /person/enrich (LinkedIn URL from the staff list)",
    "person_search": "POST /person/search (exact name + audited company) → POST /person/enrich",
    "llm_judge": "POST /person/search → match judge on the shortlist → POST /person/enrich",
    "person_identify_email": "POST /person/identify (email) → POST /person/enrich",
}


def record_lines(rec: dict[str, Any], kind: str) -> list[str]:
    """What the 'Crustdata record' expander says for one vendor or staff row."""
    r, facts = _res(rec), rec.get("crustdata") or {}
    status, method = r.get("status", "not_attempted"), r.get("method")
    paths = VENDOR_PATH if kind == "company" else STAFF_PATH
    if method in paths:
        path = paths[method]
    elif kind == "company":
        path = "POST /company/identify (domain, then exact and fuzzy name): no record accepted"
    else:
        path = "POST /person/search (name + audited company, then name only): no record accepted"
    id_key = "crustdata_company_id" if kind == "company" else "crustdata_person_id"
    lines = [
        f"**Endpoints:** {path}",
        f"**Resolution:** {status}" + (f" by `{method}`" if method else ""),
        f"**confidence_score:** {_conf(r) or 'n/a'} · "
        f"**candidates considered:** {r.get('candidates_considered', 0)}",
    ]
    if facts:
        lines += [
            f"**Crustdata id:** `{facts.get(id_key)}` · "
            f"**updated_at:** `{facts.get('updated_at')}`",
            f"**X-Request-Id:** `{facts.get('source_request_id') or 'n/a'}` · "
            f"**served from cache:** {'yes' if facts.get('cache_hit') else 'no'}",
            f"**Citation:** `{_cite(kind, facts, id_key)}`",
        ]
    return lines


def _records(records: list[dict[str, Any]], kind: str, id_key: str) -> None:
    for rec in records:
        status = _res(rec).get("status", "not_attempted")
        with st.expander(
            f"Crustdata record · {rec.get(id_key)} {rec.get('name_raw', '')} ({status})"
        ):
            st.markdown("  \n".join(record_lines(rec, kind)))


# ---------------------------------------------------------------- timeline


@lru_cache(maxsize=8)
def _first_payments(ledger: str, ledger_mtime: float, ents: str, ents_mtime: float) -> dict:
    """vendor_id -> date of its first payment, via the project's own ledger loader (read only)."""
    from casefile.ingest import link_ledger, load_ledger
    from casefile.schemas import StaffRecord, VendorRecord

    data = json.loads(Path(ents).read_text(encoding="utf-8"))
    vendors = [VendorRecord.model_validate(v) for v in data.get("vendors") or []]
    staff = [StaffRecord.model_validate(s) for s in data.get("staff") or []]
    rows, _ = load_ledger(ledger)
    out: dict[str, Any] = {}
    for row in link_ledger(rows, vendors, staff):
        if row.vendor_id and row.amount > 0:
            out[row.vendor_id] = min(out.get(row.vendor_id, row.date), row.date)
    return out


def first_payments(out_dir: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    ledger = Path(inputs.get("ledger") or Path(out_dir) / "ledger.csv")
    ents = Path(out_dir) / "entities.json"
    if not ledger.exists() or not ents.exists():
        return {}
    try:
        return _first_payments(str(ledger), ledger.stat().st_mtime, str(ents), ents.stat().st_mtime)
    except Exception:  # noqa: BLE001 - a marker is a nicety; never break the tab
        return {}


def subject_vendors(out_dir: Path) -> dict[str, set[str]]:
    """staff_id -> vendor ids it is paired with in any finding."""
    p = Path(out_dir) / "findings.json"
    pairs: dict[str, set[str]] = {}
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except (OSError, ValueError):
        return pairs
    for f in data if isinstance(data, list) else data.get("findings", []):
        if isinstance(f, dict):
            for s in f.get("subjects") or []:
                pairs.setdefault(str(s), set()).update(str(o) for o in f.get("objects") or [])
    return pairs


def _timeline(
    person: dict[str, Any],
    vendors: list[dict[str, Any]],
    paired: set[str],
    paid: dict[str, Any],
) -> None:
    import altair as alt

    today = pd.Timestamp.today().normalize()
    vendor_ids = {
        (v.get("crustdata") or {}).get("crustdata_company_id"): v.get("vendor_id")
        for v in vendors
        if v.get("crustdata")
    }
    bars = []
    linked: set[str] = set()
    for e in person.get("employment") or []:
        if not e.get("start_date"):
            continue
        vid = vendor_ids.get(e.get("crustdata_company_id"))
        if vid:
            linked.add(vid)
        bars.append(
            {
                "Role": f"{e.get('company_name', '')}: {e.get('title') or ''}",
                "start": pd.Timestamp(e["start_date"]),
                "end": pd.Timestamp(e["end_date"]) if e.get("end_date") else today,
                "Employer is a vendor": f"yes ({vid})" if vid else "no",
            }
        )
    if not bars:
        st.caption("No dated roles in the Crustdata record.")
        return
    names = {v.get("vendor_id"): v.get("name_raw", "") for v in vendors}
    marks = [
        {"date": pd.Timestamp(paid[v]), "label": f"first payment to {v} {names.get(v, '')}"}
        for v in sorted(linked | paired)
        if v in paid
    ][:4]
    base = (
        alt.Chart(pd.DataFrame(bars))
        .mark_bar(height=18)
        .encode(
            x=alt.X("start:T", title=None),
            x2="end:T",
            y=alt.Y("Role:N", sort=None, title=None),
            color=alt.condition(
                alt.datum["Employer is a vendor"] != "no",
                alt.value("#7c3aed"),
                alt.value("#94a3b8"),
            ),
            tooltip=["Role", "start:T", "end:T", "Employer is a vendor"],
        )
    )
    chart = base
    if marks:
        m = pd.DataFrame(marks)
        rule = (
            alt.Chart(m)
            .mark_rule(color="#dc2626", strokeDash=[6, 3], size=2)
            .encode(x="date:T", tooltip=["label", "date:T"])
        )
        text = (
            alt.Chart(m)
            .mark_text(align="left", dx=5, dy=-4, color="#dc2626")
            .encode(x="date:T", y=alt.value(8), text="label")
        )
        chart = base + rule + text
    st.altair_chart(chart.properties(height=40 * len(bars) + 60), use_container_width=True)
    if linked:
        st.caption(
            f"Crustdata lists an employer that is also a paid vendor: {', '.join(sorted(linked))}."
        )
    elif paired:
        st.caption(
            f"No role at {', '.join(sorted(paired))} in the Crustdata record "
            "(the allegation names it)."
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

    subjects = named_subjects(out_dir)
    people = [s for s in staff if (s.get("crustdata") or {}).get("employment")]
    if people:
        # the hidden link, on screen: Crustdata career timeline vs first payment to the vendor
        st.subheader("Crustdata employment timeline: staff named in an allegation")
        pairs, paid = subject_vendors(out_dir), first_payments(out_dir, inputs)
        for s in sorted(people, key=lambda s: s.get("staff_id") not in subjects):
            pf = s["crustdata"]
            label = (
                f"{s.get('staff_id')} {s.get('name_raw', '')}: "
                f"{_cite('person', pf, 'crustdata_person_id')}"
            )
            with st.expander(label, expanded=s.get("staff_id") in subjects):
                try:
                    _timeline(pf, vendors, pairs.get(str(s.get("staff_id")), set()), paid)
                except Exception as e:  # noqa: BLE001 - the table below still shows the facts
                    st.caption(f"timeline unavailable ({type(e).__name__})")
                st.dataframe(pd.DataFrame(employment_rows(pf)), hide_index=True, width="stretch")

    st.subheader("Vendors")
    _table(vendor_rows(vendors), key="b2_vendors")
    st.caption("Crustdata record per vendor: endpoints called, confidence, id, updated_at")
    _records(vendors, "company", "vendor_id")

    st.subheader("Staff")
    _table(staff_rows(staff, subjects), key="b2_staff")
    st.caption("Crustdata record per staff member: endpoints called, confidence, id, updated_at")
    _records(staff, "person", "staff_id")


def render(out_dir: Path, inputs: dict[str, Any]) -> None:
    """Entities tab. Polls every second while the pipeline thread is alive."""
    live = bool(inputs.get("running"))

    @st.fragment(run_every=1 if live else None)
    def _panel() -> None:
        _draw(Path(out_dir), inputs)

    _panel()
