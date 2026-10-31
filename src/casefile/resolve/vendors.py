"""Resolve vendor-master rows to Crustdata companies, then enrich the accepted ids in one batch.

Decision table (per vendor, first rule that applies wins):

1. Website or non-free-mail email domain -> Identify by `domains`; a candidate whose
   `primary_domain` or `all_domains` holds that domain is a hard match (`method=domain`).
2. Otherwise Identify by name (legal suffix stripped), `exact_match=true`; if no candidate is
   plausible, again with `exact_match=false`. A candidate is plausible only if the vendor's brand
   word appears in its name (Identify pads fictional names with unrelated 0.6 hits).
3. Leaders = plausible candidates within `identify_tie_margin` of the top score.
   - top >= `identify_accept` and one leader -> resolved (`identify_exact` / `identify_fuzzy`).
   - top >= `identify_accept`, several leaders, exactly one whose domain stem spells the name
     (Tata Steel ~ tatasteel.com) -> resolved.
   - top >= `identify_judge_min` -> a2's judge on the leaders: yes -> resolved (`llm_judge`),
     no -> unresolved, unsure / no judge / judge error -> ambiguous.
   - else unresolved.
Never `matches[0]` on name alone: "Infosys" returns six 1.0 matches.

The billed-volume plausibility check from the brief needs ledger totals, which this signature
does not receive; T13 (b3) compares headcount with billed volume instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from casefile.crustdata.client import CrustdataClient, CrustdataError
from casefile.resolve._common import (
    domain_of,
    domain_stem_matches,
    norm,
    plausible,
    safe_judge,
    same_country,
    say,
    strip_suffixes,
    threshold,
)
from casefile.schemas import (
    IdentifyResult,
    MatchVerdict,
    Resolution,
    ResolutionMethod,
    ResolutionStatus,
    VendorRecord,
)

JUDGE_MAX = 5


@dataclass
class Decision:
    status: ResolutionStatus
    method: ResolutionMethod | None = None
    confidence: float | None = None
    company_id: str | None = None
    log_record_id: str | None = None
    considered: int = 0
    notes: list[str] = field(default_factory=list)

    def resolution(self) -> Resolution:
        conf = None if self.confidence is None else max(0.0, min(1.0, float(self.confidence)))
        return Resolution(
            status=self.status,
            method=self.method,
            confidence=conf,
            candidates_considered=self.considered,
            log_record_id=self.log_record_id,
        )


def _score(c: dict[str, Any]) -> float:
    return float(c.get("confidence_score") or 0.0)


def _judge_view(c: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "name",
        "primary_domain",
        "website",
        "employee_count_range",
        "company_type",
        "year_founded",
        "industries",
        "linkedin_url",
        "confidence_score",
    )
    return {k: c.get(k) for k in keys}


def _vendor_view(v: VendorRecord) -> dict[str, Any]:
    return {
        "name": v.name_raw,
        "address": v.address,
        "city": v.city,
        "state": v.state,
        "country": v.country,
        "website": v.website,
        "email": v.email,
    }


def decide(
    query: str,
    result: IdentifyResult,
    method: ResolutionMethod,
    log_record_id: str | None,
    judge: Any = None,
    vendor: VendorRecord | None = None,
) -> Decision:
    """Rules 2-3 of the module docstring for one name query's Identify result."""
    cands = result.candidates
    d = Decision(ResolutionStatus.unresolved, considered=len(cands), log_record_id=log_record_id)
    plaus = [c for c in cands if plausible(query, c.get("name"))]
    if not plaus:
        d.notes.append(f"{len(cands)} candidates, none carries the name {query!r}")
        return d
    top = max(_score(c) for c in plaus)
    leaders = [c for c in plaus if _score(c) >= top - threshold("identify_tie_margin")]
    leaders.sort(key=_score, reverse=True)
    d.confidence = top

    def accept(c: dict[str, Any], how: ResolutionMethod, why: str) -> Decision:
        d.status, d.method, d.company_id = ResolutionStatus.resolved, how, c["crustdata_company_id"]
        d.confidence = _score(c)
        d.notes.append(why)
        return d

    if top >= threshold("identify_accept"):
        # a lone leader is accepted only under the vendor's exact (suffix-free) name; anything
        # looser is a name-only guess and goes to the judge. Country is checked after enrich.
        if len(leaders) == 1 and norm(leaders[0].get("name")) == norm(query):
            return accept(leaders[0], method, "only company with this exact name")
        stems = [c for c in leaders if domain_stem_matches(query, c.get("primary_domain"))]
        if len(stems) == 1:
            return accept(stems[0], method, f"tie broken by domain {stems[0]['primary_domain']}")
    if top < threshold("identify_judge_min"):
        d.notes.append(f"top score {top} below judge threshold")
        return d

    shortlist = leaders[:JUDGE_MAX]
    query_view: Any = _vendor_view(vendor) if vendor is not None else query
    verdict = safe_judge(judge, query_view, [_judge_view(c) for c in shortlist], "company")
    if verdict is None:
        d.status = ResolutionStatus.ambiguous
        d.notes.append(f"{len(leaders)} leaders at {top}; no judge decision")
        return d
    if verdict.log_record_id:
        d.log_record_id = verdict.log_record_id
    if verdict.decision == MatchVerdict.yes and verdict.index in range(len(shortlist)):
        return accept(shortlist[verdict.index], ResolutionMethod.llm_judge, verdict.reason)
    d.status = (
        ResolutionStatus.unresolved
        if verdict.decision == MatchVerdict.no
        else ResolutionStatus.ambiguous
    )
    d.notes.append(f"judge said {verdict.decision}: {verdict.reason}")
    return d


