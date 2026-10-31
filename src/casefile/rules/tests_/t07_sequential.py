"""T07 sequential_invoice_numbers: a vendor's invoice numbers are gap-free or advance by at most
`sequential_step_max` per invoice we receive, so we look like its only customer. Refutes shell
(weakly) when numbers advance by `sequential_spread_min` or more."""

from __future__ import annotations

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.tests_._common import invoice_number, ledger_rows, vendor_groups
from casefile.schemas import Direction, EvidenceObject

TEST = "T07"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    max_rows, min_n = ctx.th("quote_max_rows"), ctx.th("pattern_min_invoices")
    step_max, spread_min = ctx.th("sequential_step_max"), ctx.th("sequential_spread_min")
    out: list[EvidenceObject] = []
    for vid, g in vendor_groups(ctx):
        nums = sorted({n for n in (invoice_number(i) for i in g.invoice_no) if n is not None})
        if len(nums) < min_n:
            continue
        step = (nums[-1] - nums[0]) / (len(nums) - 1)
        span = f"{vid}: {len(nums)} invoice numbers {nums[0]}..{nums[-1]}, mean step {step:.1f}: "
        rows = ledger_rows(ctx, g)
        if step <= step_max:
            gap_free = all(b - a == 1 for a, b in zip(nums, nums[1:], strict=False))
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.supports,
                    strength=STRENGTH["t07_gap_free" if gap_free else "t07_narrow"],
                    summary=f"Vendor {vid}'s invoice numbers run from {nums[0]} to {nums[-1]} "
                    f"across {len(nums)} invoices"
                    + (" with no gaps." if gap_free else ", a narrow range."),
                    rows=rows,
                    max_rows=max_rows,
                    prefix=span,
                )
            )
        elif step >= spread_min:
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.refutes,
                    strength=STRENGTH["t07_refute"],
                    summary=f"Vendor {vid}'s invoice numbers advance by {step:.0f} on average "
                    "between our invoices, consistent with a vendor billing many customers.",
                    rows=rows,
                    max_rows=max_rows,
                    prefix=span,
                )
            )
    return out
