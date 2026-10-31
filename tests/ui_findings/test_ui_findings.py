"""Headless render of the Findings tab with streamlit's AppTest (skipped if streamlit is absent)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from casefile.ui.findings import inr  # noqa: E402

APP = """
from pathlib import Path
from casefile.ui.findings import render
import streamlit as st
render(Path(st.session_state["out_dir"]), st.session_state["inputs"])
"""

FINDINGS = [
    {
        "hypothesis_id": "H2",
        "verdict": "Unfounded",
        "typology": "shell_company",
        "subjects": [],
        "objects": ["V002"],
        "statement": "V002 is a shell (shell_company).",
        "supporting_evidence": [],
        "counter_evidence": ["E2"],
        "confidence": 0.9,
        "amount_at_issue_inr": None,
        "rationale": [{"text": "V002 has 400 staff.", "evidence_ids": ["E2"]}],
        "data_gaps": [],
        "verdict_by": "gate",
        "model_verdict": "Unfounded",
    },
    {
        "hypothesis_id": "H1",
        "verdict": "Substantiated",
        "typology": "conflict_of_interest",
        "subjects": ["S004"],
        "objects": ["V017"],
        "statement": "S004 steered spend to V017 (conflict_of_interest).",
        "supporting_evidence": ["E1", "E9"],
        "counter_evidence": [],
        "confidence": 0.77,
        "amount_at_issue_inr": "2173588.25",
        "rationale": [{"text": "S004 co-founded V017.", "evidence_ids": ["E1"]}],
        "data_gaps": ["test T13 produced no evidence for H1"],
        "verdict_by": "gate_override_of_model",
        "model_verdict": "Unsubstantiated",
    },
]
EVIDENCE = [
    {
        "evidence_id": eid,
        "test_id": test,
        "direction": direction,
        "strength": 0.9,
        "summary": f"summary {eid}",
        "quote": f"quote {eid}",
        "source": {
            "kind": "crustdata_company",
            "refs": ["crustdata:company:1@2026-10-01"],
            "as_of": None,
        },
        "sha256": "ab" * 32,
        "log_record_id": "rec",
    }
    for eid, test, direction in (("E1", "T17", "supports"), ("E2", "T13", "refutes"))
]


def _run(tmp_path: Path, running: bool = False, with_files: bool = True) -> AppTest:
    if with_files:
        (tmp_path / "findings.json").write_text(json.dumps(FINDINGS), encoding="utf-8")
        (tmp_path / "evidence.json").write_text(json.dumps(EVIDENCE), encoding="utf-8")
        (tmp_path / "vendors.csv").write_text(
            "Vendor Code,Vendor Name\nV002,Bharat Forge\nV005,Clean Co\nV017,DocRack\n",
            encoding="utf-8",
        )
        (tmp_path / "case.json").write_text(
            json.dumps({"must_clear": ["V002", "V005"]}), encoding="utf-8"
        )
    at = AppTest.from_string(APP, default_timeout=30)
    at.session_state["out_dir"] = str(tmp_path)
    at.session_state["inputs"] = {
        "vendors": tmp_path / "vendors.csv",
        "case_json": tmp_path / "case.json" if with_files else None,
        "running": running,
        "redact": True,
    }
    return at.run()


def test_cards_ordered_with_badges_chips_and_cleared_list(tmp_path):
    at = _run(tmp_path)
    assert not at.exception
    md = " ".join(m.value for m in at.markdown)
    assert md.index("H1 · conflict_of_interest") < md.index("H2 · shell_company")
    assert "#c62828" in md and "#2e7d32" in md
    assert "S004 co-founded V017. :violet-badge[E1 · crustdata company 1@2026-10-01]" in md
    assert ":gray-badge[E9 · not in exhibits]" in md  # supporting chip even without a sentence
    assert "**Sources:** 0 ledger rows, 1 Crustdata record" in md
    labels = [e.label for e in at.expander]
    assert any(lbl.startswith(":violet-badge[E1") and "T17" in lbl for lbl in labels)
    assert any("updated_at:** 2026-10-01" in m.value for m in at.markdown)
    metrics = [m.value for m in at.metric]
    assert "INR 21,73,588.25" in metrics
    assert "gate (overrode model: Unsubstantiated)" in metrics
    cleared = at.dataframe[0].value
    assert list(cleared["Vendor"]) == ["V002", "V005"]  # V017 is implicated
    assert list(cleared["Expected clean"]) == ["yes", "yes"]


def test_empty_state_when_no_findings(tmp_path):
    at = _run(tmp_path, running=True, with_files=False)
    assert not at.exception
    assert "Findings appear here" in at.info[0].value


def test_source_labels_and_counts():
    from casefile.ui.findings import source_counts, source_label

    ledger = {"source": {"kind": "ledger_rows", "refs": ["L00042", "L00043"]}}
    person = {
        "source": {
            "kind": "crustdata_person",
            "refs": ["crustdata:person:8812@2026-10-24T16:58:10Z"],
        }
    }
    assert source_label(ledger) == ("gray", "ledger L00042 +1")
    assert source_label(person) == ("violet", "crustdata person 8812@2026-10-24")
    ev = {"E1": ledger, "E2": person, "E3": ledger}
    assert source_counts(["E1", "E2", "E3"], ev) == (2, 1)


def test_inr_grouping():
    assert inr("2173588.25") == "INR 21,73,588.25"
    assert inr(498000) == "INR 4,98,000.00"
    assert inr("999") == "INR 999.00"
    assert inr("12345678901") == "INR 12,34,56,78,901.00"
