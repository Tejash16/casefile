"""Loading fixtures/ yields exactly the planted rows, links and flags (see fixtures/README.md)."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from casefile.ingest import (
    ledger_stats,
    link_ledger,
    link_notes,
    load_ledger,
    load_staff,
    load_tip,
    load_vendors,
)
from casefile.schemas import AddressType

FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture(scope="module")
def loaded():
    rows, ledger_notes = load_ledger(FIX / "ledger.csv")
    vendors, vendor_notes = load_vendors(FIX / "vendors.csv")
    staff, staff_notes = load_staff(FIX / "staff.csv")
    rows = link_ledger(rows, vendors, staff)
    return rows, vendors, staff, ledger_notes + vendor_notes + staff_notes + link_notes(rows)


def test_counts(loaded):
    rows, vendors, staff, _ = loaded
    assert len(rows) == 62
    assert len(vendors) == 12
    assert len(staff) == 8
    assert [r.row_id for r in rows][:2] == ["L000001", "L000002"]


def test_every_row_links(loaded):
    rows, *_ = loaded
    assert all(r.vendor_id for r in rows)
    assert all(r.approver_id for r in rows)
    per_vendor = Counter(r.vendor_id for r in rows)
    assert per_vendor["V023"] == 8 and per_vendor["V017"] == 6 and per_vendor["V003"] == 7


def test_file_level_notes(loaded):
    *_, notes = loaded
    text = "\n".join(notes)
    for needle in (
        "byte-order mark",
        "CRLF",
        "'Amount INR ' had surrounding whitespace",
        "1 blank row(s) dropped",
        "1 repeated header row(s) dropped",
    ):
        assert needle in text, needle


def test_row_flags(loaded):
    rows, *_ = loaded
    flags = Counter(f for r in rows for f in r.quality_flags)
    for f in (
        "date_coerced",
        "date_two_digit_year",
        "amount_lakh_format",
        "amount_currency_symbol",
        "vendor_spelling_variant",
        "vendor_fuzzy_match",
        "approver_initials_match",
    ):
        assert flags[f] > 0, f
    # three date formats and three amount formats rotate, so a third of rows are ISO + plain
    assert sum(1 for r in rows if not {"date_coerced"} & set(r.quality_flags)) == 21
    assert "vendor_unlinked" not in flags and "approver_unlinked" not in flags


def test_planted_shell_v023(loaded):
    rows, vendors, staff, _ = loaded
    v23 = next(v for v in vendors if v.vendor_id == "V023")
    s3 = next(s for s in staff if s.staff_id == "S003")
    assert v23.phone == s3.phone
    assert v23.address_type == AddressType.residential
    assert v23.website is None and v23.created_by == "adeshpande"
    inv = sorted((r for r in rows if r.vendor_id == "V023"), key=lambda r: r.date)
    assert {r.approver_id for r in inv} == {"S003"}
    assert all(r.amount % 1000 == 0 and r.amount < s3.approval_limit for r in inv)
    assert len({r.vendor_name_raw for r in inv}) == 3


def test_planted_duplicate_v003(loaded):
    rows, *_ = loaded
    dup = [r for r in rows if r.invoice_no == "SFL/24-25/0457"]
    assert len(dup) == 2 and {r.amount for r in dup} == {Decimal("342180")}


def test_staff_linkedin_urls(loaded):
    _, _, staff, _ = loaded
    urls = {s.staff_id: s.linkedin_url for s in staff if s.linkedin_url}
    assert set(urls) == {"S004", "S005"}
    assert all("?" not in u and not u.endswith("/") for u in urls.values())


def test_tip_and_stats(loaded):
    rows, *_ = loaded
    tip = load_tip(FIX / "tip.txt")
    assert "Brindora" in tip.text and len(tip.sha256) == 64
    stats = ledger_stats(rows)
    assert stats["row_count"] == 62
    assert stats["approvers_per_vendor"]["V023"] == ["S003"]
    assert stats["round_amount_share_per_vendor"]["V023"] == 1.0
    assert stats["top_vendors_by_spend"][0]["vendor"] == "V001"
    assert stats["unlinked_vendor_rows"] == 0
