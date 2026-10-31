"""Live smoke tests against the Anthropic API. Run with CASEFILE_LIVE=1; skipped otherwise."""

from __future__ import annotations

import os

import pytest
from agent_data import H1, LEDGER_STATS, RESOLUTIONS, STAFF, TIP, VENDORS, ev
from agent_fakes import read_log

from casefile.agents import client, critique, gate, match, propose, write
from casefile.schemas import Direction, MatchVerdict

pytestmark = pytest.mark.skipif(os.environ.get("CASEFILE_LIVE") != "1", reason="CASEFILE_LIVE!=1")


@pytest.fixture(autouse=True)
def real_client(audit_log):
    client.set_client(None)
    client.reset_usage_totals()
    yield


def test_live_match_ambiguous_is_unsure(audit_log):
    d = match.judge_candidates(
        {"name_raw": "Orbital Fasteners Pvt Ltd"},
        [
            {"name": "Orbital Fasteners", "domain": None, "hq": "India"},
            {"name": "Orbital Fastener Systems", "domain": None, "hq": "India"},
        ],
        "company",
    )
    assert d.decision == MatchVerdict.unsure, d


def test_live_propose_and_cache(audit_log):
    hs = propose.propose(TIP, LEDGER_STATS, VENDORS, STAFF)
    assert 3 <= len(hs) <= 8
    assert all(h.tests_to_run for h in hs)
    # second identical call should read the cached system prefix
    propose.propose(TIP, LEDGER_STATS, VENDORS, STAFF)
    posts = [r for r in read_log(audit_log) if r["outcome"] and r["outcome"].get("status") == "ok"]
    assert posts[-1]["outcome"]["cache_read"] > 0, posts[-1]["outcome"]


def test_live_critique_gate_write(audit_log):
    evidence = [
        ev("E1", "T15", Direction.supports, 0.9),
        ev("E2", "T05", Direction.supports, 0.7),
        ev("E3", "T13", Direction.refutes, 0.3),
    ]
    crit = critique.critique(H1, evidence)
    assert crit.rationale and all(s.evidence_ids for s in crit.rationale)
    finding = gate.decide(H1, evidence, crit, RESOLUTIONS)
    case = write.write_case_file(
        [finding],
        evidence,
        {
            "case_id": "live",
            "company_name": "Acme",
            "generated_at": "now",
            "tip": TIP,
            "hypotheses": [H1],
        },
    )
    assert case.executive_summary and all(s.evidence_ids for s in case.executive_summary)
    filt = [
        r
        for r in read_log(audit_log)
        if r["action_detail"].get("name") == "writer_citation_filter" and r["outcome"]
    ]
    assert filt[-1]["outcome"]["summary_source"] == "writer", filt[-1]["outcome"]
