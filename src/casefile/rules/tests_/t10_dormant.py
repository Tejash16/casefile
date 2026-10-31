"""T10 dormant_vendor_reactivated: a payment after `dormant_days` or more without one."""

from __future__ import annotations

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.schemas import Direction, EvidenceObject

TEST = "T10"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    dormant = ctx.th("dormant_days")
    out: list[EvidenceObject] = []
    df = ctx.rows[ctx.rows.vendor_id.notna()]
    for vid, g in df.groupby("vendor_id", sort=True):
        gaps = g.date.diff().dt.days
        for i in range(1, len(g)):
            if gaps.iloc[i] >= dormant:
                before, after = g.row_id.iloc[i - 1], g.row_id.iloc[i]
                out.append(
                    ev.from_rows(
                        test_id=TEST,
                        direction=Direction.supports,
                        strength=STRENGTH["t10_dormant"],
                        summary=f"Vendor {vid} was paid again after {int(gaps.iloc[i])} days "
                        "without a payment.",
                        rows=ctx.rows_for([before, after]),
                        max_rows=ctx.th("quote_max_rows"),
                        prefix=f"{vid}: {int(gaps.iloc[i])} idle days between ",
                        subject_ids=[ctx.ledger[after].approver_id],
                    )
                )
    return out
