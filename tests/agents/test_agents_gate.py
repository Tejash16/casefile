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
    SourceKind,
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


def test_two_items_from_one_multi_family_test_are_one_line(monkeypatch):
    monkeypatch.setattr(gate, "test_families", lambda: {"T13": ["footprint", "identity"]})
    evidence = [ev("E1", "T13", S, 0.9), ev("E2", "T13", S, 0.9)]
    assert gate.decide(H1, evidence, None, RESOLUTIONS).verdict == Verdict.Unsubstantiated


def test_no_critic_means_no_override(audit_log):
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T05", S, 0.9)]
    f = gate.decide(H1, evidence, None, RESOLUTIONS)
    assert f.verdict == Verdict.Substantiated and f.model_verdict is None
    assert f.verdict_by == VerdictBy.gate
    assert read_log(audit_log)[-1]["outcome"]["override"] is False


def test_graph_path_does_not_count_as_a_second_family():
    # kickback-style: one billing signal plus graph paths built from the same employment edge
    evidence = [ev("E1", "T12", S, SUP), ev("E2", "T16", S, 0.75), ev("E3", "T16", S, 0.75)]
    assert gate.decide(H1, evidence, None, RESOLUTIONS).verdict == Verdict.Unsubstantiated


def test_graph_path_with_two_real_families_still_substantiates():
    evidence = [ev("E1", "T15", S, 0.9), ev("E2", "T12", S, SUP), ev("E3", "T16", S, 0.75)]
    f = gate.decide(H1, evidence, None, RESOLUTIONS)
    assert f.verdict == Verdict.Substantiated and "E3" in f.supporting_evidence


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


UNRESOLVED = Resolution(status=ResolutionStatus.unresolved)
SHELL = H1.model_copy(
    update={"typology": "shell_company", "subjects": [], "objects": ["V023"], "tests_to_run": []}
)


def test_unresolved_shell_substantiated_on_ledger_and_master_families(audit_log):
    evidence = [
        ev("E1", "T01", S, 0.9),  # identity: shares S003's address and phone
        ev("E2", "T11", S, 0.8),  # control: same user created and approved
        ev("E3", "T13", S, 0.9),  # footprint from Crustdata (no record): not counted
    ]
    evidence = [e.model_copy(update={"object_ids": ["V023"]}) for e in evidence]
    f = gate.decide(SHELL, evidence, critic(Verdict.Substantiated, "E1"), {"V023": UNRESOLVED})
    assert f.verdict == Verdict.Substantiated
    assert "vendor V023 unresolved in Crustdata" in f.data_gaps
    assert any(g.startswith("evidence E3 (T13) not counted") for g in f.data_gaps)
    out = read_log(audit_log)[-1]["outcome"]
    assert out["rule"] == gate.RULE_SUBSTANTIATED and out["excluded_evidence"] == ["E3"]


def test_unresolved_shell_with_one_ledger_family_stays_unsubstantiated():
    evidence = [ev("E1", "T01", S, 0.9), ev("E3", "T13", S, 0.9)]
    evidence = [e.model_copy(update={"object_ids": ["V023"]}) for e in evidence]
    assert gate.decide(SHELL, evidence, None, {"V023": UNRESOLVED}).verdict == (
        Verdict.Unsubstantiated
    )


def test_unresolved_person_coi_with_only_career_support_stays_unsubstantiated(audit_log):
    evidence = [
        ev("E1", "T15", S, 0.95),  # career overlap from S004's Crustdata record: not counted
        ev("E2", "T17", S, 0.9, kind=SourceKind.crustdata_company),  # founders match: not counted
        ev("E3", "T05", S, 0.8),  # billing: counts, but one family only
    ]
    res = dict(RESOLUTIONS, S004=UNRESOLVED)
    f = gate.decide(H1, evidence, critic(Verdict.Substantiated, "E1"), res)
    assert f.verdict == Verdict.Unsubstantiated
    assert f.verdict_by == VerdictBy.gate_override_of_model
    assert "staff S004 unresolved in Crustdata" in f.data_gaps
    assert read_log(audit_log)[-1]["outcome"]["excluded_evidence"] == ["E1", "E2"]


def test_unresolved_person_refutation_does_not_count():
    # T15 "no employment at the vendor" means nothing if we never found the right person
    res = dict(RESOLUTIONS, S004=UNRESOLVED)
    f = gate.decide(H1, [ev("E1", "T15", R, 0.95)], None, res)
    assert f.verdict == Verdict.Unsubstantiated


def test_crustdata_evidence_about_a_resolved_entity_still_counts():
    # S004 unresolved, but E1 is V017's own (resolved) company record and names only V017
    e1 = ev("E1", "T13", S, 0.9, kind=SourceKind.crustdata_company).model_copy(
        update={"subject_ids": []}
    )
    res = dict(RESOLUTIONS, S004=UNRESOLVED)
    f = gate.decide(H1, [e1, ev("E2", "T05", S, 0.9)], None, res)
    assert f.verdict == Verdict.Substantiated


def test_missing_resolution_counts_as_unresolved():
    res = {"V017": RESOLUTIONS["V017"]}
    f = gate.decide(H1, [ev("E1", "T15", R, 0.95)], None, res)
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
    assert f.data_gaps == ["test T13 produced no evidence for H1"]
