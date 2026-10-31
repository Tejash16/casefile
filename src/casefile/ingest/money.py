"""Amount parsing: rupee symbols, lakh grouping, parentheses negatives, all to Decimal."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_CURRENCY = re.compile(r"(₹|\bINR\b|\bRs\.?(?=\s|\d|$))", re.IGNORECASE)
_LAKH = re.compile(r"^\d{1,2}(,\d{2})*,\d{3}(\.\d+)?$")  # 4,98,000 / 18,47,350.00
_THOUSANDS = re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$")  # 498,000


def parse_amount(raw: str | None) -> tuple[Decimal | None, list[str]]:
    """Parse one amount cell. Returns (Decimal or None, flags)."""
    s = (raw or "").strip()
    if not s:
        return None, ["amount_missing"]
    flags: list[str] = []
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1].strip()
        flags.append("amount_negative_parens")
    if _CURRENCY.search(s):
        s = _CURRENCY.sub("", s).strip()
        flags.append("amount_currency_symbol")
    if s.startswith("-"):
        negative, s = not negative, s[1:].strip()
    s = s.replace(" ", "")
    if "," in s:
        lakh, thousands = bool(_LAKH.match(s)), bool(_THOUSANDS.match(s))
        if lakh and thousands:  # below 1,00,000 both groupings agree: 12,345
            flags.append("amount_comma_grouping")
        elif lakh:
            flags.append("amount_lakh_format")
        elif thousands:
            flags.append("amount_thousands_format")
        else:
            flags.append("amount_irregular_commas")
        s = s.replace(",", "")
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None, [*flags, "amount_unparseable"]
    return (-value if negative else value), flags
