"""propose, match and critique against a fake client: prompts, validation and conversion."""

from __future__ import annotations

import pytest
from agent_data import H1, LEDGER_STATS, STAFF, TIP, VENDORS, ev
from agent_fakes import message

from casefile.agents import client, critique, match, propose
from casefile.schemas import Direction, MatchVerdict, Typology, Verdict


def hyp(**kw):
    base = {
        "typology": "conflict_of_interest",
        "statement": "Approver S004 steered spend to V017 (conflict_of_interest).",
        "subjects": ["S004"],
        "objects": ["V017"],
        "tests_to_run": ["T15", "T05"],
        "prior_score": 0.6,
        "origin": "tip",
        "alternative_to_tip": False,
        "rationale": "The tip names S004.",
    }
    return {**base, **kw}


GOOD = {
    "hypotheses": [
        hyp(),
        hyp(
            typology="shell_company",
            objects=["V017"],
            subjects=[],
            tests_to_run=["T13", "T02"],
            origin="screen",
        ),
        hyp(
            typology="conflict_of_interest",
            subjects=["S001"],
            tests_to_run=["T15"],
            statement="Approver S001, not S004, holds the V017 link (conflict_of_interest).",
            alternative_to_tip=True,
        ),
    ]
}


# ---------------------------------------------------------------- propose


def test_propose_prompt_has_stats_not_rows_and_data_before_instructions():
    system, messages = propose.build_request(TIP, LEDGER_STATS, VENDORS, STAFF, None)
    user = messages[0]["content"]
    for tag in ("<tip>", "<ledger_stats>", "<vendors>", "<staff>", "<instructions>"):
        assert tag in user
    assert user.index("<staff>") < user.index("<instructions>")
    assert '"spend_inr": 4860000' in user and '"invoice_count": 14' in user
    assert "<typologies>" in system[1] and "<tests>" in system[2]
    assert "T17" in system[2]


def test_propose_reads_scalar_spend_per_vendor():
    stats = {"row_count": 4, "spend_per_vendor": {"V017": "988000"}}
    _, messages = propose.build_request(TIP, stats, VENDORS, STAFF)
    user = messages[0]["content"]
    assert '"spend_inr": "988000"' in user and "spend_per_vendor" not in user


def test_propose_refuses_raw_rows():
    with pytest.raises(propose.LedgerRowsInPrompt):
        propose.build_request(TIP, {"sample": [{"row_id": "L1", "amount": 5}]}, VENDORS, STAFF)


def test_propose_menu_filter():
    system, _ = propose.build_request(TIP, {}, VENDORS, STAFF, ["shell_company"])
    assert "`shell_company`" in system[1] and "`kickback`" not in system[1]


def test_propose_returns_typed_hypotheses(fake):
    fake.responses = [message(GOOD)]
    out = propose.propose(TIP, LEDGER_STATS, VENDORS, STAFF, [t.value for t in Typology])
    assert [h.hypothesis_id for h in out] == ["H1", "H2", "H3"]
    assert out[1].typology == Typology.shell_company and out[1].origin == "screen"
    assert out[2].rationale.startswith("Alternative to the tip.")


def test_propose_requires_an_alternative_to_tip(fake):
    no_alt = {"hypotheses": [dict(h, alternative_to_tip=False) for h in GOOD["hypotheses"]]}
    fake.responses = [message(no_alt), message(GOOD)]
    propose.propose(TIP, LEDGER_STATS, VENDORS, STAFF)
    assert "alternative_to_tip" in fake.calls[1]["messages"][0]["content"][-1]["text"]
    assert fake.calls[0]["model"] == client.MODEL_STRONG
    assert fake.calls[0]["output_config"]["effort"] == "low"


def test_propose_retries_on_unknown_ids_and_bad_count(fake):
    bad = {"hypotheses": [hyp(subjects=["S999"], tests_to_run=["T99"])]}
    fake.responses = [message(bad), message(GOOD)]
    out = propose.propose(TIP, LEDGER_STATS, VENDORS, STAFF)
    assert len(out) == 3
    err = fake.calls[1]["messages"][0]["content"][-1]["text"]
    assert "unknown staff ids ['S999']" in err and "unknown test ids ['T99']" in err
    assert "expected 3-8 hypotheses, got 1" in err


