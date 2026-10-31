"""T03 vendor_age_vs_first_payment: vendor master `created_on`, or Crustdata `year_founded`,
within `new_vendor_days` of the first invoice; or founded after it was first paid."""

from __future__ import annotations

from datetime import date

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
        if cd is not None and cd.year_founded:
            max_age = (first.date - date(cd.year_founded, 1, 1)).days
            if cd.year_founded > first.date.year:
                parts.append(f"{cd.citation} year_founded {cd.year_founded}")
                reasons.append(f"was founded in {cd.year_founded}, after its first invoice")
                strength = max(strength, STRENGTH["t03_paid_before_founded"])
            elif max_age <= new_days:
                parts.append(f"{cd.citation} year_founded {cd.year_founded}")
                reasons.append(f"was founded at most {max_age} days before its first invoice")
                strength = STRENGTH["t03_both"] if strength else STRENGTH["t03_new"]
        if not parts:
            continue
        quote = "; ".join(parts) + f"; first invoice {row_line(first)}"
        refs = [first.row_id, f"vendor:{vid}"] + ([cd.citation] if cd and cd.year_founded else [])
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
