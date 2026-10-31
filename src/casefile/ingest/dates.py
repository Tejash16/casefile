"""Date parsing for Indian ledgers: explicit formats first, then dateutil with dayfirst=True.

Every parse returns the flags it raised, so the caller can record each coercion on the row.
"""

from __future__ import annotations

from datetime import date, datetime

from dateutil import parser as du_parser

# (format, extra flags). ISO is the only format that raises no flag.
_DATE_FORMATS: list[tuple[str, tuple[str, ...]]] = [
    ("%Y-%m-%d", ()),
    ("%d/%m/%Y", ("date_coerced",)),
    ("%d-%m-%Y", ("date_coerced",)),
    ("%d.%m.%Y", ("date_coerced",)),
    ("%d-%b-%y", ("date_coerced", "date_two_digit_year")),
    ("%d-%b-%Y", ("date_coerced",)),
    ("%d %b %Y", ("date_coerced",)),
    ("%d %B %Y", ("date_coerced",)),
    ("%d/%m/%y", ("date_coerced", "date_two_digit_year")),
    ("%Y/%m/%d", ("date_coerced",)),
]

# Numeric day-first formats where swapping day and month would also give a valid date
_NUMERIC_DAYFIRST = {"%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"}


def parse_date(raw: str | None) -> tuple[date | None, list[str]]:
    """Parse one date cell. Returns (date or None, flags)."""
    s = (raw or "").strip()
    if not s:
        return None, ["date_missing"]
    for fmt, flags in _DATE_FORMATS:
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        out = list(flags)
        if fmt in _NUMERIC_DAYFIRST and d.day <= 12 and d.day != d.month:
            out.append("date_ambiguous_dayfirst")
        return d, out
    try:
        d = du_parser.parse(s, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None, ["date_unparseable"]
    return d, ["date_coerced", "date_dateutil"]


def parse_datetime(raw: str | None) -> tuple[datetime | None, list[str]]:
    """Parse a posting timestamp. ISO (`2025-01-18 23:12`) raises no flag."""
    s = (raw or "").strip()
    if not s:
        return None, []
    try:
        return datetime.fromisoformat(s), []
    except ValueError:
        pass
    try:
        return du_parser.parse(s, dayfirst=True), ["posted_at_coerced"]
    except (ValueError, OverflowError):
        return None, ["posted_at_unparseable"]
