"""T03 vendor_age_vs_first_payment:

- vendor master `created_on` (a day) within `new_vendor_days` before the first invoice;
- Crustdata `year_founded` (a year only) after the first invoice's year, i.e. the vendor was paid
  before 1 January of the year it was founded. A year cannot place a founding within days of an
  invoice, so a first invoice inside the founding year is not a signal."""

from __future__ import annotations

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.evidence import row_line
from casefile.schemas import Direction, EvidenceObject, SourceKind

TEST = "T03"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    new_days = ctx.th("new_vendor_days")
    out: list[EvidenceObject] = []
    df = ctx.rows[ctx.rows.vendor_id.notna()]
    first_rows = df.groupby("vendor_id", sort=True).row_id.first()
    for vid, first_id in first_rows.items():
        v = ctx.vendors.get(vid)
        if v is None:
            continue
        first = ctx.ledger[first_id]
        parts: list[str] = []
        reasons: list[str] = []
        strength = 0.0
        if v.created_on is not None:
            age = (first.date - v.created_on).days
            if 0 <= age <= new_days:
                parts.append(f"vendor master {vid} created_on {v.created_on.isoformat()}")
                reasons.append(f"was created {age} days before its first invoice")
                strength = STRENGTH["t03_new"]
        cd = v.crustdata
        founded_after = cd is not None and cd.year_founded and cd.year_founded > first.date.year
        if founded_after:
            parts.append(f"{cd.citation} year_founded {cd.year_founded}")
            reasons.append(f"was founded in {cd.year_founded}, after its first invoice")
            strength = max(strength, STRENGTH["t03_paid_before_founded"])
        if not parts:
            continue
        quote = "; ".join(parts) + f"; first invoice {row_line(first)}"
        refs = [first.row_id, f"vendor:{vid}"] + ([cd.citation] if founded_after else [])
        out.append(
            ev.make(
                test_id=TEST,
                direction=Direction.supports,
                strength=strength,
                summary=f"Vendor {vid} " + " and ".join(reasons) + ".",
                quote=quote,
                kind=SourceKind.vendor_master,
                refs=refs,
                records={
                    "vendor": v.model_dump(mode="json", exclude={"crustdata", "resolution"}),
                    "year_founded": cd.year_founded if cd else None,
                    "first_row": first.model_dump(mode="json"),
                },
                subject_ids=[first.approver_id],
                object_ids=[vid],
            )
        )
    return out
