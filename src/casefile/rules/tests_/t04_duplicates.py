"""T04 duplicate_invoices: same vendor + invoice no.; same no. + amount across vendors (Nigrini
"same-same-different"); same vendor + amount within `duplicate_window_days`. Refutes duplicate
billing for a vendor with enough invoices and no duplicate at all."""

from __future__ import annotations

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.evidence import inr
from casefile.rules.tests_._common import invoice_key, ledger_rows, vendor_groups
from casefile.schemas import Direction, EvidenceObject

TEST = "T04"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    df = ctx.rows.assign(inv_key=[invoice_key(i) for i in ctx.rows.invoice_no])
    max_rows = ctx.th("quote_max_rows")
    window = ctx.th("duplicate_window_days")
    out: list[EvidenceObject] = []
    reported: set[frozenset[str]] = set()
    flagged: set[str] = set()

    def emit(row_ids: list[str], strength: float, summary: str, prefix: str) -> None:
        key = frozenset(row_ids)
        if any(key <= seen for seen in reported):
            return
        reported.add(key)
        rows = ctx.rows_for(row_ids)
        flagged.update(r.vendor_id for r in rows if r.vendor_id)
        out.append(
            ev.from_rows(
                test_id=TEST,
                direction=Direction.supports,
                strength=strength,
                summary=summary,
                rows=rows,
                max_rows=max_rows,
                prefix=prefix,
            )
        )

    with_inv = df[df.inv_key.notna()]
    # 1. same vendor, same invoice number
    same_no = with_inv[with_inv.duplicated(["vendor", "inv_key"], keep=False)]
    for _, g in same_no.groupby(["vendor", "inv_key"], sort=True):
        if len(g) >= 2:
            emit(
                list(g.row_id),
                STRENGTH["t04_same_invoice_no"],
                f"Invoice number {g.invoice_no.iloc[0]} from the same vendor was paid "
                f"{len(g)} times.",
                f"same invoice number paid {len(g)} times: ",
            )
    # 2. same invoice number and amount, different vendors
    same_pair = with_inv[with_inv.duplicated(["inv_key", "amount"], keep=False)]
    for _, g in same_pair.groupby(["inv_key", "amount"], sort=True):
        if g.vendor.nunique() >= 2:
            emit(
                list(g.row_id),
                STRENGTH["t04_same_same_different"],
                f"Invoice number {g.invoice_no.iloc[0]} for INR {inr(g.amount.iloc[0])} was paid "
                f"to {g.vendor.nunique()} different vendors.",
                "same number and amount, different vendors: ",
            )
    # 3. same vendor, same amount, within the window
    same_amount = df[df.duplicated(["vendor", "amount"], keep=False)]
    for (_, amount), g in same_amount.groupby(["vendor", "amount"], sort=True):
        gaps = g.date.diff().dt.days
        for i in range(1, len(g)):
            if gaps.iloc[i] <= window:
                pair = [g.row_id.iloc[i - 1], g.row_id.iloc[i]]
                emit(
                    pair,
                    STRENGTH["t04_same_amount_window"],
                    f"The same vendor was paid INR {inr(amount)} twice within "
                    f"{int(gaps.iloc[i])} days.",
                    f"same vendor and amount {int(gaps.iloc[i])} days apart: ",
                )

    # refute: vendor with enough invoices and no duplicate of any kind
    min_n = ctx.th("pattern_min_invoices")
    for vid, g in vendor_groups(ctx):
        if vid in flagged or len(g) < min_n:
            continue
        out.append(
            ev.from_rows(
                test_id=TEST,
                direction=Direction.refutes,
                strength=STRENGTH["t04_refute"],
                summary=f"None of vendor {vid}'s {len(g)} invoices repeats an invoice number or "
                f"an amount within {window} days.",
                rows=ledger_rows(ctx, g),
                max_rows=max_rows,
                prefix=f"{vid}: 0 duplicates in {len(g)} invoices: ",
            )
        )
    return out
