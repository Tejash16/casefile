"""Resolve staff-list rows to Crustdata people, then enrich the accepted profiles in one batch.

Order (first that applies wins):

1. `linkedin_url` in the staff list -> Person Enrich on it (`method=linkedin_url`): the row itself
   names the profile, so there is nothing to disambiguate.
2. `email` -> Person Identify (`person_identify_email`), only when describe_scope says the
   endpoint is enabled (it is 403 on our plan, so this is skipped without spending a call).
3. Person Search, exact mode, name + audited company (current or past roles): one hit ->
   `person_search`; several -> judge (no decision -> ambiguous). No hit -> name-only search: any
   hits end `ambiguous` and are never accepted, not even by the judge, because none of them lists
   the audited company and a namesake's career attached to our staff member is precisely the
   false lead the case file must not make. No hits at all -> unresolved.

`candidates_considered` counts every profile looked at, so the case file can say how many
namesakes were ruled out.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from casefile.crustdata.client import CrustdataClient, CrustdataError
from casefile.resolve._common import FREE_MAIL, domain_of, safe_judge, say
from casefile.resolve.vendors import _scope
from casefile.schemas import (
    MatchVerdict,
    PersonCandidate,
    PersonFacts,
    Resolution,
    ResolutionMethod,
    ResolutionStatus,
    StaffRecord,
)

SEARCH_ACCEPT_CONFIDENCE = 0.9  # one exact-name hit at the audited company
_HONORIFIC = re.compile(r"^(mr|mrs|ms|miss|dr|shri|smt|prof)\.?\s+", re.IGNORECASE)


@dataclass
class _D:
    status: ResolutionStatus = ResolutionStatus.unresolved
    method: ResolutionMethod | None = None
    confidence: float | None = None
    considered: int = 0
    log_record_id: str | None = None
    profile_url: str | None = None
    facts: PersonFacts | None = None
    notes: list[str] = field(default_factory=list)


def display_name(s: StaffRecord) -> str:
    """'Mr. Anil Deshpande' -> 'Anil Deshpande'."""
    raw = " ".join((s.name_raw or s.name_norm).split())
    prev = None
    while prev != raw:
        prev, raw = raw, _HONORIFIC.sub("", raw)
    return raw if any(ch.isupper() for ch in raw) else raw.title()


def infer_company(staff: list[StaffRecord]) -> str | None:
    """Audited company from the commonest staff email domain ('halvexa.example' -> Halvexa)."""
    doms = Counter(d for s in staff if (d := domain_of(s.email)))
    if not doms:
        return None
    stem = doms.most_common(1)[0][0].split(".")[0]
    return None if stem in FREE_MAIL else stem.replace("-", " ").title()


def _person_view(s: StaffRecord, company: str | None) -> dict[str, Any]:
    return {
        "name": display_name(s),
        "title": s.title,
        "department": s.department,
        "employer": company,
        "address": s.address,
        "joined_on": s.joined_on,
    }


def _cand_view(c: PersonCandidate) -> dict[str, Any]:
    return {
        "name": c.name,
        "current_title": c.current_title,
        "current_company": c.current_company,
        "location": c.location,
        "profile_url": c.profile_url,
    }


def _judge(
    judge: Any, s: StaffRecord, company: str | None, cands: list[PersonCandidate], d: _D
) -> None:
    shortlist = cands[:5]
    verdict = safe_judge(
        judge, _person_view(s, company), [_cand_view(c) for c in shortlist], "person"
    )
    if verdict is None:
        d.status = ResolutionStatus.ambiguous
        d.notes.append(f"{len(cands)} namesakes; no judge decision")
        return
    if verdict.log_record_id:
        d.log_record_id = verdict.log_record_id
    if verdict.decision == MatchVerdict.yes and verdict.index in range(len(shortlist)):
        d.status, d.method = ResolutionStatus.resolved, ResolutionMethod.llm_judge
        d.profile_url = shortlist[verdict.index].profile_url
        d.confidence = SEARCH_ACCEPT_CONFIDENCE
    elif verdict.decision == MatchVerdict.no:
        d.status = ResolutionStatus.unresolved
    else:
        d.status = ResolutionStatus.ambiguous
    d.notes.append(f"judge said {verdict.decision}: {verdict.reason}")


def resolve_staff(
    staff: list[StaffRecord],
    client: CrustdataClient,
    judge: Any = None,
    company_name: str | None = None,
) -> list[StaffRecord]:
    _scope(client, "person")
    calls0, credits0 = client.calls, client.credits_spent
    company = company_name or infer_company(staff)
    ds: dict[str, _D] = {s.staff_id: _D() for s in staff}
    done: set[str] = set()

    # 1. LinkedIn URL from the staff list
    by_url = {s.staff_id: s.linkedin_url.strip() for s in staff if s.linkedin_url}
    if by_url:
        try:
            status = client.enrich_persons_status(list(by_url.values()))
        except CrustdataError as e:
            say(f"person enrich by URL failed: {e}")
            status = None
        for sid, url in by_url.items():
            d = ds[sid]
            done.add(sid)  # the row names its profile; never fall back to a name search
            if status is None or url not in status:
                d.status = ResolutionStatus.not_attempted
                d.notes.append(f"{url}: enrich call failed")
                continue
            facts = status[url]
            d.considered, d.profile_url = 1, url
            if facts is None:
                d.notes.append(f"{url}: not_found or redacted")
                continue
            d.status, d.method, d.confidence = (
                ResolutionStatus.resolved,
                ResolutionMethod.linkedin_url,
                1.0,
            )
            d.facts = facts
            d.log_record_id = client.record_id_for(facts.source_request_id)

    # 2. email -> Person Identify (skipped when the plan does not include it)
    emails = {s.staff_id: s.email for s in staff if s.staff_id not in done and s.email}
    if emails and client.enabled("/person/identify"):
        for sid, email in emails.items():
            try:
                hits = client.identify_persons([email])
            except CrustdataError as e:
                say(f"person identify unavailable ({type(e).__name__}); using search")
                break
            if len(hits) == 1:
                d = ds[sid]
                d.status, d.method = (
                    ResolutionStatus.resolved,
                    ResolutionMethod.person_identify_email,
                )
                score = hits[0].score if hits[0].score is not None else 1.0
                d.confidence = max(0.0, min(1.0, float(score)))
                d.profile_url, d.considered = hits[0].profile_url, 1
                d.log_record_id = client.record_id_for(hits[0].request_id)
                done.add(sid)

    # 3. Person Search: name + company, then name only
    for s in staff:
        if s.staff_id in done:
            continue
        d, name = ds[s.staff_id], display_name(s)
        try:
            cands = client.search_person(name, employer=company) if company else []
            if cands:
                d.considered += len(cands)
                d.log_record_id = client.record_id_for(cands[0].request_id)
                if len(cands) == 1:
                    d.status, d.method = ResolutionStatus.resolved, ResolutionMethod.person_search
                    d.confidence, d.profile_url = SEARCH_ACCEPT_CONFIDENCE, cands[0].profile_url
                    d.notes.append(f"only {name} with {company} in their employment history")
                else:
                    _judge(judge, s, company, cands, d)
                continue
            cands = client.search_person(name)
        except CrustdataError as e:
            say(f"person search failed for {s.staff_id}: {e}")
            d.status = ResolutionStatus.not_attempted
            continue
        d.considered += len(cands)
        if not cands:
            d.notes.append(f"no profile named {name}")
            continue
        d.log_record_id = client.record_id_for(cands[0].request_id)
        # No judge here: none of these profiles lists the audited company, so nothing in
        # Crustdata can confirm any of them is our staff member; a model could only guess.
        d.status = ResolutionStatus.ambiguous
        d.notes.append(f"{len(cands)} namesakes of {name}, none lists {company} in their history")

    # enrich accepted profiles that have no facts yet, in one batch
    need = sorted(
        {
            d.profile_url
            for d in ds.values()
            if d.facts is None and d.profile_url and d.status == ResolutionStatus.resolved
        }
    )
    enriched: dict[str, PersonFacts | None] = {}
    if need:
        try:
            enriched = client.enrich_persons_status(need)
        except CrustdataError as e:
            say(f"person enrich failed for {len(need)} profiles: {e}")
    for d in ds.values():
        if d.facts is None and d.profile_url in enriched:
            d.facts = enriched[d.profile_url]
        if d.status == ResolutionStatus.resolved and d.facts is None:
            # an identity without facts cannot carry a finding: the gate must see a gap
            d.status = ResolutionStatus.unresolved
            d.notes.append("profile not enriched (not_found, redacted or call failed)")

    out = []
    for s in staff:
        d = ds[s.staff_id]
        res = Resolution(
            status=d.status,
            method=d.method if d.status == ResolutionStatus.resolved else None,
            confidence=d.confidence,
            candidates_considered=d.considered,
            log_record_id=d.log_record_id,
        )
        out.append(s.model_copy(update={"resolution": res, "crustdata": d.facts}))

    n_res = sum(s.resolution.status == ResolutionStatus.resolved for s in out)
    say(
        f"staff: {n_res}/{len(out)} resolved (company {company!r}); "
        f"{client.calls - calls0} Crustdata calls, {client.credits_spent - credits0:g} credits"
    )
    return out
