"""T01 vendor_staff_identifier_match: a vendor shares bank account, tax id, phone, email or
address (fuzzy >= `fuzzy_identifier_min`) with a staff member or with another vendor.

Coworking rule (judges: "separate a fraud ring from companies that simply share an office"): when
the only match is an address and either address is a coworking address, the evidence is neutral;
a phone, bank account, tax id or email match alongside it still supports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from casefile.rules import evidence as ev
from casefile.rules import normalize as norm
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.match import address_score, coworking_building_score
from casefile.schemas import (
    AddressType,
    Direction,
    EvidenceObject,
    SourceKind,
    StaffRecord,
    VendorRecord,
)

TEST = "T01"
STRENGTH_KEY = {
    "bank_account": "t01_bank",
    "tax_id": "t01_tax_id",
    "phone": "t01_phone",
    "email": "t01_email",
    "address": "t01_address",
}


@dataclass
class Party:
    kind: str  # "vendor" | "staff"
    id: str
    raw: dict[str, str | None]
    norm: dict[str, str | None]
    coworking: bool
    record: Any


def _party(rec: VendorRecord | StaffRecord) -> Party:
    is_vendor = isinstance(rec, VendorRecord)
    raw = {
        "bank_account": rec.bank_account,
        "tax_id": rec.tax_id if is_vendor else None,
        "phone": rec.phone,
        "email": rec.email,
        "address": rec.address,
    }
    return Party(
        kind="vendor" if is_vendor else "staff",
        id=rec.vendor_id if is_vendor else rec.staff_id,
        raw=raw,
        norm={
            "bank_account": norm.bank_account(raw["bank_account"]),
            "tax_id": norm.tax_id(raw["tax_id"]),
            "phone": norm.phone(raw["phone"]),
            "email": norm.email(raw["email"]),
            "address": norm.address(raw["address"]),
        },
        coworking=norm.is_coworking(rec.address)
        or (is_vendor and rec.address_type == AddressType.coworking),
        record=rec.model_dump(mode="json", exclude={"crustdata", "resolution"}),
    )


def _matches(a: Party, b: Party, fuzzy_min: int, min_tokens: int) -> dict[str, int]:
    """attribute -> score (100 for exact identifiers)."""
    found: dict[str, int] = {}
    for attr in ("bank_account", "tax_id", "phone", "email"):
        if a.norm[attr] and a.norm[attr] == b.norm[attr]:
            found[attr] = 100
    score = address_score(a.norm["address"], b.norm["address"], fuzzy_min, min_tokens)
    if score is None and a.coworking and b.coworking:
        score = coworking_building_score(a.raw["address"], b.raw["address"], fuzzy_min, min_tokens)
    if score is not None:
        found["address"] = score
    return found


def _evidence(a: Party, b: Party, found: dict[str, int]) -> EvidenceObject:
    coworking = "address" in found and (a.coworking or b.coworking)
    parts = []
    for attr, score in found.items():
        part = f'{a.kind} {a.id} {attr} "{a.raw[attr]}" = {b.kind} {b.id} {attr} "{b.raw[attr]}"'
        parts.append(part + (f" (score {score})" if score < 100 else ""))
    quote = "; ".join(parts)
    names = ", ".join(k.replace("_", " ") for k in found)
    if coworking and set(found) == {"address"}:
        direction, strength = Direction.neutral, STRENGTH["t01_coworking"]
        summary = (
            f"{a.kind.capitalize()} {a.id} and {b.kind} {b.id} share a coworking address and no "
            "phone, bank account, tax id or email."
        )
    else:
        scored = [k for k in found if not (k == "address" and coworking)]
        direction = Direction.supports
        strength = min(
            STRENGTH["t01_cap"],
            max(STRENGTH[STRENGTH_KEY[k]] for k in scored)
            + STRENGTH["t01_extra_match"] * (len(scored) - 1),
        )
        summary = f"{a.kind.capitalize()} {a.id} and {b.kind} {b.id} share {names}."
    staff = [p.id for p in (a, b) if p.kind == "staff"]
    vendors = [p.id for p in (a, b) if p.kind == "vendor"]
    return ev.make(
        test_id=TEST,
        direction=direction,
        strength=strength,
        summary=summary,
        quote=quote,
        kind=SourceKind.vendor_master,
        refs=[f"{p.kind}:{p.id}" for p in (a, b)],
        records={f"{p.kind}:{p.id}": p.record for p in (a, b)},
        subject_ids=staff,
        object_ids=vendors,
    )


def run(ctx: RuleContext) -> list[EvidenceObject]:
    fuzzy_min, min_tokens = ctx.th("fuzzy_identifier_min"), ctx.th("address_min_tokens")
    vendors = [_party(v) for _, v in sorted(ctx.vendors.items())]
    staff = [_party(s) for _, s in sorted(ctx.staff.items())]
    out: list[EvidenceObject] = []
    for i, v in enumerate(vendors):
        for other in [*staff, *vendors[i + 1 :]]:
            found = _matches(v, other, fuzzy_min, min_tokens)
            if found:
                out.append(_evidence(v, other, found))
    return out
