"""`ledger_stats`: the small summary the proposer sees instead of raw rows."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from casefile.schemas import LedgerRow

ROUND_UNIT = Decimal(1000)  # an amount is "round" when it is a whole multiple of this


def ledger_stats(rows: list[LedgerRow]) -> dict[str, Any]:
    """Row count, date range, total spend, per-vendor spend / invoices / approvers, round share.

    Vendors are keyed by `vendor_id`, or by `vendor_key` when the row is unlinked. Money is a
    string (Decimal) so the dict serialises to JSON unchanged.
    """
    spend: dict[str, Decimal] = defaultdict(Decimal)
    invoices: dict[str, int] = defaultdict(int)
    approvers: dict[str, set[str]] = defaultdict(set)
    round_by_vendor: dict[str, int] = defaultdict(int)
    names: dict[str, str] = {}
    for r in rows:
        k = r.vendor_id or r.vendor_key
        names.setdefault(k, r.vendor_name_raw)
        spend[k] += r.amount
        invoices[k] += 1
        if r.approver_id or r.approver_name_raw:
            approvers[k].add(r.approver_id or r.approver_name_raw or "")
        if r.amount % ROUND_UNIT == 0:
            round_by_vendor[k] += 1
    n_round = sum(round_by_vendor.values())
    top = sorted(spend.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "row_count": len(rows),
        "date_range": [min(r.date for r in rows).isoformat(), max(r.date for r in rows).isoformat()]
        if rows
        else [],
        "total_spend_inr": str(sum(spend.values(), Decimal(0))),
        "vendor_count": len(spend),
        "spend_per_vendor": {k: str(v) for k, v in sorted(spend.items())},
        "invoices_per_vendor": dict(sorted(invoices.items())),
        "approvers_per_vendor": {k: sorted(v) for k, v in sorted(approvers.items())},
        "round_amount_share": round(n_round / len(rows), 4) if rows else 0.0,
        "round_amount_share_per_vendor": {
            k: round(round_by_vendor[k] / invoices[k], 4) for k in sorted(invoices)
        },
        "round_unit_inr": str(ROUND_UNIT),
        "top_vendors_by_spend": [
            {"vendor": k, "name": names[k], "spend_inr": str(v), "invoices": invoices[k]}
            for k, v in top
        ],
        "unlinked_vendor_rows": sum(1 for r in rows if r.vendor_id is None),
        "unlinked_approver_rows": sum(
            1 for r in rows if r.approver_name_raw and r.approver_id is None
        ),
    }
