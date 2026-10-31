"""T14 lookalike_vendor_names: two vendor ids whose names score >= `lookalike_name_min`
(token sort ratio, legal suffixes stripped), or one tax id under several vendor ids."""

from __future__ import annotations

from itertools import combinations

from rapidfuzz import fuzz

from casefile.rules import evidence as ev
from casefile.rules import normalize as norm
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.match import numbers_agree
from casefile.schemas import Direction, EvidenceObject, SourceKind, VendorRecord

TEST = "T14"


def _record(v: VendorRecord) -> dict:
    return v.model_dump(mode="json", exclude={"crustdata", "resolution"})


def run(ctx: RuleContext) -> list[EvidenceObject]:
    name_min = ctx.th("lookalike_name_min")
    vendors = sorted(ctx.vendors.items())
    out: list[EvidenceObject] = []
    names = {vid: norm.company_name(v.name_raw) for vid, v in vendors}
    for (ia, a), (ib, b) in combinations(vendors, 2):
        if not numbers_agree(names[ia], names[ib]):  # "Plant 1 Services" vs "Plant 2 Services"
            continue
        score = round(fuzz.token_sort_ratio(names[ia], names[ib]))
        if score >= name_min:
            out.append(
                ev.make(
                    test_id=TEST,
                    direction=Direction.supports,
                    strength=STRENGTH["t14_lookalike"],
                    summary=f"Vendors {ia} and {ib} have near-identical names under different "
                    "vendor ids.",
                    quote=f'vendor {ia} "{a.name_raw}" ~ vendor {ib} "{b.name_raw}" '
                    f"(score {score})",
                    kind=SourceKind.vendor_master,
                    refs=[f"vendor:{ia}", f"vendor:{ib}"],
                    records={ia: _record(a), ib: _record(b)},
                    object_ids=[ia, ib],
                )
            )
    by_tax: dict[str, list[str]] = {}
    for vid, v in vendors:
        t = norm.tax_id(v.tax_id)
        if t:
            by_tax.setdefault(t, []).append(vid)
    for ids in by_tax.values():
        if len(ids) < 2:
            continue
        quote = "; ".join(f'vendor {i} tax_id "{ctx.vendors[i].tax_id}"' for i in ids)
        out.append(
            ev.make(
                test_id=TEST,
                direction=Direction.supports,
                strength=STRENGTH["t14_same_tax_id"],
                summary=f"One tax id is registered under {len(ids)} vendor ids: "
                + ", ".join(ids)
                + ".",
                quote=quote,
                kind=SourceKind.vendor_master,
                refs=[f"vendor:{i}" for i in ids],
                records={i: _record(ctx.vendors[i]) for i in ids},
                object_ids=ids,
            )
        )
    return out
