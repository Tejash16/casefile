"""T15 career_overlap, from the staff member's Crustdata PersonFacts.employment:

- an employment at the vendor (by company id, else domain, else fuzzy name) that overlaps the
  payment window, ended within `career_gap_days` before the first payment, or started within
  `career_gap_days` after the last one: supports conflict_of_interest (`t15_overlap`; capped at
  `t15_non_approver` when the staff member approved none of the vendor's invoices);
- such an employment further away than that: neutral (`t15_old_employment`);
- a resolved person with employment history and none at the vendor: refutes (`t15_refute`, or
  `t15_refute_low_confidence` below `identify_accept`);
- an unresolved person: neutral, a data gap.

Pairs: every approver-vendor pair in the ledger, every hypothesis subject-object pair, and every
resolved staff member against every paid vendor (so a tip-named non-approver can be cleared).
"""

from __future__ import annotations

from datetime import date

from casefile.rules import evidence as ev
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.match import employment_at_vendor, employment_timing
from casefile.schemas import Direction, EvidenceObject, SourceKind

TEST = "T15"


def _d(x: date | None) -> str:
    return x.isoformat() if x else "unknown"


def pairs(ctx: RuleContext) -> list[tuple[str, str]]:
    df = ctx.rows[ctx.rows.vendor_id.notna() & ctx.rows.approver_id.notna()]
    out = set(zip(df.approver_id, df.vendor_id, strict=True))
    for h in ctx.hypotheses:
        out |= {(s, v) for s in h.subjects for v in h.objects}
    paid = set(ctx.rows.vendor_id.dropna())
    for sid, s in ctx.staff.items():
        if s.crustdata is not None and s.resolution.status == "resolved":
            out |= {(sid, vid) for vid in paid}
    return sorted((s, v) for s, v in out if s in ctx.staff and v in ctx.vendors)


def run(ctx: RuleContext) -> list[EvidenceObject]:
    fuzzy_min, gap = ctx.th("fuzzy_identifier_min"), ctx.th("career_gap_days")
    accept = ctx.th("identify_accept")
    out: list[EvidenceObject] = []
    for sid, vid in pairs(ctx):
        s, v = ctx.staff[sid], ctx.vendors[vid]
        g = ctx.rows[(ctx.rows.vendor_id == vid) & (ctx.rows.approver_id == sid)]
        approver = not g.empty
        if g.empty:
            g = ctx.rows[ctx.rows.vendor_id == vid]
        if g.empty:
            continue
        first_row, last_row = ctx.ledger[g.row_id.iloc[0]], ctx.ledger[g.row_id.iloc[-1]]
        first, last = first_row.date, last_row.date
        p = s.crustdata
        if p is None or s.resolution.status != "resolved":
            out.append(
                ev.make(
                    test_id=TEST,
                    direction=Direction.neutral,
                    strength=STRENGTH["t15_unresolved"],
                    summary=f"Staff member {sid} could not be matched to a Crustdata profile "
                    f"(resolution {s.resolution.status}), so their career history at vendor "
                    f"{vid} was not checked.",
                    quote=f'staff list {sid} "{s.name_raw}": Crustdata resolution '
                    f"{s.resolution.status}",
                    kind=SourceKind.staff_list,
                    refs=[f"staff:{sid}"],
                    records={"staff_id": sid, "resolution": s.resolution.model_dump(mode="json")},
                    subject_ids=[sid],
                    object_ids=[vid],
                )
            )
            continue
        common = dict(
            test_id=TEST,
            kind=SourceKind.crustdata_person,
            refs=[p.citation] + ([v.crustdata.citation] if v.crustdata else []),
            as_of=p.updated_at,
            records={"person": p.model_dump(mode="json"), "first_payment": first_row.row_id},
            subject_ids=[sid],
            object_ids=[vid],
        )
        hits = [
            (i, e, how)
            for i, e in enumerate(p.employment)
            if (how := employment_at_vendor(e, v, fuzzy_min))
        ]
        if hits:
            best = None
            for i, e, _ in hits:
                when = employment_timing(e, first, last, gap)
                if when:
                    best = (i, e, when)
                    break
            i, e, when = best or (hits[0][0], hits[0][1], None)
            end_txt = "present" if e.is_current else _d(e.end_date)
            quote = (
                f"{p.citation} employment[{i}]: {e.company_name}, {e.title or 'title unknown'}, "
                f"{_d(e.start_date)} to {end_txt}; first payment {first.isoformat()} "
                f"({first_row.row_id}); last payment {last.isoformat()} ({last_row.row_id})"
            )
            if when is None:
                out.append(
                    ev.make(
                        direction=Direction.neutral,
                        strength=STRENGTH["t15_old_employment"],
                        summary=f"Staff member {sid}'s Crustdata career history includes vendor "
                        f"{vid}, but more than {gap} days away from its payments.",
                        quote=quote,
                        **common,
                    )
                )
                continue
            out.append(
                ev.make(
                    direction=Direction.supports,
                    strength=STRENGTH["t15_overlap" if approver else "t15_non_approver"],
                    summary=f"Staff member {sid}'s Crustdata career history includes vendor {vid} "
                    f"({e.company_name}, {_d(e.start_date)} to {end_txt}), {when}"
                    + ("." if approver else f"; {sid} approved none of its invoices."),
                    quote=quote,
                    **common,
                )
            )
            continue
        if not p.employment:
            continue  # resolved but no history: absence of data, not evidence of absence
        conf = s.resolution.confidence
        strong = conf is None or conf >= accept
        listing = "; ".join(
            f"[{i}] {e.company_name} {_d(e.start_date)} to "
            f"{'present' if e.is_current else _d(e.end_date)}"
            for i, e in enumerate(p.employment)
        )
        out.append(
            ev.make(
                direction=Direction.refutes,
                strength=STRENGTH["t15_refute" if strong else "t15_refute_low_confidence"],
                summary=f"Staff member {sid}'s Crustdata career history lists "
                f"{len(p.employment)} employers and none of them is vendor {vid}.",
                quote=f"{p.citation} employment: {listing}",
                **common,
            )
        )
    return out
