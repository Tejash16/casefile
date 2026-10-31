from pathlib import Path

import pytest
from typer.testing import CliRunner

from casefile import pipeline
from casefile.cli import app
from casefile.schemas import Sentence


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name in ("tip.txt", "ledger.csv", "vendors.csv", "staff.csv"):
        p = tmp_path / name
        p.write_text(f"placeholder {name}\n", encoding="utf-8")
        paths[name.split(".")[0]] = p
    return paths


LANDED = {"audit", "check", "render"}  # real modules on main; everything else stubbed here


@pytest.fixture
def all_stubs(monkeypatch):
    monkeypatch.setenv(
        "CASEFILE_FORCE_STUBS", ",".join(k for k in pipeline.REGISTRY if k not in LANDED)
    )


def test_run_end_to_end_on_stubs(inputs, tmp_path, all_stubs):
    out = tmp_path / "out"
    case = pipeline.run(inputs["tip"], inputs["ledger"], inputs["vendors"], inputs["staff"], out)
    for name in ("case_file.md", "exhibits.md", "evidence.json", "log.jsonl", "root.txt"):
        assert (out / name).exists(), name
    assert case.findings and case.hypotheses
    assert case.merkle_root
    assert case.metrics["log_records"] > 0
    assert "rules" in case.metrics["stubbed"]
    assert "render" not in case.metrics["stubbed"]

    from casefile.audit.verify import verify

    assert verify(out / "log.jsonl").ok


def test_one_failed_critique_does_not_abort_the_run(inputs, tmp_path, all_stubs, monkeypatch):
    from casefile.agents.client import ModelRefusalError
    from casefile.stubs import agents

    def refuse(hypothesis, evidence):
        raise ModelRefusalError("refused")

    monkeypatch.setattr(agents, "critique", refuse)
    out = tmp_path / "out"
    case = pipeline.run(inputs["tip"], inputs["ledger"], inputs["vendors"], inputs["staff"], out)
    assert [f.verdict for f in case.findings] == ["Unsubstantiated"]


def test_redact_hides_staff_names(inputs, tmp_path, all_stubs):
    out = tmp_path / "out"
    pipeline.run(
        inputs["tip"], inputs["ledger"], inputs["vendors"], inputs["staff"], out, redact=True
    )
    text = (out / "case_file.md").read_text(encoding="utf-8")
    assert "Asha Rao" not in text  # stub staff name


def test_uncited_sentence_exits_2(inputs, tmp_path, all_stubs, monkeypatch):
    from casefile.stubs import agents

    real_write = agents.write_case_file

    def uncited(findings, evidence, meta):
        case = real_write(findings, evidence, meta)
        return case.model_copy(update={"executive_summary": [Sentence(text="no citation")]})

    monkeypatch.setattr(agents, "write_case_file", uncited)
    args = ["investigate", "--out", str(tmp_path / "out")]
    for k, p in inputs.items():
        args += [f"--{k}", str(p)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2, result.output