# ---------------------------------------------------------------- match


CANDS = [
    {"name": "Orbital Fasteners", "domain": "orbitalfasteners.in", "hq": "Pune, India"},
    {"name": "Orbital Fasteners Inc", "domain": "orbitalfasteners.com", "hq": "Ohio, USA"},
]


def test_match_prompt_and_fast_model(fake):
    fake.responses = [message({"decision": "unsure", "index": None, "reason": "two fit"})]
    d = match.judge_candidates({"name_raw": "Orbital Fasteners Pvt Ltd", "city": None}, CANDS)
    assert d.decision == MatchVerdict.unsure and d.index is None and d.log_record_id
    sent = fake.calls[0]
    assert sent["model"] == client.MODEL_FAST
    assert "temperature" not in sent
    assert sent["output_config"]["effort"] == "low"
    user = sent["messages"][0]["content"]
    assert '<candidate index="1">' in user and "city" not in user


def test_match_yes_needs_valid_index(fake):
    fake.responses = [
        message({"decision": "yes", "index": 5, "reason": "x"}),
        message({"decision": "yes", "index": 0, "reason": "domain matches"}),
    ]
    d = match.judge_candidates("Orbital Fasteners, Pune", CANDS, "company")
    assert d.decision == MatchVerdict.yes and d.index == 0


def test_match_no_candidates_skips_model(fake):
    assert match.judge_candidates("x", [], "person").decision == MatchVerdict.no
    assert fake.calls == []


# ---------------------------------------------------------------- critique

EVIDENCE = [ev("E1", "T15", Direction.supports, 0.9), ev("E2", "T05", Direction.refutes, 0.4)]


def test_critique_fresh_context_and_citations(fake):
    fake.responses = [
        message(
            {
                "model_verdict": "Unsubstantiated",
                "rationale": [{"text": "S004 worked at V017.", "evidence_ids": ["E1"]}],
                "strongest_counter": "E2",
                "missing_tests": ["T16"],
            }
        )
    ]
    out = critique.critique(H1, EVIDENCE)
    assert out.model_verdict == Verdict.Unsubstantiated
    assert out.strongest_counter == "E2" and out.missing_tests == ["T16"]
    assert out.rationale[0].evidence_ids == ["E1"]
    user = fake.calls[0]["messages"][0]["content"]
    assert "PROPOSER-REASONING-MARKER" not in user and "prior" not in user
    assert '<evidence id="E1" test="T15" direction="supports" strength="0.90">' in user
    assert fake.calls[0]["model"] == client.MODEL_STRONG


def test_critique_rejects_uncited_and_unknown_ids(fake):
    bad = {
        "model_verdict": "Substantiated",
        "rationale": [
            {"text": "Uncited.", "evidence_ids": []},
            {"text": "Bad id.", "evidence_ids": ["E77"]},
        ],
        "strongest_counter": "E99",
        "missing_tests": [],
    }
    good = dict(bad, rationale=[{"text": "Ok.", "evidence_ids": ["E2"]}], strongest_counter=None)
    fake.responses = [message(bad), message(good)]
    out = critique.critique(H1, EVIDENCE)
    err = fake.calls[1]["messages"][0]["content"][-1]["text"]
    assert "sentence 1 cites no evidence id" in err and "E77" in err and "E99" in err
    assert out.rationale[0].text == "Ok."


def test_critique_without_evidence_skips_model(fake):
    out = critique.critique(H1, [])
    assert out.model_verdict == Verdict.Unsubstantiated and fake.calls == []


def test_critique_all_parallel_and_failure_isolated(fake):
    ok = {
        "model_verdict": "Substantiated",
        "rationale": [{"text": "Fact.", "evidence_ids": ["E1"]}],
        "strongest_counter": None,
        "missing_tests": [],
    }
    h2 = H1.model_copy(update={"hypothesis_id": "H2"})

    def respond(kwargs):
        user = kwargs["messages"][0]["content"]
        return RuntimeError("boom") if 'id="H2"' in user else message(ok)

    fake.responses = [respond, respond]
    out = critique.critique_all([(H1, EVIDENCE), (h2, EVIDENCE)])
    assert out["H1"].model_verdict == Verdict.Substantiated
    assert out["H2"].model_verdict == Verdict.Unsubstantiated and out["H2"].rationale == []
