"""T02 thin_vendor_footprint: PO box, residential or virtual address; no phone, tax id and
website at all; a personal mailbox. A coworking address alone is not a signal (neutral note)."""

from __future__ import annotations

from casefile.rules import evidence as ev
from casefile.rules import normalize as norm
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.schemas import AddressType, Direction, EvidenceObject, SourceKind

TEST = "T02"
THIN_ADDRESS = {AddressType.po_box, AddressType.residential, AddressType.virtual}


def run(ctx: RuleContext) -> list[EvidenceObject]:
    providers = set(ctx.th("personal_email_providers"))
    out: list[EvidenceObject] = []
    for vid, v in sorted(ctx.vendors.items()):
        atype = norm.address_type(v.address, v.address_type)
        signals: list[tuple[str, float]] = []
        fields = [f'address "{v.address or ""}" ({atype.value})']
        if atype in THIN_ADDRESS:
            signals.append((f"a {atype.value.replace('_', ' ')} address", STRENGTH["t02_address"]))
        if not (v.phone or v.tax_id or v.website):
            signals.append(("no phone, tax id or website", STRENGTH["t02_no_contact"]))
        fields.append(
            f'phone "{v.phone or ""}"; tax_id "{v.tax_id or ""}"; website "{v.website or ""}"'
        )
        domain = norm.email_domain(v.email)
        if domain and domain.split(".")[0] in providers:
            signals.append(("a personal mailbox", STRENGTH["t02_personal_email"]))
            fields.append(f'email "{v.email}"')
        quote = f"vendor master {vid}: " + "; ".join(fields)
        record = v.model_dump(mode="json", exclude={"crustdata", "resolution"})
        common = dict(
            test_id=TEST,
            quote=quote,
            kind=SourceKind.vendor_master,
            refs=[f"vendor:{vid}"],
            records=record,
            object_ids=[vid],
        )
        if signals:
            strength = min(
                STRENGTH["t02_cap"],
                max(s for _, s in signals) + STRENGTH["t02_extra_signal"] * (len(signals) - 1),
            )
            out.append(
                ev.make(
                    direction=Direction.supports,
                    strength=strength,
                    summary=f"Vendor {vid} has " + " and ".join(n for n, _ in signals) + ".",
                    **common,
                )
            )
        elif atype == AddressType.coworking:
            out.append(
                ev.make(
                    direction=Direction.neutral,
                    strength=STRENGTH["t02_coworking"],
                    summary=f"Vendor {vid} is registered at a coworking address, which unrelated "
                    "companies share; on its own this is not a thin-footprint signal.",
                    **common,
                )
            )
    return out
