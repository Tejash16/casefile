"""Builders for small in-memory ledgers, vendor masters and staff lists (b3 tests)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from casefile.rules.config import THRESHOLDS
from casefile.schemas import (
    CompanyFacts,
    Employment,
    LedgerRow,
    PersonBrief,
    PersonFacts,
    Resolution,
    StaffRecord,
    VendorRecord,
)


def th(name: str) -> Any:
    return THRESHOLDS[name].value


class Book:
    """Accumulates ledger rows with sequential row ids."""

    def __init__(self) -> None:
        self.rows: list[LedgerRow] = []

    def add(
        self,
        vendor_id: str,
        on: date,
        amount: float | Decimal,
        invoice_no: str | None = None,
        approver_id: str | None = "S900",
        posted_at: datetime | None = None,
        created_by: str | None = None,
    ) -> LedgerRow:
        r = LedgerRow(
            row_id=f"L{len(self.rows) + 1:06d}",
            date=on,
            vendor_name_raw=f"Vendor {vendor_id}",
            vendor_key=f"vendor {vendor_id.lower()}",
            vendor_id=vendor_id,
            invoice_no=invoice_no,
            amount=Decimal(str(amount)),
            approver_id=approver_id,
            created_by=created_by,
            posted_at=posted_at,
        )
        self.rows.append(r)
        return r

    def background(
        self, vendors: int = 6, per_vendor: int = 6, start: date = date(2024, 4, 3)
    ) -> None:
        """Clean population: irregular amounts, spread invoice numbers, business hours."""
        for v in range(vendors):
            vid = f"V{800 + v}"
            for i in range(per_vendor):
                d = start + timedelta(days=37 * i + 5 * v)
                amt = 12_345.67 * (v + 1) + 1_013.11 * i
                self.add(
                    vid,
                    d,
                    round(amt, 2),
                    invoice_no=f"X{v}-{1000 + 97 * i + 13 * v}",
                    posted_at=_weekday(datetime(d.year, d.month, d.day, 11, 30)),
                )


def _weekday(t: datetime) -> datetime:
    while t.weekday() >= 5:
        t += timedelta(days=1)
    return t


def vendor(vid: str, **kw: Any) -> VendorRecord:
    base: dict[str, Any] = dict(
        vendor_id=vid, name_raw=f"Vendor {vid}", name_norm=f"vendor {vid.lower()}"
    )
    base.update(kw)
    return VendorRecord(**base)


def staff(sid: str, name: str = "Test Person", **kw: Any) -> StaffRecord:
    base: dict[str, Any] = dict(staff_id=sid, name_raw=name, name_norm=name.lower())
    base.update(kw)
    return StaffRecord(**base)


def resolved(confidence: float = 0.95) -> Resolution:
    return Resolution(status="resolved", method="identify_exact", confidence=confidence)


def company(cid: str, name: str, **kw: Any) -> CompanyFacts:
    base: dict[str, Any] = dict(
        crustdata_company_id=cid,
        name=name,
        updated_at="2026-10-01T00:00:00Z",
        source_request_id="req-test",
    )
    base.update(kw)
    return CompanyFacts(**base)


def person(pid: str, name: str, employment: list[Employment], **kw: Any) -> PersonFacts:
    base: dict[str, Any] = dict(
        crustdata_person_id=pid,
        name=name,
        profile_url=f"https://www.linkedin.com/in/{pid}",
        employment=employment,
        updated_at="2026-09-15T00:00:00Z",
        source_request_id="req-test",
    )
    base.update(kw)
    return PersonFacts(**base)


__all__ = [
    "ctx_for",
    "of",
    "Book",
    "Employment",
    "PersonBrief",
    "company",
    "person",
    "resolved",
    "staff",
    "th",
    "vendor",
]


def ctx_for(
    book: Book,
    vendors: list[VendorRecord] = (),
    staff_list: list[StaffRecord] = (),
    **kw: Any,
):
    """RuleContext over the book; any vendor id in the rows without a record gets a plain one."""
    from casefile.rules.context import build_context

    known = {v.vendor_id for v in vendors}
    extra = [vendor(vid) for vid in sorted({r.vendor_id for r in book.rows} - known)]
    return build_context(book.rows, [*vendors, *extra], list(staff_list), **kw)


def of(evs, test_id=None, direction=None, obj=None, subj=None):
    """Filter evidence by test, direction value, object id and subject id."""
    return [
        e
        for e in evs
        if (test_id is None or e.test_id == test_id)
        and (direction is None or e.direction == direction)
        and (obj is None or obj in e.object_ids)
        and (subj is None or subj in e.subject_ids)
    ]
