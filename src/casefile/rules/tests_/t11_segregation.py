"""T11 segregation_of_duties: the user who created the vendor in the master also approved or
posted its invoices. User names (`adeshpande`, `anil.deshpande`) are mapped to staff ids."""

from __future__ import annotations

import re

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.evidence import rows_quote
from casefile.rules.normalize import person_name
from casefile.schemas import Direction, EvidenceObject, SourceKind, StaffRecord

TEST = "T11"


def _key(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def user_index(staff: dict[str, StaffRecord]) -> dict[str, str]:
    """Login-style keys -> staff id: id, full name, email local part, first initial + surname,
    first name + surname initial."""
    idx: dict[str, str] = {}
    for sid, s in sorted(staff.items()):
        tokens = person_name(s.name_raw).split()
        keys = {_key(sid), _key("".join(tokens))}
        if s.email and "@" in s.email:
            keys.add(_key(s.email.split("@")[0]))
        if len(tokens) >= 2:
            keys.add(_key(tokens[0][0] + tokens[-1]))
            keys.add(_key(tokens[0] + tokens[-1][0]))
            keys.add(_key(tokens[0] + tokens[-1]))
        for k in keys:
            if k:
                idx.setdefault(k, sid)
    return idx


def run(ctx: RuleContext) -> list[EvidenceObject]:
    idx = user_index(ctx.staff)
    out: list[EvidenceObject] = []
    for vid, v in sorted(ctx.vendors.items()):
        creator = idx.get(_key(v.created_by)) or (_key(v.created_by) or None)
        if not creator:
            continue
        g = ctx.rows[ctx.rows.vendor_id == vid]
        approved = g.approver_id == creator
        posted = g.created_by.map(lambda u: idx.get(_key(u)) or _key(u)) == creator
        hit = g[approved | posted]
        if hit.empty:
            continue
        rows = ctx.rows_for(list(hit.row_id))
        roles = " and ".join(
            r for r, m in (("approved", approved), ("posted", posted)) if m[hit.index].any()
        )
        created = v.created_on.isoformat() if v.created_on else "date unknown"
        quote = (
            f"vendor master {vid} created_by {v.created_by} ({creator}) on {created}; "
            + rows_quote(rows, ctx.th("quote_max_rows"))
        )
        out.append(
            ev.make(
                test_id=TEST,
                direction=Direction.supports,
                strength=STRENGTH["t11_same_user"],
                summary=f"The user who created vendor {vid} in the master ({creator}) also {roles} "
                f"{len(rows)} of its invoices.",
                quote=quote,
                kind=SourceKind.ledger_rows,
                refs=[f"vendor:{vid}", *(r.row_id for r in rows)],
                records={
                    "vendor": v.model_dump(mode="json", exclude={"crustdata", "resolution"}),
                    "rows": [r.model_dump(mode="json") for r in rows],
                },
                subject_ids=[creator if creator in ctx.staff else None],
                object_ids=[vid],
            )
        )
    return out
