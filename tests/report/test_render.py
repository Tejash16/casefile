"""Renderer, citation check and redaction."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from casefile.audit.log import AuditLog
from casefile.audit.payloads import PayloadStore
from casefile.audit.verify import verify
from casefile.report.check import check_citations, citation_validity
from casefile.report.redact import Redactor, initials
from casefile.report.render import CitationError, inr, render
from casefile.schemas import (
    CaseFile,
    EvidenceObject,
    Finding,
    Hypothesis,
    Sentence,
    Source,
)

LEDGER = (
    "L00042 2025-03-14 Orbital Fasteners 4,98,000 approver S004\n"
    "L00057 2025-04-02 Orbital Fasteners 4,95,500 approver S004\n"
)
PERSON = json.dumps(
    {
        "name": "Ravi Kumar",
        "profile_url": "https://www.linkedin.com/in/ravi-kumar-1234",
        "employment[2]": "Orbital Fasteners, Analyst, 2021-06-01 to 2024-11-30",
    }
)
COMPANY = "headcount_total: 2; website: none; year_founded: 2024"


def make_case(store: PayloadStore) -> CaseFile:
    e1 = EvidenceObject(
        evidence_id="E1",
        test_id="T15",
        hypothesis_ids=["H1"],
        subject_ids=["S004"],
        object_ids=["V017"],
        direction="supports",
        strength=0.9,
        summary="Ravi Kumar worked at Orbital Fasteners until three months before the first payment.",
        quote="employment[2]: Orbital Fasteners, Analyst, 2021-06-01 to 2024-11-30",
        source=Source(
            kind="crustdata_person",
            refs=["crustdata:person:987@2026-10-01T00:00:00Z"],
            as_of="2026-10-01T00:00:00Z",
        ),
        sha256=store.put(PERSON),
        log_record_id="rec-1",
    )
    e2 = EvidenceObject(
        evidence_id="E2",
        test_id="T05",
        hypothesis_ids=["H1"],
        subject_ids=["S004"],
        object_ids=["V017"],
        direction="supports",
        strength=0.7,
        summary="Two invoices fall in the band just under S004's approval limit.",
        quote="L00042 2025-03-14 Orbital Fasteners 4,98,000 approver S004",
        source=Source(kind="ledger_rows", refs=["L00042", "L00057"]),
        sha256=store.put(LEDGER),
        log_record_id="rec-2",
    )
    e3 = EvidenceObject(
        evidence_id="E3",
        test_id="T13",
        hypothesis_ids=["H2"],
        object_ids=["V023"],
        direction="refutes",
        strength=0.8,
        summary="Crustdata shows the vendor is small.",
        quote="headcount_total: 2",
        source=Source(
            kind="crustdata_company",
            refs=["crustdata:company:555@2026-09-30T12:00:00Z"],
            as_of="2026-09-30T12:00:00Z",
        ),
        sha256=store.put(COMPANY),
        log_record_id="rec-3",
    )
    return CaseFile(
        case_id="career_overlap",
        company_name="Acme Components Pvt Ltd",
        generated_at="2026-10-31T13:00:00Z",
        predication=Sentence(text="A tip alleges that Ravi Kumar steers orders to Orbital Fasteners."),
        executive_summary=[
            Sentence(text="Ravi Kumar approved payments to his former employer.", evidence_ids=["E1", "E2"]),
        ],
        scope=["Ledger 2025-01-01 to 2025-12-31, 412 rows."],
        approach=["Six stages; Crustdata person/search x3, company/enrich x1."],
        hypotheses=[
            Hypothesis(
                hypothesis_id="H1",
                typology="conflict_of_interest",
                statement="Ravi Kumar (S004) steered payments to Orbital Fasteners (V017), his former employer.",
                subjects=["S004"],
                objects=["V017"],
            ),
            Hypothesis(
                hypothesis_id="H2",
                typology="shell_company",
                statement="V023 is a shell.",
                objects=["V023"],
                origin="screen",
            ),
        ],
        findings=[
            Finding(
                hypothesis_id="H2",
                verdict="Unsubstantiated",
                rationale=[Sentence(text="Only one test ran.", evidence_ids=["E3"])],
                counter_evidence=["E3"],
                data_gaps=["vendor V023 has no address"],
            ),
            Finding(
                hypothesis_id="H1",
                verdict="Substantiated",
                model_verdict="Unsubstantiated",
                verdict_by="gate_override_of_model",
                supporting_evidence=["E1", "E2"],
                confidence=0.85,
                amount_at_issue_inr=Decimal("993500"),
                rationale=[
                    Sentence(text="Employment ended 2024-11-30.", evidence_ids=["E1"]),
                    Sentence(text="Both invoices sit under the limit.", evidence_ids=["E2"]),
                ],
            ),
        ],
        data_quality=["3 spellings of Orbital Fasteners merged."],
        assumptions={"threshold_band_pct": "5", "career_gap_days": "180"},
        exhibits=[e1, e2, e3],
        metrics={"wall_seconds": 41.2, "crustdata_calls": 9, "credits_used": 12, "model_calls": 4},
        merkle_root="ab" * 32,
        verify_command="python verify.py out/career_overlap/log.jsonl",
    )


@pytest.fixture
def store() -> PayloadStore:
    return PayloadStore()


def test_clean_case_passes_check(store: PayloadStore) -> None:
    case = make_case(store)
    assert check_citations(case, store) == []
    assert citation_validity(case, store) == 1.0


def test_render_writes_all_files(tmp_path: Path, store: PayloadStore) -> None:
    case = make_case(store)
    md_path = render(case, tmp_path, evidence_index=store)
    for name in ("case_file.md", "exhibits.md", "evidence.json", "findings.json", "root.txt"):
        assert (tmp_path / name).is_file(), name
    md = md_path.read_text(encoding="utf-8")
    sections = [
        "## 1. Background and predication",
        "## 2. Executive summary",
        "## 3. Scope",
        "## 4. Approach",
        "## 5. Findings",
        "## 6. Data quality notes",
        "## 7. Assumptions and thresholds",
        "## 8. Metrics",
        "## 9. Exhibits",
    ]
    positions = [md.index(s) for s in sections]
    assert positions == sorted(positions)
    # Substantiated first, anchors link to in-document exhibit headings
    assert md.index("H1: conflict_of_interest") < md.index("H2: shell_company")
    assert "[[E1]](#e1) [[E2]](#e2)" in md
    assert "### E1\n" in md
    assert "INR 9,93,500" in md
    assert "overriding the model" in md
    assert "`threshold_band_pct`" in md
    assert "employment[2]: Orbital Fasteners, Analyst, 2021-06-01 to 2024-11-30" in md
    assert "crustdata:person:987@2026-10-01T00:00:00Z" in md
    findings = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))
    h1 = next(f for f in findings if f["hypothesis_id"] == "H1")
    assert (h1["typology"], h1["subjects"], h1["objects"]) == ("conflict_of_interest", ["S004"], ["V017"])


def test_uncited_sentence_blocks_render(tmp_path: Path, store: PayloadStore) -> None:
    case = make_case(store)
    case.findings[1].rationale.append(Sentence(text="He is clearly guilty."))
    errors = check_citations(case, store)
    assert errors == ["findings[H1].rationale[2]: uncited sentence: 'He is clearly guilty.'"]
    with pytest.raises(CitationError) as exc:
        render(case, tmp_path / "out", evidence_index=store)
    assert exc.value.code == 2
    assert not (tmp_path / "out" / "case_file.md").exists()


def test_unknown_evidence_id(store: PayloadStore) -> None:
    case = make_case(store)
    case.executive_summary.append(Sentence(text="See [E9].", evidence_ids=["E99"]))
    errors = check_citations(case, store)
    assert any("cites E99" in e for e in errors)
    assert any("cites E9," in e for e in errors)


def test_quote_must_be_literal_in_payload(store: PayloadStore) -> None:
    case = make_case(store)
    case.exhibits[1].quote = "L00042 2025-03-14 Orbital Fasteners 9,98,000 approver S004"
    errors = check_citations(case, store)
    assert errors == [
        "E2: quote not found literally in its source payload: "
        "'L00042 2025-03-14 Orbital Fasteners 9,98,000 approver S004'"
    ]
    assert citation_validity(case, store) == pytest.approx(1 / 4)


def test_tampered_payload_fails_hash(store: PayloadStore) -> None:
    case = make_case(store)
    sha = case.exhibits[0].sha256
    tampered = {k: v for k, v in store.items()}
    tampered[sha] = PERSON.replace("2024-11-30", "2020-11-30").encode()
    errors = check_citations(case, tampered)
    assert len(errors) == 1 and errors[0].startswith("E1: payload sha256")


def test_missing_payload(store: PayloadStore) -> None:
    case = make_case(store)
    assert any("no stored payload" in e for e in check_citations(case, {}))
    assert check_citations(case, {}, require_payloads=False) == []


def test_crustdata_needs_updated_at(store: PayloadStore) -> None:
    case = make_case(store)
    case.exhibits[2].source = Source(kind="crustdata_company", refs=["crustdata:company:555"])
    errors = check_citations(case, store)
    assert "E3: Crustdata source without updated_at (source.as_of)" in errors
    assert any("is not crustdata:<kind>:<id>@<updated_at>" in e for e in errors)


def test_payload_store_roundtrip(tmp_path: Path, store: PayloadStore) -> None:
    case = make_case(store)
    store.dump(tmp_path / "payloads")
    reloaded = PayloadStore.load(tmp_path / "payloads")
    assert check_citations(case, reloaded) == []


# --- redaction ---------------------------------------------------------------------------


def test_initials() -> None:
    assert initials("Ravi Kumar") == "R.K."
    assert initials("anita  m. desai") == "A.M.D."


def test_redactor_variants() -> None:
    r = Redactor(["Ravi Kumar", "Rahul Kapoor", "Anita Desai"])
    assert r("RAVI KUMAR and ravi-kumar-1234 and Kumar, Ravi") == "R.K. and R.K.-1234 and R.K."
    assert r("Rahul Kapoor") == "R.K.2"
    assert r("Orbital Fasteners S004 crustdata:person:987") == "Orbital Fasteners S004 crustdata:person:987"
    assert r.mapping == {"R.K.": "Ravi Kumar", "R.K.2": "Rahul Kapoor", "A.D.": "Anita Desai"}


def test_render_redacted(tmp_path: Path, store: PayloadStore) -> None:
    case = make_case(store)
    out = tmp_path / "demo"
    render(case, out, redact=True, evidence_index=store, people=["Ravi Kumar"])
    for name in ("case_file.md", "exhibits.md", "evidence.json", "findings.json"):
        text = (out / name).read_text(encoding="utf-8")
        assert "Ravi" not in text and "ravi-kumar" not in text, name
    md = (out / "case_file.md").read_text(encoding="utf-8")
    assert "R.K." in md and "S004" in md and "Orbital Fasteners" in md
    assert "crustdata:person:987@2026-10-01T00:00:00Z" in md
    mapping = json.loads((tmp_path / ".redaction" / "demo.json").read_text(encoding="utf-8"))
    assert mapping == {"R.K.": "Ravi Kumar"}
    assert not (out / "redaction_map.json").exists()


# --- formatting and the log/case-file root link ------------------------------------------


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("498000"), "INR 4,98,000"),
        (Decimal("12345678.5"), "INR 1,23,45,678.50"),
        (Decimal("999"), "INR 999"),
        (Decimal("-1000"), "INR -1,000"),
        (None, "not quantified"),
    ],
)
def test_inr(amount: Decimal | None, text: str) -> None:
    assert inr(amount) == text


def test_case_file_root_checked_by_verifier(tmp_path: Path, store: PayloadStore) -> None:
    """Pipeline order from a1: root at render time, render, post, seal."""
    log = AuditLog(tmp_path / "log.jsonl")
    for i in range(5):
        with log.step("rule_test", {"name": f"T0{i}"}):
            pass
    case = make_case(store)
    case.metrics["log_records"] = log.seq
    case.merkle_root = log.merkle_root()
    rid = log.pre("render", {"name": "case_file"})
    render(case, tmp_path, evidence_index=store)
    log.post(rid, {"status": "ok"})
    log.seal()
    log.close()
    assert verify(tmp_path / "log.jsonl").ok

    md = tmp_path / "case_file.md"
    md.write_text(md.read_text(encoding="utf-8").replace(case.merkle_root, "cd" * 32), encoding="utf-8")
    rep = verify(tmp_path / "log.jsonl")
    assert [f.check for f in rep.failures] == ["root"]
    assert "case_file.md Merkle root" in rep.failures[0].message
