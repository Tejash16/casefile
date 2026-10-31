from __future__ import annotations

from agent_data import H1, TIP, ev
from agent_fakes import message, read_log, text_block

from casefile.agents import write
from casefile.schemas import Direction, Finding, Sentence, Verdict

E1 = ev("E1", "T15", Direction.supports, 0.9)
E2 = ev("E2", "T05", Direction.supports, 0.8)
E3 = ev("E3", "T13", Direction.refutes, 0.9)
EVIDENCE = [E1, E2, E3, ev("E4", "T08", Direction.neutral, 0.1)]

F1 = Finding(hypothesis_id="H1", verdict=Verdict.Substantiated, supporting_evidence=["E1", "E2"])
F2 = Finding(
    hypothesis_id="H2",
    verdict=Verdict.Unfounded,
    counter_evidence=["E3"],
    rationale=[Sentence(text="V023 has 400 staff.", evidence_ids=["E3"])],
)
META = {
    "case_id": "fixture",
    "company_name": "Acme",
    "generated_at": "2026-10-31T12:00:00Z",
    "tip": TIP,
    "scope": ["period"],
    "approach": ["six stages"],
    "assumptions": {"new_vendor_days": "90"},
    "hypotheses": [H1],
}


def cite(e, idx):
    return {
        "type": "search_result_location",
        "source": write.source_id(e),
        "title": e.summary,
        "cited_text": e.quote,
        "search_result_index": idx,
        "start_block_index": 0,
        "end_block_index": 1,
    }


def test_request_uses_search_results_with_hash_sources():
    _, messages = write.build_request([F1, F2], [E1, E2, E3], {"H1": H1})
    content = messages[0]["content"]
    sr = content[0]
    assert sr["type"] == "search_result" and sr["citations"] == {"enabled": True}
    assert sr["source"] == f"evidence:E1|{E1.sha256}"
    assert sr["content"][0]["text"] == E1.quote
    assert "<findings>" in content[-1]["text"] and content[-1]["text"].rstrip().endswith(
        "</instructions>"
    )
    assert 'verdict="Substantiated"' in content[-1]["text"]


def test_parse_keeps_cited_drops_uncited(fake, audit_log):
    blocks = [
        text_block("## Executive summary\n"),
        text_block("S004 was employed at V017 until 2024-11.", [cite(E1, 0)]),
        text_block(" This is an uncited flourish sentence here.\n\n## Finding H1\n"),
        text_block(
            "Invoices clustered under the limit at Orbital Pvt. Ltd. every month.", [cite(E2, 1)]
        ),
        text_block("\n\n## Finding H2\n"),
        text_block("V023 reports 400 employees.", [cite(E3, 2)]),
        text_block(
            " Forged citation sentence that should drop.",
            [dict(cite(E1, 0), source="evidence:E1|deadbeef", search_result_index=9)],
        ),
    ]
    fake.responses = [message(blocks)]
    case = write.write_case_file([F2, F1], EVIDENCE, META)

    assert [s.text for s in case.executive_summary] == ["S004 was employed at V017 until 2024-11."]
    assert case.executive_summary[0].evidence_ids == ["E1"]
    assert [f.hypothesis_id for f in case.findings] == ["H1", "H2"]  # Substantiated first
    h1 = case.findings[0].rationale
    assert len(h1) == 1 and "Pvt. Ltd." in h1[0].text and h1[0].evidence_ids == ["E2"]
    assert [s.text for s in case.findings[1].rationale] == ["V023 reports 400 employees."]
    assert {e.evidence_id for e in case.exhibits} == {"E1", "E2", "E3"}
    assert case.assumptions["new_vendor_days"] == "90"
    assert "gate_support_min_strength" in case.assumptions
    assert "Ravi in procurement" in case.predication.text
    assert case.metrics["model_calls"] == 1

    sent = fake.calls[0]
    assert "output_config" not in sent or "format" not in sent["output_config"]
    rec = read_log(audit_log)[-1]
    assert rec["action_detail"]["name"] == "writer_citation_filter"
    assert rec["outcome"]["dropped_sentences"] == 2
    for s in case.executive_summary + [s for f in case.findings for s in f.rationale]:
        assert s.evidence_ids


def test_writer_failure_falls_back_to_cited_sentences(fake, audit_log):
    fake.responses = [RuntimeError("down")]
    case = write.write_case_file([F1, F2], EVIDENCE, META)
    assert len(case.executive_summary) == 2
    assert all(s.evidence_ids for s in case.executive_summary)
    assert case.findings[0].rationale[0].evidence_ids == ["E1"]  # fallback from evidence
    assert case.findings[1].rationale[0].text == "V023 has 400 staff."  # critic rationale kept
    assert read_log(audit_log)[-1]["outcome"]["status"] == "fallback"
