"""T17 founders_match: a vendor's Crustdata founders or decision makers (b2's `vendor_people`)
match a staff name at >= `fuzzy_identifier_min`. Same LinkedIn profile: supports strongly.
Different profiles: a namesake, neutral. No profile to compare: name only, weak support."""

from __future__ import annotations

from casefile.rules import evidence as ev
from casefile.rules import normalize as norm
from casefile.rules.config import STRENGTH
from casefile.rules.context import RuleContext
from casefile.rules.match import name_score, staff_profile
from casefile.schemas import Direction, EvidenceObject, SourceKind

TEST = "T17"


def run(ctx: RuleContext) -> list[EvidenceObject]:
    fuzzy_min = ctx.th("fuzzy_identifier_min")
    out: list[EvidenceObject] = []
    for vid, v in sorted(ctx.vendors.items()):
        cd = v.crustdata
        if cd is None:
            continue
        for person in ctx.vendor_people.get(vid, []):
            for sid, s in sorted(ctx.staff.items()):
                score = name_score(person.name, s.name_raw)
                if score < fuzzy_min:
                    continue
                theirs, ours = norm.profile_url(person.linkedin_url), staff_profile(s)
                if theirs and ours:
                    same = theirs == ours
                    direction = Direction.supports if same else Direction.neutral
                    strength = STRENGTH["t17_same_profile" if same else "t17_namesake"]
                    summary = (
                        f"Vendor {vid}'s {person.title or 'officer'} {person.name} has the same "
                        f"LinkedIn profile as staff member {sid}."
                        if same
                        else f"Vendor {vid}'s {person.title or 'officer'} shares staff member "
                        f"{sid}'s name but has a different LinkedIn profile: a namesake."
                    )
                else:
                    direction, strength = Direction.supports, STRENGTH["t17_name_only"]
                    summary = (
                        f"Vendor {vid}'s {person.title or 'officer'} {person.name} has the same "
                        f"name as staff member {sid}; no profile was available to compare."
                    )
                quote = (
                    f'{cd.citation} person "{person.name}", {person.title or "title unknown"}, '
                    f'{person.linkedin_url or "no profile"}; staff {sid} "{s.name_raw}" '
                    f"{ours or 'no profile'} (name score {score})"
                )
                out.append(
                    ev.make(
                        test_id=TEST,
                        direction=direction,
                        strength=strength,
                        summary=summary,
                        quote=quote,
                        kind=SourceKind.crustdata_company,
                        refs=[cd.citation],
                        as_of=cd.updated_at,
                        records={
                            "person": person.model_dump(mode="json"),
                            "staff_id": sid,
                            "staff_name": s.name_raw,
                            "staff_profile": ours,
                        },
                        subject_ids=[sid],
                        object_ids=[vid],
                    )
                )
    return out
