from __future__ import annotations

from decimal import Decimal

from agent_data import H1, RESOLUTIONS, ev
from agent_fakes import read_log

from casefile.agents import gate
from casefile.schemas import (
    CriticOutput,
    Direction,
    Resolution,
    ResolutionStatus,
    Sentence,
    Verdict,
    VerdictBy,
)

S, R, N = Direction.supports, Direction.refutes, Direction.neutral
SUP = gate.SUPPORT_MIN_STRENGTH
REF = gate.REFUTE_MIN_STRENGTH


def critic(verdict: Verdict, *ids: str) -> CriticOutput:
    return CriticOutput(
        hypothesis_id="H1",
        model_verdict=verdict,
        rationale=[Sentence(text=f"Fact {i}.", evidence_ids=[i]) for i in ids],
    )


def test_substantiated_two_families(audit_log):
    evidence = [ev("E1", "T15", S, SUP + 0.2), ev("E2", "T05", S, SUP)]
    f = gate.decide(H1, evidence, critic(Verdict.Substantiated, "E1"), RESOLUTIONS)
    assert f.verdict == Verdict.Substantiated
    assert f.verdict_by == VerdictBy.gate
    assert f.supporting_evidence == ["E1", "E2"]
    assert f.rationale[0].evidence_ids == ["E1"]
    rec = read_log(audit_log)[-1]
    assert rec["action_type"] == "gate"
    assert rec["outcome"]["rule"] == gate.RULE_SUBSTANTIATED
    assert rec["outcome"]["override"] is False
    assert rec["outcome"]["gate_verdict"] == "Substantiated"
    assert rec["outcome"]["model_verdict"] == "Substantiated"


def test_same_family_is_not_enough():
    evidence = [ev("E1", "T05", S, 0.9), ev("E2", "T06", S, 0.9)]  # both billing
    f = gate.decide(H1, evidence, critic(Verdict.Substantiated, "E1"), RESOLUTIONS)
    assert f.verdict == Verdict.Unsubstantiated
    assert f.verdict_by == VerdictBy.gate_override_of_model


def test_weak_support_is_not_enough():
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T05", S, SUP - 0.01)]
    assert gate.decide(H1, evidence, None, RESOLUTIONS).verdict == Verdict.Unsubstantiated


def test_strong_refutation_blocks_substantiated(audit_log):
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T05", S, 0.9), ev("E3", "T13", R, REF)]
    f = gate.decide(H1, evidence, critic(Verdict.Substantiated, "E1"), RESOLUTIONS)
    assert f.verdict == Verdict.Unsubstantiated
    assert f.counter_evidence == ["E3"]
    rec = read_log(audit_log)[-1]
    assert rec["outcome"]["override"] is True and rec["outcome"]["rule"] == gate.RULE_DEFAULT


def test_weak_refutation_does_not_block():
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T05", S, 0.9), ev("E3", "T13", R, REF - 0.01)]
    assert gate.decide(H1, evidence, None, RESOLUTIONS).verdict == Verdict.Substantiated


def test_unfounded(audit_log):
    evidence = [ev("E1", "T15", R, 0.95), ev("E2", "T05", S, SUP - 0.1), ev("E3", "T16", N, 0.5)]
    f = gate.decide(H1, evidence, critic(Verdict.Unsubstantiated, "E1"), RESOLUTIONS)
    assert f.verdict == Verdict.Unfounded
    assert f.verdict_by == VerdictBy.gate_override_of_model
    assert f.confidence == 0.95
    assert f.amount_at_issue_inr is None
    assert read_log(audit_log)[-1]["outcome"]["rule"] == gate.RULE_UNFOUNDED


def test_refutation_with_strong_support_is_unsubstantiated():
    evidence = [ev("E1", "T15", R, 0.95), ev("E2", "T05", S, 0.8)]
    assert gate.decide(H1, evidence, None, RESOLUTIONS).verdict == Verdict.Unsubstantiated


def test_no_evidence_is_unsubstantiated():
    f = gate.decide(H1, [], critic(Verdict.Unsubstantiated), RESOLUTIONS)
    assert f.verdict == Verdict.Unsubstantiated and f.verdict_by == VerdictBy.gate


def test_unresolved_entity_forces_unsubstantiated(audit_log):
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T05", S, 0.9)]
    res = dict(RESOLUTIONS, V017=Resolution(status=ResolutionStatus.unresolved))
    f = gate.decide(H1, evidence, critic(Verdict.Substantiated, "E1"), res)
    assert f.verdict == Verdict.Unsubstantiated
    assert f.verdict_by == VerdictBy.gate_override_of_model
    assert "vendor V017 unresolved in Crustdata" in f.data_gaps
    assert read_log(audit_log)[-1]["outcome"]["rule"] == gate.RULE_UNRESOLVED


def test_missing_resolution_counts_as_unresolved():
    evidence = [ev("E1", "T15", R, 0.95)]
    res = {"V017": RESOLUTIONS["V017"]}
    f = gate.decide(H1, evidence, None, res)
    assert f.verdict == Verdict.Unsubstantiated
    assert "staff S004 not_attempted in Crustdata" in f.data_gaps


def test_evidence_filter_and_rationale_filter():
    other = ev("E9", "T13", R, 0.99, hyp=["H2"])  # another hypothesis: ignored
    screening = ev("E8", "T08", S, 0.4, hyp=[])  # untagged but about S004/V017: kept
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T05", S, 0.9), other, screening]
    crit = critic(Verdict.Substantiated, "E1", "E9")
    f = gate.decide(H1, evidence, crit, RESOLUTIONS)
    assert f.verdict == Verdict.Substantiated
    assert "E9" not in f.counter_evidence
    assert "E8" in f.supporting_evidence
    assert [s.evidence_ids for s in f.rationale] == [["E1"]]


def test_amount_at_issue_sums_supporting_ledger_rows():
    evidence = [
        ev("E1", "T15", S, 0.9, refs=["L1", "L2"]),
        ev("E2", "T05", S, 0.9, refs=["L2", "L3"]),
    ]
    amounts = {"L1": Decimal("100"), "L2": Decimal("250.50"), "L3": Decimal("49.50"), "L4": 7}
    f = gate.decide(H1, evidence, None, RESOLUTIONS, ledger_amounts=amounts)
    assert f.amount_at_issue_inr == Decimal("400.00")


def test_missing_tests_become_data_gaps():
    crit = critic(Verdict.Unsubstantiated)
    crit = crit.model_copy(update={"missing_tests": ["T15", "T13"]})
    f = gate.decide(H1, [ev("E1", "T15", S, 0.5)], crit, RESOLUTIONS)
    assert f.data_gaps == ["test T13 not run for H1"]
