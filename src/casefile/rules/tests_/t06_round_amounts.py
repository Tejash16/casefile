"""T06 round_amounts: a vendor's share of round amounts (multiples of `round_unit_inr`) is at
least `round_ratio_min` x the population's. Refutes shell_company when the share is no higher than
the population's."""

from __future__ import annotations

import numpy as np

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.tests_._common import elevated, ledger_rows, pct, rest_share, vendor_groups
from casefile.schemas import Direction, EvidenceObject

TEST = "T06"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    df = ctx.rows
    unit = ctx.th("round_unit_inr")
    is_round = np.isclose(np.mod(df.amount.round(2), unit), 0) & (df.amount > 0)
    df = df.assign(is_round=is_round)
    max_rows, min_n, ratio = (
        ctx.th("quote_max_rows"),
        ctx.th("pattern_min_invoices"),
        ctx.th("round_ratio_min"),
    )
    out: list[EvidenceObject] = []
    for vid, g in vendor_groups(ctx):
        if len(g) < min_n:
            continue
        mask = df.is_round[g.index]
        k, n = int(mask.sum()), len(g)
        share = k / n
        rest = rest_share(df.is_round, df.vendor_id, vid)
        if k >= 2 and elevated(share, rest, ratio):
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.supports,
                    strength=STRENGTH["t06_round_many" if k == n else "t06_round"],
                    summary=f"{k} of vendor {vid}'s {n} invoices are round amounts, against "
                    f"{pct(rest)} of other invoices.",
                    rows=ledger_rows(ctx, g[mask.values]),
                    max_rows=max_rows,
                    prefix=f"{vid}: {k}/{n} round ({pct(share)} vs population {pct(rest)}): ",
                )
            )
        elif share <= rest:
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.refutes,
                    strength=STRENGTH["t06_refute"],
                    summary=f"Vendor {vid}'s share of round amounts is no higher than the "
                    f"population's ({pct(share)} vs {pct(rest)}).",
                    rows=ledger_rows(ctx, g),
                    max_rows=max_rows,
                    prefix=f"{vid}: {k}/{n} round vs population {pct(rest)}: ",
                )
            )
    return out
