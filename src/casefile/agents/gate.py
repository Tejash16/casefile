"""The verdict gate: deterministic rules from docs/contract.md section 7. The model never decides.

Rules, in order:
1. Any subject or object whose `resolution.status != resolved` (or with no resolution at all)
   forces Unsubstantiated and adds a data gap, regardless of the evidence or the model.
2. Substantiated: >= 2 supporting evidence objects from >= 2 different test families, each with
   strength >= 0.6, and no refuting evidence with strength >= 0.7.
3. Unfounded: >= 1 refuting evidence with strength >= 0.7 and no supporting evidence >= 0.6.
4. Otherwise Unsubstantiated.
If the gate's verdict differs from the critic's, `verdict_by = gate_override_of_model` and the gate
log record says which rule fired.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from itertools import combinations

from casefile.agents._audit import AuditSink, get_audit
from casefile.agents.models import test_families
from casefile.schemas import (
    CriticOutput,
    Direction,
    EvidenceObject,
    Finding,
    Hypothesis,
    Resolution,
    ResolutionStatus,
    Sentence,
    SourceKind,
    Verdict,
    VerdictBy,
)

SUPPORT_MIN_STRENGTH = 0.6
REFUTE_MIN_STRENGTH = 0.7
MIN_SUPPORTING = 2
MIN_FAMILIES = 2

GATE_ASSUMPTIONS = {
    "gate_support_min_strength": str(SUPPORT_MIN_STRENGTH),
    "gate_refute_min_strength": str(REFUTE_MIN_STRENGTH),
    "gate_min_supporting_evidence": str(MIN_SUPPORTING),
    "gate_min_test_families": str(MIN_FAMILIES),
    "gate_unresolved_entity": "forces Unsubstantiated",
}

RULE_UNRESOLVED = "unresolved_entity"
RULE_SUBSTANTIATED = "substantiated_two_families"
RULE_UNFOUNDED = "unfounded_strong_refutation"
RULE_DEFAULT = "default_unsubstantiated"


def relevant_evidence(h: Hypothesis, evidence: Sequence[EvidenceObject]) -> list[EvidenceObject]:
    """Evidence tagged with this hypothesis, plus untagged screening evidence about its entities."""
    ids = set(h.subjects) | set(h.objects)
    out = []
    for e in evidence:
        if h.hypothesis_id in e.hypothesis_ids:
            out.append(e)
        elif not e.hypothesis_ids and ids & (set(e.subject_ids) | set(e.object_ids)):
            out.append(e)
    return out


def _two_families(strong: Sequence[EvidenceObject], families: Mapping[str, list[str]]) -> bool:
    """True if two distinct evidence objects can be assigned two different families."""
    for a, b in combinations(strong, 2):
        fa = set(families.get(a.test_id, [a.test_id]))
        fb = set(families.get(b.test_id, [b.test_id]))
        if any(x != y for x in fa for y in fb):
            return True
    return False


def _unresolved(h: Hypothesis, resolutions: Mapping[str, Resolution | None]) -> list[str]:
    gaps = []
    for kind, ids in (("staff", h.subjects), ("vendor", h.objects)):
        for entity_id in ids:
            res = resolutions.get(entity_id)
            status = res.status if res is not None else ResolutionStatus.not_attempted
            if status != ResolutionStatus.resolved:
                gaps.append(f"{kind} {entity_id} {status} in Crustdata")
    return gaps


def _amount(
    supporting: Sequence[EvidenceObject], ledger_amounts: Mapping[str, Decimal] | None
) -> Decimal | None:
    if not ledger_amounts:
        return None
    rows = {
        ref
        for e in supporting
        if e.source.kind == SourceKind.ledger_rows
        for ref in e.source.refs
        if ref in ledger_amounts
    }
    if not rows:
        return None
    return sum((Decimal(ledger_amounts[r]) for r in sorted(rows)), Decimal(0))


def evaluate(
    h: Hypothesis,
    evidence: Sequence[EvidenceObject],
    resolutions: Mapping[str, Resolution | None],
) -> tuple[Verdict, str, float, list[str]]:
    """Pure rule evaluation: (verdict, rule, confidence, data_gaps). No logging."""
    families = test_families()
    supports = [e for e in evidence if e.direction == Direction.supports]
    refutes = [e for e in evidence if e.direction == Direction.refutes]
    strong_s = [e for e in supports if e.strength >= SUPPORT_MIN_STRENGTH]
    strong_r = [e for e in refutes if e.strength >= REFUTE_MIN_STRENGTH]
    top = max((e.strength for e in supports + refutes), default=0.0)

    gaps = _unresolved(h, resolutions)
    if gaps:
        return Verdict.Unsubstantiated, RULE_UNRESOLVED, round(1 - top, 3), gaps
    if len(strong_s) >= MIN_SUPPORTING and _two_families(strong_s, families) and not strong_r:
        conf = sum(e.strength for e in strong_s) / len(strong_s)
        return Verdict.Substantiated, RULE_SUBSTANTIATED, round(conf, 3), []
    if strong_r and not strong_s:
        return Verdict.Unfounded, RULE_UNFOUNDED, round(max(e.strength for e in strong_r), 3), []
    return Verdict.Unsubstantiated, RULE_DEFAULT, round(1 - top, 3), []


def decide(
    hypothesis: Hypothesis,
    evidence: Sequence[EvidenceObject],
    critic: CriticOutput | None,
    resolutions: Mapping[str, Resolution | None],
    ledger_amounts: Mapping[str, Decimal] | None = None,
    *,
    audit: AuditSink | None = None,
) -> Finding:
    audit = get_audit(audit)
    ev = relevant_evidence(hypothesis, evidence)
    model_verdict = critic.model_verdict if critic else None
    rid = audit.pre(
        "gate",
        {
            "name": "gate",
            "hypothesis_id": hypothesis.hypothesis_id,
            "model_verdict": model_verdict,
            "evidence_ids": [e.evidence_id for e in ev],
        },
    )
    verdict, rule, confidence, gaps = evaluate(hypothesis, ev, resolutions)
    override = model_verdict is not None and model_verdict != verdict

    ev_ids = {e.evidence_id for e in ev}
    tested = {e.test_id for e in ev}
    if critic:
        gaps += [
            f"test {t} produced no evidence for {hypothesis.hypothesis_id}"
            for t in critic.missing_tests
            if t not in tested
        ]
    rationale = [
        Sentence(text=s.text, evidence_ids=list(s.evidence_ids), require_citation=True)
        for s in (critic.rationale if critic else [])
        if s.evidence_ids and set(s.evidence_ids) <= ev_ids
    ]
    supporting = sorted(
        (e for e in ev if e.direction == Direction.supports), key=lambda e: -e.strength
    )
    counter = sorted((e for e in ev if e.direction == Direction.refutes), key=lambda e: -e.strength)

    audit.post(
        rid,
        {
            "status": "ok",
            "gate_verdict": verdict,
            "model_verdict": model_verdict,
            "rule": rule,
            "override": override,
            "confidence": confidence,
            "data_gaps": gaps,
        },
    )
    return Finding(
        hypothesis_id=hypothesis.hypothesis_id,
        verdict=verdict,
        verdict_by=VerdictBy.gate_override_of_model if override else VerdictBy.gate,
        model_verdict=model_verdict,
        supporting_evidence=[e.evidence_id for e in supporting],
        counter_evidence=[e.evidence_id for e in counter],
        confidence=confidence,
        amount_at_issue_inr=None
        if verdict == Verdict.Unfounded
        else _amount(supporting, ledger_amounts),
        rationale=rationale,
        data_gaps=gaps,
    )
