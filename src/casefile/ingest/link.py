"""Link ledger rows to the vendor master and the staff list by normalised key, then fuzzy match."""

from __future__ import annotations

from rapidfuzz import fuzz

from casefile.ingest.names import initials_compatible, normalize_person_name
from casefile.schemas import LedgerRow, StaffRecord, VendorRecord

FUZZY_MIN = 92  # RapidFuzz token_set_ratio needed to accept a link


def _best(query: str, keys: dict[str, str]) -> tuple[str | None, float]:
    """Best id for `query` among {norm: id} by token_set_ratio, ties broken by plain ratio.

    Returns (None, score) when the best score is below FUZZY_MIN or two different ids tie.
    """
    scored = sorted(
        ((fuzz.token_set_ratio(query, k), fuzz.ratio(query, k), i) for k, i in keys.items()),
        reverse=True,
    )
    if not scored or scored[0][0] < FUZZY_MIN:
        return None, scored[0][0] if scored else 0.0
    top = scored[0]
    if len(scored) > 1 and scored[1][:2] == top[:2] and scored[1][2] != top[2]:
        return None, top[0]
    return top[2], top[0]


def match_vendor(key: str, vendors: list[VendorRecord]) -> tuple[str | None, list[str]]:
    """Vendor id for a normalised vendor key, plus the flags the link raised."""
    by_norm = {v.name_norm: v.vendor_id for v in vendors}
    if key in by_norm:
        return by_norm[key], []
    vid, _ = _best(key, by_norm)
    return (vid, ["vendor_fuzzy_match"]) if vid else (None, ["vendor_unlinked"])


def match_staff(raw: str, staff: list[StaffRecord]) -> tuple[str | None, list[str]]:
    """Staff id for a raw person name, plus the flags the link raised."""
    norm = normalize_person_name(raw)
    by_norm = {s.name_norm: s.staff_id for s in staff}
    if norm in by_norm:
        return by_norm[norm], []
    sid, _ = _best(norm, by_norm)
    if sid:
        return sid, ["approver_spelling_variant"]
    hits = {s.staff_id for s in staff if initials_compatible(norm, s.name_norm)}
    if len(hits) == 1:
        return hits.pop(), ["approver_initials_match"]
    return None, ["approver_unlinked"]


def link_ledger(
    rows: list[LedgerRow], vendors: list[VendorRecord], staff: list[StaffRecord]
) -> list[LedgerRow]:
    """Fill `vendor_id` and `approver_id`; every non-exact link adds a quality flag to the row."""
    names = {v.vendor_id: v.name_raw for v in vendors}
    out: list[LedgerRow] = []
    for r in rows:
        flags = list(r.quality_flags)
        vid, f = match_vendor(r.vendor_key, vendors)
        flags += f
        if (
            vid
            and r.vendor_name_raw.strip() != names[vid]
            and "vendor_spelling_variant" not in flags
        ):
            flags.append("vendor_spelling_variant")
        aid = None
        if r.approver_name_raw:
            aid, f = match_staff(r.approver_name_raw, staff)
            flags += f
            if aid and not f:
                staff_raw = next(s.name_raw for s in staff if s.staff_id == aid)
                if r.approver_name_raw.strip() != staff_raw:
                    flags.append("approver_spelling_variant")
        out.append(
            r.model_copy(update={"vendor_id": vid, "approver_id": aid, "quality_flags": flags})
        )
    return out


def link_notes(rows: list[LedgerRow]) -> list[str]:
    """Human sentences for the links `link_ledger` could not make or made fuzzily."""
    notes = []
    unlinked_v = sorted({r.vendor_name_raw for r in rows if r.vendor_id is None})
    if unlinked_v:
        notes.append(f"ledger: vendor name(s) not in the vendor master: {', '.join(unlinked_v)}.")
    fuzzy = sorted(
        {
            f"{r.vendor_name_raw} -> {r.vendor_id}"
            for r in rows
            if "vendor_fuzzy_match" in r.quality_flags
        }
    )
    if fuzzy:
        notes.append(
            f"ledger: vendor names linked by fuzzy match (token_set_ratio >= {FUZZY_MIN}): "
            f"{'; '.join(fuzzy)}."
        )
    unlinked_a = sorted(
        {r.approver_name_raw or "" for r in rows if r.approver_name_raw and r.approver_id is None}
    )
    if unlinked_a:
        notes.append(f"ledger: approver name(s) not in the staff list: {', '.join(unlinked_a)}.")
    initials = sorted(
        {
            f"{r.approver_name_raw} -> {r.approver_id}"
            for r in rows
            if "approver_initials_match" in r.quality_flags
        }
    )
    if initials:
        notes.append(f"ledger: approver names linked through initials: {'; '.join(initials)}.")
    return notes
