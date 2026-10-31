from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from casefile.schemas import (
    CaseSpec,
    EvidenceObject,
    LedgerRow,
    Sentence,
    Source,
    VendorRecord,
)


def test_ledger_row_parses_date_and_decimal():
    row = LedgerRow(
        row_id="L000001",
        date="2025-03-14",
        vendor_name_raw="Orbital Fasteners Pvt Ltd",
        vendor_key="orbital fasteners",
        amount="498000.00",
    )
    assert row.date == date(2025, 3, 14)
    assert row.amount == Decimal("498000.00")
    assert row.currency == "INR"


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        VendorRecord(vendor_id="V1", name_raw="x", name_norm="x", nonsense=1)


def test_vendor_defaults_to_not_attempted():
    v = VendorRecord(vendor_id="V1", name_raw="x", name_norm="x")
    assert v.resolution.status == "not_attempted"


def test_sentence_requires_citation_when_flagged():
    with pytest.raises(ValidationError):
        Sentence(text="uncited", require_citation=True)
    assert Sentence(text="ok", evidence_ids=["E1"], require_citation=True).evidence_ids == ["E1"]
    assert Sentence(text="free text").evidence_ids == []


def test_evidence_sha256_and_roundtrip():
    payload = b"L00042 2025-03-14 Orbital Fasteners 4,98,000 approver S004"
    ev = EvidenceObject(
        evidence_id="E1",
        test_id="T05",
        direction="supports",
        strength=0.8,
        summary="Invoice just under the approval limit.",
        quote=payload.decode(),
        source=Source(kind="ledger_rows", refs=["L00042"]),
        sha256=EvidenceObject.compute_sha256(payload),
        log_record_id="r1",
    )
    assert len(ev.sha256) == 64
    assert EvidenceObject.model_validate_json(ev.model_dump_json()) == ev


def test_case_spec_matches_contract_example():
    spec = CaseSpec.model_validate(
        {
            "name": "career_overlap_true_positive",
            "inputs": {
                "tip": "tip.txt",
                "ledger": "ledger.csv",
                "vendors": "vendors.csv",
                "staff": "staff.csv",
            },
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
            "notes": "S004 ...",
        }
    )
    assert spec.expected[1].verdict == "Unfounded"
