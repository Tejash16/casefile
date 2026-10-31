"""T09 off_hours_postings: a vendor's postings at night (`off_hours`), on weekends or on national
holidays, at least `off_hours_ratio_min` x the population's share. Rows without `posted_at` are
left out."""

from __future__ import annotations

import pandas as pd

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.tests_._common import elevated, ledger_rows, pct, rest_share
from casefile.schemas import Direction, EvidenceObject

TEST = "T09"


def off_hours_mask(posted: pd.Series, start: int, end: int, holidays: list[str]) -> pd.Series:
    hour = posted.dt.hour
    night = (hour >= start) | (hour < end)
    weekend = posted.dt.day_of_week >= 5
    holiday = posted.dt.strftime("%m-%d").isin(holidays)
    return night | weekend | holiday


def run(ctx: RuleContext) -> list[EvidenceObject]:
    df = ctx.rows[ctx.rows.posted_at.notna()]
    if df.empty:
        return []
    start, end = ctx.th("off_hours")
    mask = off_hours_mask(df.posted_at, start, end, ctx.th("holidays_mm_dd"))
    min_n, ratio = ctx.th("pattern_min_invoices"), ctx.th("off_hours_ratio_min")
    out: list[EvidenceObject] = []
    for vid, g in df[df.vendor_id.notna()].groupby("vendor_id", sort=True):
        if len(g) < min_n:
            continue
        m = mask[g.index]
        k, n = int(m.sum()), len(g)
        rest = rest_share(mask, df.vendor_id, vid)
        if k >= 2 and elevated(k / n, rest, ratio):
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.supports,
                    strength=STRENGTH["t09_off_hours"],
                    summary=f"{k} of vendor {vid}'s {n} invoices were posted at night, on a "
                    f"weekend or on a holiday, against {pct(rest)} of other postings.",
                    rows=ledger_rows(ctx, g[m.values]),
                    max_rows=ctx.th("quote_max_rows"),
                    prefix=f"{vid}: {k}/{n} off-hours ({start:02d}:00-{end:02d}:00, weekends, "
                    f"holidays) vs population {pct(rest)}: ",
                )
            )
    return out
