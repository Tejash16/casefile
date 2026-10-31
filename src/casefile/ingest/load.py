"""Loaders: tip, ledger, vendor master, staff list -> contract models plus data-quality notes.

Every coercion is recorded: on the row as a `quality_flags` entry (ledger), and in the notes as a
human sentence. Rows that cannot carry a date or an amount are dropped and named in the notes.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from casefile.ingest.csv import (
    LEDGER_SYNONYMS,
    STAFF_SYNONYMS,
    VENDOR_SYNONYMS,
    Table,
    decode,
    read_table,
)
from casefile.ingest.dates import parse_date, parse_datetime
from casefile.ingest.money import parse_amount
from casefile.ingest.names import (
    normalize_company_name,
    normalize_linkedin_url,
    normalize_person_name,
    normalize_phone,
    normalize_website,
)
from casefile.schemas import AddressType, LedgerRow, StaffRecord, Tip, VendorRecord

# Human sentence per flag, used to summarise row flags in the notes
FLAG_TEXT: dict[str, str] = {
    "date_coerced": "dates in a non-ISO format converted to YYYY-MM-DD",
    "date_two_digit_year": "dates with a two-digit year read as 20YY",
    "date_ambiguous_dayfirst": "dates where day and month could swap, read day-first",
    "date_dateutil": "dates parsed by the fallback parser",
    "amount_lakh_format": "amounts in lakh grouping (4,98,000)",
    "amount_thousands_format": "amounts in thousands grouping (498,000)",
    "amount_comma_grouping": "amounts with comma grouping",
    "amount_irregular_commas": "amounts with irregular comma grouping",
    "amount_currency_symbol": "amounts with a currency symbol (₹, Rs., INR) stripped",
    "amount_negative_parens": "amounts in parentheses read as negative",
    "posted_at_coerced": "posting timestamps in a non-ISO format",
    "posted_at_unparseable": "posting timestamps that could not be parsed (left empty)",
    "vendor_name_whitespace": "vendor names with extra whitespace",
    "vendor_spelling_variant": "vendor names spelled differently from the vendor master",
    "vendor_fuzzy_match": "vendor names linked to the master by fuzzy match",
    "vendor_unlinked": "vendor names that match no vendor in the master",
    "approver_spelling_variant": "approver names spelled differently from the staff list",
    "approver_initials_match": "approver names linked through initials",
    "approver_unlinked": "approver names that match no one in the staff list",
}

_DEFAULT_COWORKING = [
    "wework",
    "regus",
    "awfis",
    "91springboard",
    "innov8",
    "smartworks",
    "cowrks",
    "indiqube",
    "spaces",
    "table space",
    "bhive",
    "coworking",
    "co-working",
    "workafella",
    "starthub",
]
_RESIDENTIAL = [
    "flat",
    "apartment",
    "apartments",
    "apts",
    "apt",
    "chs",
    "society",
    "bungalow",
    "row house",
    "villa",
    "residency",
    "nagar colony",
    "house no",
    "h no",
]
_PO_BOX = ["po box", "p o box", "p.o. box", "post box", "pob "]
_VIRTUAL = ["virtual office", "registered agent", "mail drop"]
_COMMERCIAL = [
    "plot",
    "midc",
    "industrial",
    "sez",
    "tower",
    "towers",
    "park",
    "complex",
    "estate",
    "centre",
    "center",
    "campus",
    "market",
    "shop",
    "office",
    "house",
    "street",
    "road",
    "chowk",
    "gidc",
    "phase",
]


def _coworking_markers() -> list[str]:
    """`THRESHOLDS.coworking_markers` from b3's rules/config when it exists, else a local list."""
    try:
        from casefile.rules.config import THRESHOLDS  # type: ignore[attr-defined]

        value = THRESHOLDS["coworking_markers"].value
        return [str(v).lower() for v in value]
    except (ImportError, KeyError, AttributeError, TypeError):
        return _DEFAULT_COWORKING


def classify_address(address: str | None) -> AddressType:
    """Heuristic address type from text. Coworking wins over commercial."""
    if not address or not address.strip():
        return AddressType.unknown
    s = " " + " ".join(address.lower().replace(",", " ").split()) + " "
    compact = re.sub(r"[^a-z0-9]", "", s)  # "We Work" and "WeWork" alike
    if any(re.sub(r"[^a-z0-9]", "", m) in compact for m in _coworking_markers()):
        return AddressType.coworking
    if any(f" {m} " in s or s.strip().startswith(m) for m in _PO_BOX):
        return AddressType.po_box
    if any(m in s for m in _VIRTUAL):
        return AddressType.virtual
    if any(f" {m} " in s or f" {m}." in s for m in _RESIDENTIAL):
        return AddressType.residential
    if any(f" {m} " in s for m in _COMMERCIAL):
        return AddressType.commercial
    return AddressType.unknown


