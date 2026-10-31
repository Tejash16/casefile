"""T05 threshold_structuring: invoices in the `threshold_band_pct` band under the approver's
limit, more often than the population; and splits (each under the limit, together over it within
`split_window_days`). Refutes threshold structuring when a vendor's band share is no higher than
the population's and it has no splits."""

from __future__ import annotations

import pandas as pd

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.evidence import inr
from casefile.rules.tests_._common import elevated, invoice_key, ledger_rows, pct, rest_share
from casefile.schemas import Direction, EvidenceObject

TEST = "T05"


def _splits(g: pd.DataFrame, window: int) -> list[list[str]]:
    """Maximal runs of >= 2 invoices within `window` days, each under the limit, summing over it."""
    out: list[list[str]] = []
    dates, amounts, limits, ids = list(g.date), list(g.amount), list(g.limit), list(g.row_id)
    i = 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and (dates[j + 1] - dates[i]).days <= window:
            j += 1
        run = range(i, j + 1)
        if (
            j > i
            and all(amounts[k] <= limits[k] for k in run)
            and sum(amounts[k] for k in run) > limits[i]
        ):
            out.append([ids[k] for k in run])
            i = j + 1
        else:
            i += 1
    return out


def run(ctx: RuleContext) -> list[EvidenceObject]:
    limits = {
        sid: float(s.approval_limit) for sid, s in ctx.staff.items() if s.approval_limit is not None
    }
    df = ctx.rows[ctx.rows.approver_id.isin(list(limits))].copy()
    if df.empty:
        return []
    df["limit"] = df.approver_id.map(limits)
    lo = df.limit * (1 - ctx.th("threshold_band_pct") / 100)
    df["in_band"] = (df.amount >= lo) & (df.amount <= df.limit)
    max_rows, min_n = ctx.th("quote_max_rows"), ctx.th("pattern_min_invoices")
    ratio, window = ctx.th("band_ratio_min"), ctx.th("split_window_days")
    out: list[EvidenceObject] = []

    linked = df[df.vendor_id.notna()]
    for vid, gv in linked.groupby("vendor_id", sort=True):
        vendor_has_signal = False
        for aid, g in gv.groupby("approver_id", sort=True):
            limit = limits[aid]
            k, n = int(g.in_band.sum()), len(g)
            share = k / n
            rest = rest_share(df.in_band, df.vendor_id, vid)
            if k >= 2 and elevated(share, rest, ratio):
                vendor_has_signal = True
                band = g[g.in_band]
                out.append(
                    ev.from_rows(
                        test_id=TEST,
                        direction=Direction.supports,
                        strength=STRENGTH["t05_band_majority" if share > 0.5 else "t05_band"],
                        summary=f"{k} of {n} invoices from vendor {vid} approved by {aid} fall "
                        f"just under {aid}'s INR {inr(limit)} limit, against {pct(rest)} of "
                        "other invoices.",
                        rows=ledger_rows(ctx, band),
                        max_rows=max_rows,
                        prefix=f"{aid} limit {inr(limit)}; {k}/{n} in band ({pct(share)} vs "
                        f"population {pct(rest)}): ",
                    )
                )
            # a repeated invoice number is a duplicate payment (T04), not a split
            keys = g.invoice_no.map(invoice_key)
            distinct = g[keys.isna() | ~keys.duplicated()]
            for split in _splits(distinct, window):
                vendor_has_signal = True
                rows = ctx.rows_for(split)
                total = sum(float(r.amount) for r in rows)
                out.append(
                    ev.from_rows(
                        test_id=TEST,
                        direction=Direction.supports,
                        strength=STRENGTH["t05_split"],
                        summary=f"{len(rows)} invoices from vendor {vid}, each within {aid}'s "
                        f"INR {inr(limit)} limit, total INR {inr(total)} within {window} days.",
                        rows=rows,
                        max_rows=max_rows,
                        prefix=f"split: {len(rows)} invoices total {inr(total)} over limit "
                        f"{inr(limit)}: ",
                    )
                )
        if vendor_has_signal or len(gv) < min_n:
            continue
        share = float(gv.in_band.mean())
        rest = rest_share(df.in_band, df.vendor_id, vid)
        if share <= rest:
            out.append(
                ev.from_rows(
                    test_id=TEST,
                    direction=Direction.refutes,
                    strength=STRENGTH["t05_refute"],
                    summary=f"Vendor {vid}'s invoices sit just under the approver's limit no more "
                    f"often than the population ({pct(share)} vs {pct(rest)}), with no splits.",
                    rows=ledger_rows(ctx, gv),
                    max_rows=max_rows,
                    prefix=f"{vid}: {int(gv.in_band.sum())}/{len(gv)} in band vs population "
                    f"{pct(rest)}: ",
                )
            )
    return out