def _domain_decision(dom: str, result: IdentifyResult, rid: str | None) -> Decision | None:
    hits = [
        c
        for c in result.candidates
        if (c.get("primary_domain") or "").lower() == dom
        or dom in [x.lower() for x in c.get("all_domains") or []]
    ]
    if not hits:
        return None
    primary = [c for c in hits if (c.get("primary_domain") or "").lower() == dom]
    pool = primary or hits
    if len(pool) > 1:
        return None  # several companies claim the domain: fall through to the name rules
    c = pool[0]
    return Decision(
        ResolutionStatus.resolved,
        ResolutionMethod.domain,
        _score(c),
        c["crustdata_company_id"],
        rid,
        len(result.candidates),
        [f"domain {dom} matches {c.get('name')}"],
    )


def _queries(vendors: list[VendorRecord]) -> dict[str, str]:
    """vendor_id -> Identify query; spellings within `vendor_collapse_min` share one query."""
    reps: list[tuple[str, str]] = []  # (normalised, query)
    out: dict[str, str] = {}
    for v in vendors:
        key = norm(v.name_norm or v.name_raw)
        for rep_key, rep_query in reps:
            if fuzz.token_sort_ratio(key, rep_key) >= threshold("vendor_collapse_min"):
                out[v.vendor_id] = rep_query
                break
        else:
            q = strip_suffixes(v.name_raw)
            reps.append((key, q))
            out[v.vendor_id] = q
    return out


def _scope(client: CrustdataClient, dataset: str) -> None:
    if any(p.startswith(f"/{dataset}/") for p in client.scope):
        return
    try:
        client.describe_scope(dataset)
    except CrustdataError as e:
        say(f"describe_scope({dataset}) failed: {e}")


def resolve_vendors(
    vendors: list[VendorRecord], client: CrustdataClient, judge: Any = None
) -> list[VendorRecord]:
    _scope(client, "company")
    calls0, credits0 = client.calls, client.credits_spent
    decisions: dict[str, Decision] = {}
    seen: dict[str, int] = {}

    # 1. hard match by domain
    doms = {v.vendor_id: domain_of(v.website) or domain_of(v.email) for v in vendors}
    uniq = sorted({d for d in doms.values() if d})
    by_dom: dict[str, IdentifyResult] = {}
    if uniq:
        try:
            by_dom = dict(zip(uniq, client.identify_companies(uniq, by="domains"), strict=True))
        except CrustdataError as e:
            say(f"identify by domain failed: {e}")
    for v in vendors:
        dom = doms[v.vendor_id]
        if dom and dom in by_dom:
            r = by_dom[dom]
            seen[v.vendor_id] = len(r.candidates)
            hit = _domain_decision(dom, r, client.record_id_for(r.request_id))
            if hit is not None:
                decisions[v.vendor_id] = hit

    # 2-3. by name, exact then fuzzy
    pending = [v for v in vendors if v.vendor_id not in decisions]
    queries = _queries(pending)
    for exact in (True, False):
        todo = [v for v in pending if v.vendor_id not in decisions]
        qs = sorted({queries[v.vendor_id] for v in todo})
        if not qs:
            break
        try:
            results = dict(zip(qs, client.identify_companies(qs, exact=exact), strict=True))
        except CrustdataError as e:
            say(f"identify by name (exact={exact}) failed: {e}")
            break
        method = ResolutionMethod.identify_exact if exact else ResolutionMethod.identify_fuzzy
        for v in todo:
            r = results[queries[v.vendor_id]]
            rid = client.record_id_for(r.request_id)
            d = decide(queries[v.vendor_id], r, method, rid, judge=judge, vendor=v)
            d.considered += seen.get(v.vendor_id, 0)
            seen[v.vendor_id] = d.considered
            no_plausible = d.status == ResolutionStatus.unresolved and d.confidence is None
            if exact and no_plausible:
                continue  # try exact_match=false before giving up
            decisions[v.vendor_id] = d

    # enrich every accepted id in one batched call (2 credits per company)
    ids = sorted({d.company_id for d in decisions.values() if d.company_id})
    facts: dict[str, Any] = {}
    if ids:
        try:
            facts = {f.crustdata_company_id: f for f in client.enrich_companies(ids)}
        except CrustdataError as e:
            say(f"enrich failed for {len(ids)} companies: {e}")

    out: list[VendorRecord] = []
    for v in vendors:
        d = decisions.get(v.vendor_id)
        if d is None:  # every Identify call for it failed
            res = Resolution(
                status=ResolutionStatus.not_attempted,
                candidates_considered=seen.get(v.vendor_id, 0),
            )
            out.append(v.model_copy(update={"resolution": res, "crustdata": None}))
            continue
        fact = facts.get(d.company_id) if d.company_id else None
        if d.status == ResolutionStatus.resolved and fact is None:
            # an identity without facts cannot carry a finding: the gate must see a gap
            d.status, d.method, d.company_id = ResolutionStatus.unresolved, None, None
            d.notes.append("enrich returned no record")
        elif (
            fact is not None
            and d.method != ResolutionMethod.domain
            and not same_country(v.country, fact.hq_country)
        ):
            d.status, d.method, d.company_id, fact = ResolutionStatus.ambiguous, None, None, None
            d.notes.append(f"name matched but HQ country differs from {v.country!r}")
        out.append(v.model_copy(update={"resolution": d.resolution(), "crustdata": fact}))

    n_res = sum(v.resolution.status == ResolutionStatus.resolved for v in out)
    say(
        f"vendors: {n_res}/{len(out)} resolved; {client.calls - calls0} Crustdata calls, "
        f"{client.credits_spent - credits0:g} credits"
    )
    return out
