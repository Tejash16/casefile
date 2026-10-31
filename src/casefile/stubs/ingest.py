"""Stub for casefile.ingest (b1): two vendors, two staff, four ledger rows, tip read from disk."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from casefile.schemas import AddressType, LedgerRow, StaffRecord, Tip, VendorRecord

STUB_NOTE = "stub ingest: canned rows, input file not parsed"


def load_tip(path: str | Path) -> Tip:
    p = Path(path)
    raw = p.read_bytes() if p.exists() else b"Anonymous tip: S001 steers orders to V001."
    return Tip(
        text=raw.decode("utf-8", errors="replace").strip(),
        received_at=datetime.now(UTC).isoformat(timespec="seconds"),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def load_ledger(path: str | Path) -> tuple[list[LedgerRow], list[str]]:
    rows = [
        ("L000001", "2025-01-18", "Orbital Fasteners Pvt Ltd", "INV-101", "490000", "Asha Rao"),
        ("L000002", "2025-02-11", "Orbital Fasteners Pvt Ltd", "INV-102", "498000", "Asha Rao"),
        ("L000003", "2025-02-20", "Tata Steel Ltd", "TS-88812", "1234567", "Vikram Shah"),
        ("L000004", "2025-03-03", "Tata Steel Ltd", "TS-88913", "987654", "Vikram Shah"),
    ]
    return [
        LedgerRow(
            row_id=rid,
            date=d,
            vendor_name_raw=v,
            vendor_key=normalize_company_name(v),
            invoice_no=inv,
            amount=Decimal(amt),
            approver_name_raw=appr,
        )
        for rid, d, v, inv, amt, appr in rows
    ], [STUB_NOTE]


def load_vendors(path: str | Path) -> tuple[list[VendorRecord], list[str]]:
    return [
        VendorRecord(
            vendor_id="V001",
            name_raw="Orbital Fasteners Pvt Ltd",
            name_norm="orbital fasteners",
            address="Flat 4B, Shanti Apartments, Andheri East, Mumbai",
            address_type=AddressType.residential,
            city="Mumbai",
            created_on=date(2025, 1, 10),
        ),
        VendorRecord(
            vendor_id="V002",
            name_raw="Tata Steel Ltd",
            name_norm="tata steel",
            address="Bombay House, 24 Homi Mody Street, Mumbai",
            address_type=AddressType.commercial,
            city="Mumbai",
            website="tatasteel.com",
            created_on=date(2019, 4, 1),
        ),
    ], [STUB_NOTE]


def load_staff(path: str | Path) -> tuple[list[StaffRecord], list[str]]:
    return [
        StaffRecord(
            staff_id="S001",
            name_raw="Asha Rao",
            name_norm="asha rao",
            title="Procurement Manager",
            approval_limit=Decimal("500000"),
        ),
        StaffRecord(
            staff_id="S002",
            name_raw="Vikram Shah",
            name_norm="vikram shah",
            title="Finance Controller",
            approval_limit=Decimal("5000000"),
        ),
    ], [STUB_NOTE]


def normalize_company_name(raw: str) -> str:
    s = raw.lower().replace(".", " ")
    for suffix in (" private limited", " pvt ltd", " ltd", " llp", " inc", " llc"):
        s = s.removesuffix(suffix)
    return " ".join(s.split())


def normalize_person_name(raw: str) -> str:
    return " ".join(raw.lower().split())


def link_ledger(
    rows: list[LedgerRow], vendors: list[VendorRecord], staff: list[StaffRecord]
) -> list[LedgerRow]:
    by_vendor = {v.name_norm: v.vendor_id for v in vendors}
    by_staff = {s.name_norm: s.staff_id for s in staff}
    return [
        r.model_copy(
            update={
                "vendor_id": by_vendor.get(r.vendor_key),
                "approver_id": by_staff.get(normalize_person_name(r.approver_name_raw or "")),
            }
        )
        for r in rows
    ]


def ledger_stats(rows: list[LedgerRow]) -> dict[str, Any]:
    spend: dict[str, Decimal] = {}
    for r in rows:
        spend[r.vendor_id or r.vendor_key] = spend.get(r.vendor_id or r.vendor_key, 0) + r.amount
    return {
        "row_count": len(rows),
        "date_range": [str(min(r.date for r in rows)), str(max(r.date for r in rows))]
        if rows
        else [],
        "total_spend_inr": str(sum((r.amount for r in rows), Decimal(0))),
        "spend_per_vendor": {k: str(v) for k, v in spend.items()},
    }
