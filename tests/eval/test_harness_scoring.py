"""Scoring logic of tests/eval_harness.py on synthetic findings (no pipeline, no network)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from casefile.schemas import CaseFile, CaseSpec, Finding, Hypothesis, Sentence

_path = Path(__file__).resolve().parents[1] / "eval_harness.py"
_spec = importlib.util.spec_from_file_location("eval_harness", _path)
harness = importlib.util.module_from_spec(_spec)
sys.modules["eval_harness"] = harness  # dataclasses look the module up while building
_spec.loader.exec_module(harness)

SPEC = CaseSpec.model_validate(
    {
        "name": "career_overlap",
        "inputs": {"tip": "t", "ledger": "l", "vendors": "v", "staff": "s"},
        "expected": [
            {
                "typology": "conflict_of_interest",
                "subjects": ["S004"],
                "objects": ["V017"],
                "verdict": "Substantiated",
            },
            {"typology": "shell_company", "objects": ["V023"], "verdict": "Unfounded"},
        ],
        "must_clear": ["V002", "V009"],
    }
)


def case_with(*items: tuple[str, str, list[str], list[str], str]) -> CaseFile:
    hyps, findings = [], []
    for hid, typ, subj, obj, verdict in items:
        hyps.append(
            Hypothesis(hypothesis_id=hid, typology=typ, statement="s", subjects=subj, objects=obj)
        )
        findings.append(Finding(hypothesis_id=hid, verdict=verdict))
    return CaseFile(
        case_id="c",
        company_name="Acme",
        generated_at="now",
        predication=Sentence(text="tip"),
        hypotheses=hyps,
        findings=findings,
    )


def test_all_correct() -> None:
    case = case_with(
        ("H1", "conflict_of_interest", ["S004"], ["V017"], "Substantiated"),
        ("H2", "shell_company", [], ["V023"], "Unfounded"),
        ("H3", "kickback", ["S001"], ["V002"], "Unsubstantiated"),
    )
    r = harness.score(case, SPEC)
    assert r.ok, r.mismatches
    assert (r.planted_caught, r.planted) == (1, 1)
    assert (r.expected_correct, r.expected_total) == (2, 2)
    assert (r.substantiated_correct, r.substantiated) == (1, 1)
    assert r.turned_away == [] and r.unsubstantiated == 1


def test_wrong_verdict_and_missing() -> None:
    case = case_with(("H1", "conflict_of_interest", ["S004"], ["V017"], "Unsubstantiated"))
    r = harness.score(case, SPEC)
    assert not r.ok
    assert r.planted_caught == 0
    assert any("expected Substantiated, got H1=Unsubstantiated" in m for m in r.mismatches)
    assert any("shell_company" in m and "no such hypothesis" in m for m in r.mismatches)


def test_must_clear_vendor_turned_away() -> None:
    case = case_with(
        ("H1", "conflict_of_interest", ["S004"], ["V017"], "Substantiated"),
        ("H2", "shell_company", [], ["V023"], "Unfounded"),
        ("H3", "duplicate_billing", [], ["V009"], "Substantiated"),
    )
    r = harness.score(case, SPEC)
    assert r.turned_away == ["V009"]
    assert (r.substantiated_correct, r.substantiated) == (1, 2)
    assert not r.ok


def test_stray_substantiated_on_expected_unfounded() -> None:
    case = case_with(
        ("H1", "conflict_of_interest", ["S004"], ["V017"], "Substantiated"),
        ("H2", "shell_company", [], ["V023"], "Unfounded"),
        ("H4", "shell_company", ["S004"], ["V023"], "Substantiated"),
    )
    r = harness.score(case, SPEC)
    # exact match (H2, no subjects in expectation -> subjects ignored) still sees H4's verdict
    assert not r.ok
    assert any("expected Unfounded" in m for m in r.mismatches)


def test_subset_match_when_proposer_adds_objects() -> None:
    case = case_with(
        ("H1", "conflict_of_interest", ["S004"], ["V017", "V018"], "Substantiated"),
        ("H2", "shell_company", [], ["V023"], "Unfounded"),
    )
    assert harness.score(case, SPEC).ok


def test_table_renders() -> None:
    case = case_with(
        ("H1", "conflict_of_interest", ["S004"], ["V017"], "Substantiated"),
        ("H2", "shell_company", [], ["V023"], "Unfounded"),
    )
    runs = [harness.score(case, SPEC, run=i) for i in (1, 2, 3)]
    for r in runs:
        r.log_verifies, r.citation_validity, r.wall_seconds = True, 1.0, 10.0
    tbl = harness.table({"career_overlap": runs}, 3)
    assert "| career_overlap | 1/1, 1/1, 1/1 | 0 | 6/6 | 100% | 100% | 0% | 3/3 | 10.0 |" in tbl
    assert "**pass 3/3**" in tbl
