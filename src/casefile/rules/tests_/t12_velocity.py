"""T12 velocity_and_share: a vendor's share of total spend, or its growth from the first half of
the ledger period to the second, at least `velocity_z` standard deviations above other vendors.
Refutes (weakly) when both are below `velocity_normal_z`."""

from __future__ import annotations

import numpy as np
import pandas as pd

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.evidence import inr
from casefile.rules.tests_._common import ledger_rows, pct, vendor_groups
from casefile.schemas import Direction, EvidenceObject

TEST = "T12"


def _z(x: pd.Series, sd_floor: float) -> pd.Series:
    return (x - x.mean()) / max(float(x.std(ddof=0)), sd_floor)


def run(ctx: RuleContext) -> list[EvidenceObject]:
    df = ctx.rows[ctx.rows.vendor_id.notna()]
    if df.vendor_id.nunique() < ctx.th("velocity_min_vendors"):
        return []
    mid = df.date.min() + (df.date.max() - df.date.min()) / 2
    spend = df.groupby("vendor_id").amount.sum()
    late = df[df.date >= mid].groupby("vendor_id").amount.sum().reindex(spend.index, fill_value=0)
    early = spend - late
    share = spend / spend.sum()
    growth = (late - early) / spend
    floor = ctx.th("velocity_sd_floor")
    z_share, z_growth = _z(share, floor * float(share.mean())), _z(growth, floor)
    zmin, znorm = ctx.th("velocity_z"), ctx.th("velocity_normal_z")
    min_n, max_rows = ctx.th("pattern_min_invoices"), ctx.th("quote_max_rows")
    cut = mid.date().isoformat()
    out: list[EvidenceObject] = []
    for vid, g in vendor_groups(ctx):
        zs, zg = float(z_share[vid]), float(z_growth[vid])
        stats = (
            f"{vid}: spend {inr(spend[vid])} = {pct(share[vid])} of {inr(spend.sum())} "
            f"(share z {zs:.1f}); before {cut} {inr(early[vid])}, from {cut} {inr(late[vid])} "
            f"(growth z {zg:.1f}); "
        )
        rows = ledger_rows(ctx, g)
        if zs >= zmin or zg >= zmin:
            # growth is the velocity signal; share alone flags the biggest supplier by nature
            growth = zg >= zmin
            which, z = ("growth in spend", zg) if growth else ("share of spend", zs)
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.supports,
                    strength=STRENGTH["t12_growth" if growth else "t12_share"],
                    summary=f"Vendor {vid}'s {which} is {z:.1f} standard deviations "
                    f"above the other {len(spend) - 1} vendors.",
                    rows=rows,
                    max_rows=max_rows,
                    prefix=stats,
                    subject_ids=[],
                )
            )
        elif len(g) >= min_n and zs < znorm and zg < znorm and np.isfinite([zs, zg]).all():
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.refutes,
                    strength=STRENGTH["t12_refute"],
                    summary=f"Vendor {vid}'s share of spend and its growth are within the range "
                    "of the other vendors.",
                    rows=rows,
                    max_rows=max_rows,
                    prefix=stats,
                    subject_ids=[],
                )
            )
    return out
