"""Inputs tab (b1): the tip, the three CSVs as received with every coerced cell highlighted, and
ingest's data-quality notes. Reads only the copies app.py puts in out_dir; re-parses them with
casefile.ingest (pure, milliseconds), never the pipeline. Under redact, staff names become initials.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from casefile.ingest import link_ledger, load_staff, load_tip, load_vendors
from casefile.ingest.csv import LEDGER_SYNONYMS, STAFF_SYNONYMS, VENDOR_SYNONYMS, read_table
from casefile.ingest.load import FLAG_TEXT, load_ledger_lines
from casefile.report.redact import NoRedaction, Redactor

FILES = {"tip": "tip.txt", "ledger": "ledger.csv", "vendors": "vendors.csv", "staff": "staff.csv"}
HIGHLIGHT = "background-color: #fff3bf"
# ledger column shown -> prefix of the quality flags that concern it
CELL_FLAGS = {
    "date as given": "date_",
    "amount as given": "amount_",
    "supplier as given": "vendor_",
    "approver as given": "approver_",
    "posted at": "posted_at_",
}
# "vendors.csv: V023 phone '...' normalised to ..." -> (id, field)
NOTE_FIELD = re.compile(r"^[\w.]+: (?P<id>[VS]\d+[\w-]*) (?P<field>[a-z_]+) ")
NOTE_FIELD_TO_COLUMN = {"name": "name_raw"}
PERSON_COLUMNS = {"name_raw", "email", "linkedin_url", "created_by"}


def render(out_dir: Path, inputs: dict) -> None:
    paths = {k: Path(inputs.get(k) or Path(out_dir) / f) for k, f in FILES.items()}
    live = bool(inputs.get("running")) and not all(p.exists() for p in paths.values())
    st.fragment(run_every=1 if live else None)(_body)(paths, bool(inputs.get("redact")))


def _body(paths: dict[str, Path], redact: bool) -> None:
    missing = [FILES[k] for k, p in paths.items() if not p.exists()]
    if len(missing) == len(paths):
        st.info("The tip and the three CSVs appear here as soon as a case is picked and run.")
        return
    if missing:
        st.info(f"Waiting for {', '.join(missing)}.")
        return
    vendors, vendor_notes = load_vendors(paths["vendors"])
    staff, staff_notes = load_staff(paths["staff"])
    rows, ledger_notes, lines = load_ledger_lines(paths["ledger"])
    rows = link_ledger(rows, vendors, staff)
    red: Any = (
        Redactor([s.name_norm for s in staff], keep=[v.name_raw for v in vendors])
        if redact
        else NoRedaction()
    )
    notes = [red(n) for n in ledger_notes + vendor_notes + staff_notes]

    _headline(rows, vendors, ledger_notes)

    st.markdown("#### Anonymous tip, as received")
    st.text_area(
        "tip",
        red(load_tip(paths["tip"]).text),
        height=170,
        disabled=True,
        label_visibility="collapsed",
    )

    st.markdown("#### Data quality: what ingest coerced, and why")
    for line in _summary(rows, vendors, ledger_notes):
        st.markdown(f"- {line}")
    with st.expander(f"All {len(notes)} data-quality notes"):
        for n in notes:
            st.markdown(f"- {n}")

    st.markdown("#### The three files as received")
    st.caption("Highlighted cells were coerced or linked fuzzily; the flag names say how.")
    tab_l, tab_v, tab_s = st.tabs(
        [f"Ledger ({len(rows)} rows)", f"Vendors ({len(vendors)})", f"Staff ({len(staff)})"]
    )
    with tab_l:
        only = st.checkbox("Only rows with a coercion", value=False, key="b1_only_flagged")
        df = _ledger_frame(paths["ledger"], rows, lines, staff, red)
        if only:
            df = df[df["quality flags"] != ""]
        st.dataframe(df.style.apply(_ledger_style, axis=1), hide_index=True, width="stretch")
    with tab_v:
        _master_table(paths["vendors"], VENDOR_SYNONYMS, "vendor_id", vendor_notes, red)
    with tab_s:
        _master_table(paths["staff"], STAFF_SYNONYMS, "staff_id", staff_notes, red)


def _headline(rows, vendors, ledger_notes: list[str]) -> None:
    flagged = sum(1 for r in rows if r.quality_flags)
    raw_names = {r.vendor_name_raw.strip() for r in rows if r.vendor_id}
    dropped = sum(_count(n, r"(\d+) (?:blank row|repeated header)") for n in ledger_notes)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ledger rows loaded", len(rows))
    c2.metric("Rows with a coercion", flagged)
    c3.metric("Vendor spellings → vendors", f"{len(raw_names)} → {len(vendors)}")
    c4.metric("Junk rows dropped", dropped)


def _summary(rows, vendors, ledger_notes: list[str]) -> list[str]:
    flags = Counter(f for r in rows for f in r.quality_flags)
    names = {v.vendor_id: v.name_raw for v in vendors}
    merged: dict[str, set[str]] = {}
    for r in rows:
        if r.vendor_id and r.vendor_name_raw.strip() != names.get(r.vendor_id):
            merged.setdefault(r.vendor_id, set()).add(r.vendor_name_raw.strip())
    out = []
    if merged:
        n = sum(len(s) for s in merged.values())
        vid, spellings = max(merged.items(), key=lambda kv: len(kv[1]))
        example = ", ".join(f"“{s}”" for s in sorted(spellings)[:3])
        out.append(
            f"**{n} vendor spellings merged** into {len(merged)} vendors "
            f"(e.g. {example} → {vid} “{names[vid]}”)."
        )
    for flag, label in (
        ("date_coerced", FLAG_TEXT["date_coerced"]),
        ("date_ambiguous_dayfirst", FLAG_TEXT["date_ambiguous_dayfirst"]),
        ("amount_lakh_format", FLAG_TEXT["amount_lakh_format"]),
        ("amount_currency_symbol", FLAG_TEXT["amount_currency_symbol"]),
        ("vendor_fuzzy_match", FLAG_TEXT["vendor_fuzzy_match"]),
        ("approver_initials_match", FLAG_TEXT["approver_initials_match"]),
        ("vendor_unlinked", FLAG_TEXT["vendor_unlinked"]),
        ("approver_unlinked", FLAG_TEXT["approver_unlinked"]),
    ):
        if flags[flag]:
            out.append(f"**{flags[flag]}** {label} (`{flag}`).")
    for n in ledger_notes:
        if any(k in n for k in ("byte-order mark", "blank row", "repeated header", "whitespace")):
            out.append(n.split(": ", 1)[1])
    return out


def _ledger_frame(path: Path, rows, lines: list[int], staff, red) -> pd.DataFrame:
    raw = read_table(path, LEDGER_SYNONYMS)
    by_line = dict(zip(raw.line_numbers, raw.rows, strict=True))
    label = {s.staff_id: red(s.name_norm.title()) for s in staff}
    data = []
    for r, line in zip(rows, lines, strict=True):
        rec = by_line.get(line, {})
        approver = rec.get("approver_name_raw", "")
        if not isinstance(red, NoRedaction) and approver:
            approver = label.get(r.approver_id) or red(approver)
        data.append(
            {
                "line": line,
                "row_id": r.row_id,
                "date as given": rec.get("date", ""),
                "date": r.date.isoformat(),
                "supplier as given": rec.get("vendor_name_raw", ""),
                "vendor": r.vendor_id or "unlinked",
                "invoice": r.invoice_no or "",
                "amount as given": rec.get("amount", ""),
                "amount INR": f"{r.amount:,.2f}",
                "approver as given": approver,
                "approver": r.approver_id or "",
                "posted at": rec.get("posted_at", ""),
                "quality flags": ", ".join(r.quality_flags),
            }
        )
    return pd.DataFrame(data)


def _ledger_style(row: pd.Series) -> list[str]:
    flags = row["quality flags"].split(", ") if row["quality flags"] else []
    return [
        HIGHLIGHT if col in CELL_FLAGS and any(f.startswith(CELL_FLAGS[col]) for f in flags) else ""
        for col in row.index
    ]


def _master_table(path: Path, synonyms: dict, id_col: str, notes: list[str], red) -> None:
    table = read_table(path, synonyms)
    df = pd.DataFrame(table.rows).drop(columns=[c for c in table.columns if c.startswith("_x_")])
    for col in PERSON_COLUMNS & set(df.columns):
        df[col] = df[col].map(red)
    touched: set[tuple[str, str]] = set()
    for n in notes:
        m = NOTE_FIELD.match(n)
        if m:
            field = NOTE_FIELD_TO_COLUMN.get(m["field"], m["field"])
            touched.add((m["id"], field))
    if id_col not in df.columns:
        st.dataframe(df, hide_index=True, width="stretch")
        return

    def style(row: pd.Series) -> list[str]:
        return [HIGHLIGHT if (row[id_col], col) in touched else "" for col in row.index]

    st.dataframe(df.style.apply(style, axis=1), hide_index=True, width="stretch")
    if touched:
        st.caption(f"{len(touched)} highlighted cells were normalised; see the notes above.")


def _count(text: str, pattern: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0