def _clean(v: str | None) -> str | None:
    s = (v or "").strip()
    return s or None


def _summarise_flags(name: str, flagged: dict[str, list[str]]) -> list[str]:
    notes = []
    for flag, ids in flagged.items():
        text = FLAG_TEXT.get(flag, flag)
        shown = ", ".join(ids[:8]) + (f" and {len(ids) - 8} more" if len(ids) > 8 else "")
        notes.append(f"{name}: {len(ids)} {text} [{flag}]: {shown}.")
    return notes


# ---------------------------------------------------------------- tip


def load_tip(path: str | Path) -> Tip:
    p = Path(path)
    raw = p.read_bytes()
    text, _ = decode(raw, p.name)
    received = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    return Tip(
        text=text.replace("\r\n", "\n").strip(),
        received_at=received.isoformat(timespec="seconds"),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


# ---------------------------------------------------------------- ledger


def load_ledger(path: str | Path) -> tuple[list[LedgerRow], list[str]]:
    rows, notes, _ = load_ledger_lines(path)
    return rows, notes


def load_ledger_lines(path: str | Path) -> tuple[list[LedgerRow], list[str], list[int]]:
    """`load_ledger` plus the 1-based physical file line of each loaded row (for the UI)."""
    table = read_table(path, LEDGER_SYNONYMS)
    notes = list(table.notes)
    _require(table, ["date", "vendor_name_raw", "amount"], notes)
    rows: list[LedgerRow] = []
    lines: list[int] = []
    flagged: dict[str, list[str]] = defaultdict(list)
    dropped: list[str] = []
    for rec, line in zip(table.rows, table.line_numbers, strict=True):
        row_id = f"L{len(rows) + 1:06d}"
        flags: list[str] = []
        d, f = parse_date(rec.get("date"))
        flags += f
        amount, f = parse_amount(rec.get("amount"))
        flags += f
        vendor_raw = rec.get("vendor_name_raw") or ""
        if d is None or amount is None or not vendor_raw.strip():
            why = [x for x in flags if x.endswith(("_missing", "_unparseable"))]
            dropped.append(f"line {line} ({', '.join(why) or 'vendor_missing'})")
            continue
        if vendor_raw != vendor_raw.strip() or "  " in vendor_raw:
            flags.append("vendor_name_whitespace")
        posted_at, f = parse_datetime(rec.get("posted_at"))
        flags += f
        currency = (_clean(rec.get("currency")) or "INR").upper()
        rows.append(
            LedgerRow(
                row_id=row_id,
                date=d,
                vendor_name_raw=vendor_raw,
                vendor_key=normalize_company_name(vendor_raw),
                invoice_no=_clean(rec.get("invoice_no")),
                amount=amount,
                currency=currency,
                approver_name_raw=_clean(rec.get("approver_name_raw")),
                created_by=_clean(rec.get("created_by")),
                posted_at=posted_at,
                description=_clean(rec.get("description")),
                po_number=_clean(rec.get("po_number")),
                bank_account=_clean(rec.get("bank_account")),
                quality_flags=flags,
            )
        )
        lines.append(line)
        for x in flags:
            flagged[x].append(row_id)
    if dropped:
        notes.append(
            f"{table.name}: {len(dropped)} row(s) dropped for a missing date, amount or vendor: "
            f"{'; '.join(dropped)}."
        )
    notes += _summarise_flags(table.name, flagged)
    notes.append(f"{table.name}: {len(rows)} ledger rows loaded as L000001-L{len(rows):06d}.")
    return rows, notes, lines


# ---------------------------------------------------------------- vendors


def load_vendors(path: str | Path) -> tuple[list[VendorRecord], list[str]]:
    table = read_table(path, VENDOR_SYNONYMS)
    notes = list(table.notes)
    _require(table, ["name_raw"], notes)
    vendors: list[VendorRecord] = []
    seen: set[str] = set()
    for i, (rec, line) in enumerate(zip(table.rows, table.line_numbers, strict=True), start=1):
        name_raw = (rec.get("name_raw") or "").strip()
        if not name_raw:
            notes.append(f"{table.name}: line {line} has no vendor name; dropped.")
            continue
        vid = _clean(rec.get("vendor_id")) or f"V{900 + i:03d}"
        if not _clean(rec.get("vendor_id")):
            notes.append(
                f"{table.name}: line {line} ({name_raw}) has no vendor code; assigned {vid}."
            )
        if vid in seen:
            notes.append(
                f"{table.name}: vendor code {vid} appears twice (line {line}); "
                f"second kept as {vid}-dup."
            )
            vid = f"{vid}-dup"
        seen.add(vid)
        created_on, f = parse_date(rec.get("created_on"))
        _note_field(notes, table.name, vid, "created_on", rec.get("created_on"), created_on, f)
        address = _clean(rec.get("address"))
        phone = normalize_phone(rec.get("phone"))
        website = normalize_website(rec.get("website"))
        _note_change(notes, table.name, vid, "phone", rec.get("phone"), phone)
        _note_change(notes, table.name, vid, "website", rec.get("website"), website)
        vendors.append(
            VendorRecord(
                vendor_id=vid,
                name_raw=name_raw,
                name_norm=normalize_company_name(name_raw),
                address=address,
                address_type=classify_address(address),
                city=_clean(rec.get("city")),
                state=_clean(rec.get("state")),
                country=_clean(rec.get("country")),
                phone=phone,
                email=(_clean(rec.get("email")) or "").lower() or None,
                website=website,
                tax_id=(_clean(rec.get("tax_id")) or "").upper() or None,
                bank_account=_clean(rec.get("bank_account")),
                created_on=created_on,
                created_by=_clean(rec.get("created_by")),
            )
        )
    notes.append(f"{table.name}: {len(vendors)} vendors loaded.")
    return vendors, notes


# ---------------------------------------------------------------- staff


def load_staff(path: str | Path) -> tuple[list[StaffRecord], list[str]]:
    table = read_table(path, STAFF_SYNONYMS)
    notes = list(table.notes)
    _require(table, ["name_raw"], notes)
    staff: list[StaffRecord] = []
    for i, (rec, line) in enumerate(zip(table.rows, table.line_numbers, strict=True), start=1):
        name_raw = (rec.get("name_raw") or "").strip()
        if not name_raw:
            notes.append(f"{table.name}: line {line} has no name; dropped.")
            continue
        sid = _clean(rec.get("staff_id")) or f"S{900 + i:03d}"
        if not _clean(rec.get("staff_id")):
            notes.append(f"{table.name}: line {line} ({name_raw}) has no staff id; assigned {sid}.")
        name_norm = normalize_person_name(name_raw)
        if name_norm.split() != name_raw.lower().split():
            notes.append(f"{table.name}: {sid} name {name_raw!r} normalised to {name_norm!r}.")
        joined_on, f = parse_date(rec.get("joined_on"))
        _note_field(notes, table.name, sid, "joined_on", rec.get("joined_on"), joined_on, f)
        limit: Decimal | None = None
        if _clean(rec.get("approval_limit")):
            limit, f = parse_amount(rec.get("approval_limit"))
            if f:
                notes.append(
                    f"{table.name}: {sid} approval_limit {rec.get('approval_limit')!r} "
                    f"read as {limit} [{', '.join(f)}]."
                )
        phone = normalize_phone(rec.get("phone"))
        _note_change(notes, table.name, sid, "phone", rec.get("phone"), phone)
        linkedin = normalize_linkedin_url(rec.get("linkedin_url"))
        _note_change(notes, table.name, sid, "linkedin_url", rec.get("linkedin_url"), linkedin)
        staff.append(
            StaffRecord(
                staff_id=sid,
                name_raw=name_raw,
                name_norm=name_norm,
                title=_clean(rec.get("title")),
                department=_clean(rec.get("department")),
                address=_clean(rec.get("address")),
                phone=phone,
                email=(_clean(rec.get("email")) or "").lower() or None,
                bank_account=_clean(rec.get("bank_account")),
                joined_on=joined_on,
                approval_limit=limit,
                linkedin_url=linkedin,
            )
        )
    notes.append(f"{table.name}: {len(staff)} staff loaded.")
    return staff, notes


# ---------------------------------------------------------------- helpers


def _require(table: Table, cols: list[str], notes: list[str]) -> None:
    missing = [c for c in cols if c not in table.columns]
    if missing:
        notes.append(f"{table.name}: required column(s) not found: {', '.join(missing)}.")


def _note_field(notes, name, ident, fieldname, raw, parsed, flags) -> None:
    raw = (raw or "").strip()
    if not raw:
        return
    if parsed is None:
        notes.append(f"{name}: {ident} {fieldname} {raw!r} could not be parsed; left empty.")
    elif flags:
        notes.append(
            f"{name}: {ident} {fieldname} {raw!r} read as {parsed.isoformat()} "
            f"[{', '.join(flags)}]."
        )


def _note_change(notes, name, ident, fieldname, raw, value) -> None:
    raw = (raw or "").strip()
    if raw and raw != value:
        notes.append(f"{name}: {ident} {fieldname} {raw!r} normalised to {value!r}.")
