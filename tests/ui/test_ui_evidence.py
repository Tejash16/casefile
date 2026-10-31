"""Evidence tab (b3): log parsing, T16 path drawing, and the panel rendering in Streamlit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")

from casefile.ui import evidence as panel  # noqa: E402
from casefile.ui.evidence import DATA_SOURCE, path_dot  # noqa: E402

T16 = {
    "evidence_id": "E95",
    "test_id": "T16",
    "hypothesis_ids": ["H1"],
    "subject_ids": ["S004"],
    "object_ids": ["V017"],
    "direction": "supports",
    "strength": 0.75,
    "summary": "Staff member S004 is linked to vendor V017 in 3 steps through employment.",
    "quote": "staff:S004 -[resolution: crustdata:person:1@x]- cdperson:1 -[employment: "
    "crustdata:person:1@x employment[0]: DocRack, Co-Founder]- cdco:71095782 "
    "-[resolution: crustdata:company:71095782@y]- vendor:V017",
    "source": {
        "kind": "graph",
        "refs": ["staff:S004", "cdperson:1", "cdco:71095782", "vendor:V017"],
    },
    "sha256": "0" * 64,
    "log_record_id": "r1",
}


def _log(path: Path) -> None:
    recs = [
        {
            "record_id": "a",
            "action_type": "rule_test",
            "record_phase": "pre_execution",
            "action_detail": {"name": "T05", "test": "threshold_structuring"},
        },
        {
            "record_id": "b",
            "action_type": "rule_test",
            "record_phase": "post_execution",
            "parent_record_id": "a",
            "outcome": {"status": "ok", "evidence_ids": ["E1", "E2"]},
        },
        {
            "record_id": "c",
            "action_type": "rule_test",
            "record_phase": "pre_execution",
            "action_detail": {"name": "T16", "args": ["S004", "V017"]},
        },
        {
            "record_id": "d",
            "action_type": "rule_test",
            "record_phase": "post_execution",
            "parent_record_id": "c",
            "outcome": {"status": "ok", "evidence_ids": ["E95"]},
        },
        {"record_id": "e", "action_type": "tool_call", "record_phase": "pre_execution"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n{partial", encoding="utf-8")


def test_tests_run_reads_rule_records_and_tolerates_a_partial_line(tmp_path):
    _log(tmp_path / "log.jsonl")
    rows = {r["test"]: r for r in panel.tests_run(tmp_path / "log.jsonl")}
    assert rows["T05"]["hits"] == 2 and rows["T05"]["data source"] == "Ledger"
    assert rows["T16"]["name"] == "graph_path" and rows["T16"]["data source"] == "Both"
    assert panel.tests_run(tmp_path / "missing.jsonl") == []


def test_data_source_mapping():
    assert {DATA_SOURCE[t] for t in ("T13", "T15", "T17")} == {"Crustdata"}
    assert {DATA_SOURCE[t] for t in ("T01", "T03", "T16")} == {"Both"}
    assert {DATA_SOURCE[f"T{i:02d}"] for i in range(4, 13)} == {"Ledger"}


def test_path_dot_draws_a_chain_and_masks_identifiers_under_redact():
    dot = path_dot(T16)
    assert "rankdir=LR" in dot and dot.count("->") == 3
    assert 'label="employment"' in dot and "Crustdata company" in dot
    phone = {
        **T16,
        "source": {"kind": "graph", "refs": ["staff:S003", "phone:9822041736", "vendor:V023"]},
        "quote": "staff:S003 -[phone: x]- phone:9822041736 -[phone: y]- vendor:V023",
    }
    assert "9822041736" in path_dot(phone)
    assert "9822041736" not in path_dot(phone, redact=True)
    assert path_dot({**T16, "test_id": "T05"}) is None


def _app(out_dir: str, running: bool = False) -> None:
    from pathlib import Path

    from casefile.ui.evidence import render

    render(Path(out_dir), {"running": running, "redact": True})


def test_panel_renders_empty_state_and_full_run(tmp_path):
    from streamlit.testing.v1 import AppTest

    empty = AppTest.from_function(_app, args=(str(tmp_path),)).run(timeout=30)
    assert not empty.exception
    assert any("appear" in i.value for i in empty.info)

    _log(tmp_path / "log.jsonl")
    (tmp_path / "evidence.json").write_text(json.dumps([T16]), encoding="utf-8")
    (tmp_path / "findings.json").write_text(
        json.dumps(
            [
                {
                    "hypothesis_id": "H1",
                    "typology": "conflict_of_interest",
                    "subjects": ["S004"],
                    "objects": ["V017"],
                    "verdict": "Substantiated",
                    "supporting_evidence": ["E95"],
                    "counter_evidence": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    full = AppTest.from_function(_app, args=(str(tmp_path),)).run(timeout=30)
    assert not full.exception
    assert full.selectbox(key="b3_evidence_hypothesis").options[1].startswith("H1")
    full.selectbox(key="b3_evidence_hypothesis").select_index(1).run(timeout=30)
    assert not full.exception
