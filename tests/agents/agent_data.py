"""Hand-built contract objects for agent tests."""

from __future__ import annotations

from decimal import Decimal

from casefile.schemas import (
    Direction,
    EvidenceObject,
    Hypothesis,
    Resolution,
    ResolutionStatus,
    Source,
    SourceKind,
    StaffRecord,
    Tip,
    Typology,
    VendorRecord,
)

TIP = Tip(
    text="Ravi in procurement keeps pushing Orbital Fasteners. I heard he used to work there.",
    received_at="2026-10-01T09:00:00Z",
    sha256="0" * 64,
)

VENDORS = [
    VendorRecord(
        vendor_id="V017", name_raw="Orbital Fasteners Pvt Ltd", name_norm="orbital fasteners"
    ),
    VendorRecord(vendor_id="V002", name_raw="Tata Steel Ltd", name_norm="tata steel"),
]
STAFF = [
    StaffRecord(
        staff_id="S004",
        name_raw="Ravi Kumar",
        name_norm="ravi kumar",
        title="Procurement Manager",
        approval_limit=Decimal("500000"),
    ),
    StaffRecord(staff_id="S001", name_raw="Asha Rao", name_norm="asha rao", title="CFO"),
]
LEDGER_STATS = {
    "rows": 1200,
    "period": ["2024-04-01", "2026-03-31"],
    "per_vendor": {
        "V017": {"spend": 4860000, "invoice_count": 14},
        "V002": {"spend": 92000000, "invoice_count": 210},
    },
}

H1 = Hypothesis(
    hypothesis_id="H1",
    typology=Typology.conflict_of_interest,
    statement="Approver S004 steered INR 48.6 lakh to V017, a company S004 worked for.",
    subjects=["S004"],
    objects=["V017"],
    tests_to_run=["T05", "T15", "T16"],
    prior_score=0.7,
    rationale="PROPOSER-REASONING-MARKER",
)


def ev(
    eid: str,
    test: str,
    direction: Direction,
    strength: float,
    hyp: list[str] | None = None,
    kind: SourceKind = SourceKind.ledger_rows,
    refs: list[str] | None = None,
) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=eid,
        test_id=test,
        hypothesis_ids=["H1"] if hyp is None else hyp,
        subject_ids=["S004"],
        object_ids=["V017"],
        direction=direction,
        strength=strength,
        summary=f"Summary of {eid} from {test}.",
        quote=f"quote for {eid}",
        source=Source(kind=kind, refs=refs or [f"L000{eid[1:]}"]),
        sha256=f"{eid}sha".ljust(64, "0"),
        log_record_id="rec-" + eid,
    )


RESOLVED = Resolution(status=ResolutionStatus.resolved)
RESOLUTIONS = {"S004": RESOLVED, "V017": RESOLVED, "V002": RESOLVED, "S001": RESOLVED}
