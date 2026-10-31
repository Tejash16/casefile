"""Stub for casefile.agents (a2): no model calls; one hypothesis, echo-style critique and writer."""

from __future__ import annotations

from typing import Any

from casefile.schemas import (
    CaseFile,
    CriticOutput,
    Direction,
    EvidenceObject,
    Finding,
    Hypothesis,
    MatchDecision,
    MatchVerdict,
    Origin,
    Resolution,
    Sentence,
    StaffRecord,
    Tip,
    Typology,
    VendorRecord,
    Verdict,
)


def propose(
    tip: Tip,
    ledger_stats: dict[str, Any],
    vendors: list[VendorRecord],
    staff: list[StaffRecord],
    typologies: list[str],
) -> list[Hypothesis]:
    s, v = staff[0].staff_id, vendors[0].vendor_id
    return [
        Hypothesis(
            hypothesis_id="H1",
            typology=Typology.conflict_of_interest,
            statement=f"{s} approved payments to {v} while holding an undisclosed interest in it.",
            subjects=[s],
            objects=[v],
            tests_to_run=["T02", "T05", "T15"],
            prior_score=0.7,
            origin=Origin.tip,
            rationale="Stub hypothesis built from the first staff member and vendor.",
        )
    ]


def judge_candidates(query: str, candidates: list[dict], kind: str) -> MatchDecision:
    return MatchDecision(decision=MatchVerdict.unsure, reason="stub")


def critique(hypothesis: Hypothesis, evidence: list[EvidenceObject]) -> CriticOutput:
    support = [e for e in evidence if e.direction == Direction.supports]
    return CriticOutput(
        hypothesis_id=hypothesis.hypothesis_id,
        model_verdict=Verdict.Substantiated if len(support) >= 2 else Verdict.Unsubstantiated,
        rationale=[Sentence(text=e.summary, evidence_ids=[e.evidence_id]) for e in evidence],
    )


def decide(
    hypothesis: Hypothesis,
    evidence: list[EvidenceObject],
    critic: CriticOutput | None,
    resolutions: dict[str, Resolution],
    ledger_amounts: dict[str, Any] | None = None,
) -> Finding:
    if critic is None:
        critic = CriticOutput(model_verdict=Verdict.Unsubstantiated)
    return Finding(
        hypothesis_id=hypothesis.hypothesis_id,
        verdict=critic.model_verdict,
        model_verdict=critic.model_verdict,
        supporting_evidence=[e.evidence_id for e in evidence if e.direction == Direction.supports],
        counter_evidence=[e.evidence_id for e in evidence if e.direction == Direction.refutes],
        confidence=0.5,
        rationale=critic.rationale,
    )


def write_case_file(
    findings: list[Finding], evidence: list[EvidenceObject], meta: dict[str, Any]
) -> CaseFile:
    summary = [
        Sentence(
            text=f"Allegation {f.hypothesis_id} is {f.verdict}.",
            evidence_ids=f.supporting_evidence + f.counter_evidence,
        )
        for f in findings
    ]
    cited = {i for f in findings for i in f.supporting_evidence + f.counter_evidence}
    cited |= {i for f in findings for s in f.rationale for i in s.evidence_ids}
    tip: Tip = meta["tip"]
    return CaseFile(
        case_id=meta["case_id"],
        company_name=meta["company_name"],
        generated_at=meta["generated_at"],
        predication=Sentence(text=tip.text[:300]),
        executive_summary=summary,
        scope=meta.get("scope", []),
        approach=meta.get("approach", []),
        findings=findings,
        data_quality=meta.get("data_quality", []),
        assumptions=meta.get("assumptions", {}),
        exhibits=[e for e in evidence if e.evidence_id in cited],
        metrics=meta.get("metrics", {}),
        merkle_root=meta.get("merkle_root", ""),
        verify_command=meta.get("verify_command", ""),
    )
