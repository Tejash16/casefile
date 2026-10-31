"""People attached to a resolved vendor, for b3's T17 founders_match."""

from __future__ import annotations

from casefile.schemas import PersonBrief, VendorRecord


def vendor_people(vendor: VendorRecord, include_decision_makers: bool = True) -> list[PersonBrief]:
    """Founders first, then decision makers, one entry per name; empty when unresolved.

    Large companies list hundreds of decision makers (Tata Steel: 300), so a name match against
    them is weak evidence; founders of a small vendor are the strong case.
    """
    facts = vendor.crustdata
    if facts is None:
        return []
    people = list(facts.founders)
    if include_decision_makers:
        people += facts.decision_makers
    seen: set[str] = set()
    out: list[PersonBrief] = []
    for p in people:
        key = " ".join(p.name.lower().split())
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return out
