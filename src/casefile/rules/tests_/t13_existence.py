"""T13 existence_and_capacity, from Crustdata CompanyFacts:

- unresolved / no record: supports shell or ghost (data gap, `t13_unresolved`);
- no website: supports (`t13_thin`); headcount <= `shell_headcount_max` with a website: a
  weaker lead (`t13_tiny_with_website`), since tiny real companies exist;
- billed INR per head above `volume_per_head_max_inr`: supports (`t13_volume`);
- headcount >= `established_headcount_min` with a website: refutes shell (`t13_refute`).
Headcount falls back to the bounds of `employee_count_range` ("1-10", "51-200", "10001+")."""

from __future__ import annotations

import re

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.evidence import inr
from casefile.schemas import CompanyFacts, Direction, EvidenceObject, SourceKind

TEST = "T13"


def headcount_bounds(cd: CompanyFacts) -> tuple[int | None, int | None, str]:
    """(low, high, quoted field) for the company's headcount."""
    if cd.headcount_total is not None:
        return cd.headcount_total, cd.headcount_total, f"headcount_total {cd.headcount_total}"
    rng = cd.employee_count_range or ""
    nums = [int(n) for n in re.findall(r"\d+", rng.replace(",", ""))]
    if not nums:
        return None, None, "headcount unknown"
    high = nums[1] if len(nums) > 1 else (None if "+" in rng else nums[0])
    return nums[0], high, f"employee_count_range {rng}"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    billed = ctx.rows[ctx.rows.vendor_id.notna()].groupby("vendor_id").amount.sum()
    shell_max, est_min = ctx.th("shell_headcount_max"), ctx.th("established_headcount_min")
    per_head_max = ctx.th("volume_per_head_max_inr")
    out: list[EvidenceObject] = []
    for vid, v in sorted(ctx.vendors.items()):
        cd = v.crustdata
        if cd is None or v.resolution.status != "resolved":
            status = v.resolution.status
            out.append(
                ev.make(
                    test_id=TEST,
                    direction=Direction.supports,
                    strength=STRENGTH["t13_unresolved"],
                    summary=f"Vendor {vid} has no matching Crustdata company record "
                    f"(resolution {status}); its existence could not be confirmed.",
                    quote=f'vendor master {vid} "{v.name_raw}": Crustdata resolution {status}, '
                    f"candidates considered {v.resolution.candidates_considered}",
                    kind=SourceKind.vendor_master,
                    refs=[f"vendor:{vid}"],
                    records={
                        "vendor_id": vid,
                        "name_raw": v.name_raw,
                        "resolution": v.resolution.model_dump(mode="json"),
                    },
                    object_ids=[vid],
                )
            )
            continue
        low, high, hc_field = headcount_bounds(cd)
        website = cd.website or cd.primary_domain
        fields = f"{hc_field}; website {website or 'none'}"
        common = dict(
            test_id=TEST,
            kind=SourceKind.crustdata_company,
            refs=[cd.citation],
            as_of=cd.updated_at,
            records=cd.model_dump(mode="json"),
            object_ids=[vid],
        )
        tiny = high is not None and high <= shell_max
        if tiny or not website:
            # FinCEN: "limited or no internet presence"; a tiny company with a website is a lead
            out.append(
                ev.make(
                    direction=Direction.supports,
                    strength=STRENGTH["t13_thin" if not website else "t13_tiny_with_website"],
                    summary=f"Crustdata's record for vendor {vid} shows "
                    + (f"{hc_field.replace('_', ' ')}" if high is not None else "no headcount")
                    + (" and no website." if not website else f" with website {website}."),
                    quote=f"{cd.citation} {fields}",
                    **common,
                )
            )
        spend = float(billed.get(vid, 0.0))
        if low is not None and spend / max(low, 1) > per_head_max:
            out.append(
                ev.make(
                    direction=Direction.supports,
                    strength=STRENGTH["t13_volume"],
                    summary=f"Vendor {vid} billed INR {inr(spend)}, more than INR "
                    f"{inr(per_head_max)} per employee on Crustdata's headcount.",
                    quote=f"{cd.citation} {hc_field}; billed {inr(spend)}",
                    **common,
                )
            )
        if low is not None and low >= est_min and website:
            out.append(
                ev.make(
                    direction=Direction.refutes,
                    strength=STRENGTH["t13_refute"],
                    summary=f"Crustdata's record for vendor {vid} shows an established company: "
                    f"{hc_field.replace('_', ' ')} and website {website}.",
                    quote=f"{cd.citation} {fields}",
                    **common,
                )
            )
    return out
