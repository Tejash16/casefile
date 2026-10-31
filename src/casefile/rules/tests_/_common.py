"""Helpers shared by the rule tests."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pandas as pd

from casefile.rules.context import RuleContext
from casefile.schemas import LedgerRow

_TRAILING_INT = re.compile(r"(\d+)\D*$")


def vendor_groups(ctx: RuleContext) -> Iterator[tuple[str, pd.DataFrame]]:
    """(vendor_id, rows) for linked rows, vendor ids in sorted order, rows in date order."""
    df = ctx.rows[ctx.rows.vendor_id.notna()]
    yield from df.groupby("vendor_id", sort=True)


def ledger_rows(ctx: RuleContext, g: pd.DataFrame) -> list[LedgerRow]:
    return [ctx.ledger[r] for r in g.row_id]


def rest_share(mask: pd.Series, vendor_ids: pd.Series, vid: str) -> float:
    """Share of True in `mask` over every row not belonging to `vid` (the population)."""
    other = vendor_ids != vid
    return float(mask[other].mean()) if other.any() else 0.0


def elevated(share: float, rest: float, ratio: float) -> bool:
    """Vendor share at least `ratio` x the population's (capped at 100%) and above it."""
    return share > rest and share >= min(1.0, ratio * rest)


def invoice_key(s: str | None) -> str | None:
    """`SFL/24-25/0457` and `sfl 24-25 0457` compare equal."""
    if not s:
        return None
    k = re.sub(r"[^A-Z0-9]", "", s.upper())
    return k or None


def invoice_number(s: str | None) -> int | None:
    """Trailing integer of an invoice number: `PSL/INV/2025/3301` -> 3301."""
    if not s:
        return None
    m = _TRAILING_INT.search(s)
    return int(m.group(1)) if m else None


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"
