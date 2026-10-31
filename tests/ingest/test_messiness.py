"""One test per messiness type the loaders must survive and record."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from casefile.ingest import (
    link_ledger,
    load_ledger,
    load_staff,
    load_vendors,
    normalize_company_name,
    normalize_person_name,
)
from casefile.ingest.dates import parse_date
from casefile.ingest.load import classify_address
from casefile.ingest.money import parse_amount
from casefile.ingest.names import normalize_linkedin_url, normalize_phone, normalize_website
from casefile.schemas import AddressType

HEADER = "Txn Date,Supplier,Invoice No,Amount INR,Approved By\n"


def _write(tmp_path: Path, text: str, name: str = "ledger.csv", prefix: bytes = b"") -> Path:
    p = tmp_path / name
    p.write_bytes(prefix + text.encode("utf-8"))
    return p


# ---------------------------------------------------------------- file-level mess


def test_utf8_bom_is_stripped_and_noted(tmp_path):
    p = _write(tmp_path, HEADER + "2025-03-14,Acme,I1,100,X\n", prefix=b"\xef\xbb\xbf")
    rows, notes = load_ledger(p)
    assert len(rows) == 1 and rows[0].date == date(2025, 3, 14)
    assert any("byte-order mark" in n for n in notes)


def test_blank_row_dropped_and_noted(tmp_path):
    p = _write(tmp_path, HEADER + "2025-03-14,Acme,I1,100,X\n,,,,\n\n2025-03-15,Acme,I2,200,X\n")
    rows, notes = load_ledger(p)
    assert [r.invoice_no for r in rows] == ["I1", "I2"]
    assert any("blank row" in n for n in notes)


def test_repeated_header_dropped_and_noted(tmp_path):
    p = _write(
        tmp_path, HEADER + "2025-03-14,Acme,I1,100,X\n" + HEADER + "2025-03-15,Acme,I2,200,X\n"
    )
    rows, notes = load_ledger(p)
    assert [r.row_id for r in rows] == ["L000001", "L000002"]
    assert any("repeated header" in n for n in notes)


def test_trailing_space_column_name_and_synonyms(tmp_path):
    p = _write(tmp_path, "Date,Payee,Invoice,Amt ,Approver\n2025-03-14,Acme,I1,100,X\n")
    rows, notes = load_ledger(p)
    assert rows[0].amount == Decimal(100) and rows[0].vendor_name_raw == "Acme"
    assert rows[0].approver_name_raw == "X"
    assert any("surrounding whitespace" in n for n in notes)


def test_semicolon_delimiter_sniffed(tmp_path):
    p = _write(tmp_path, "date;vendor;amount\n2025-03-14;Acme;100\n2025-03-15;Acme;200\n")
    rows, notes = load_ledger(p)
    assert len(rows) == 2
    assert any("delimiter" in n for n in notes)


def test_cp1252_file_decoded(tmp_path):
    p = tmp_path / "ledger.csv"
    p.write_bytes("date,vendor,amount\n2025-03-14,Café Ltd,100\n".encode("cp1252"))
    rows, notes = load_ledger(p)
    assert rows[0].vendor_name_raw.startswith("Caf")
    assert any("not valid UTF-8" in n for n in notes)


def test_unparseable_row_dropped_not_silently(tmp_path):
    p = _write(tmp_path, HEADER + "not a date,Acme,I1,100,X\n2025-03-15,Acme,I2,abc,X\n")
    rows, notes = load_ledger(p)
    assert rows == []
    assert any("2 row(s) dropped" in n for n in notes)


# ---------------------------------------------------------------- dates


@pytest.mark.parametrize(
    ("raw", "expected", "flag"),
    [
        ("2025-03-14", date(2025, 3, 14), None),
        ("14/03/2025", date(2025, 3, 14), "date_coerced"),
        ("14-Mar-25", date(2025, 3, 14), "date_two_digit_year"),
        ("05/04/2025", date(2025, 4, 5), "date_ambiguous_dayfirst"),
        ("14 March 2025", date(2025, 3, 14), "date_coerced"),
    ],
)
def test_date_formats(raw, expected, flag):
    d, flags = parse_date(raw)
    assert d == expected
    assert (flag in flags) if flag else flags == []


def test_iso_date_raises_no_flag_and_garbage_is_flagged():
    assert parse_date("2025-03-14")[1] == []
    assert parse_date("yesterday-ish") == (None, ["date_unparseable"])


# ---------------------------------------------------------------- amounts


@pytest.mark.parametrize(
    ("raw", "expected", "flag"),
    [
        ("4,98,000", Decimal("498000"), "amount_lakh_format"),
        ("498000.00", Decimal("498000.00"), None),
        ("₹ 4,98,000.00", Decimal("498000.00"), "amount_currency_symbol"),
        ("Rs. 4,98,000", Decimal("498000"), "amount_currency_symbol"),
        ("INR 498,000", Decimal("498000"), "amount_thousands_format"),
        ("(12,500)", Decimal("-12500"), "amount_negative_parens"),
    ],
)
def test_amount_formats(raw, expected, flag):
    value, flags = parse_amount(raw)
    assert value == expected
    assert (flag in flags) if flag else flags == []


def test_lakh_and_rupee_ledger_rows_flagged(tmp_path):
    p = _write(
        tmp_path,
        HEADER + '2025-03-14,Acme,I1,"4,98,000",X\n2025-03-14,Acme,I2,"₹ 4,98,000.00",X\n',
    )
    rows, _ = load_ledger(p)
    assert all(r.amount == Decimal(498000) for r in rows)
    assert "amount_lakh_format" in rows[0].quality_flags
    assert "amount_currency_symbol" in rows[1].quality_flags


# ---------------------------------------------------------------- names and identifiers


@pytest.mark.parametrize(
    "raw",
    [
        "Orbital Fasteners Pvt Ltd",
        "ORBITAL FASTENERS PRIVATE LIMITED",
        "Orbital Fasteners Pvt. Ltd.",
        "Orbital Fasteners Limited",
        "orbital  fasteners llp",
    ],
)
def test_company_suffix_variants_share_a_key(raw):
    assert normalize_company_name(raw) == "orbital fasteners"


def test_company_name_ampersand_and_co():
    assert normalize_company_name("Larsen & Toubro Ltd") == "larsen and toubro"
    assert normalize_company_name("SKN & Co.") == "skn"


def test_person_name_honorifics_and_initials():
    assert normalize_person_name("Mr. Anil  Deshpande") == "anil deshpande"
    assert normalize_person_name("A. Deshpande") == "a deshpande"
    assert normalize_person_name("Smt. PRIYA NAIR") == "priya nair"


def test_phone_website_linkedin_normalised():
    assert normalize_phone("+91 98220 41736") == normalize_phone("9822041736") == "+919822041736"
    assert normalize_website("https://www.TataSteel.com/en/") == "tatasteel.com"
    url = "https://www.linkedin.com/in/someone-123?utm_source=share_via&utm_medium=member_ios"
    assert normalize_linkedin_url(url) == "https://www.linkedin.com/in/someone-123"
    assert normalize_linkedin_url("linkedin.com/in/someone-123/") == url.split("?")[0]


@pytest.mark.parametrize(
    ("address", "kind"),
    [
        ("Flat 7, Shivneri Apartments, Kothrud, Pune", AddressType.residential),
        ("WeWork Futura, Kharadi, Pune", AddressType.coworking),
        ("P.O. Box 1234, Mumbai", AddressType.po_box),
        ("Plot 12, MIDC Bhosari, Pune", AddressType.commercial),
        ("", AddressType.unknown),
    ],
)
def test_address_type_heuristic(address, kind):
    assert classify_address(address) == kind


# ---------------------------------------------------------------- linking


def test_spelling_variants_link_to_one_vendor_with_flags(tmp_path):
    ledger = _write(
        tmp_path,
        HEADER
        + "2025-03-14,Orbital Fasteners Pvt Ltd,I1,100,Anil Deshpande\n"
        + "2025-03-15,ORBITAL FASTENERS PRIVATE LIMITED,I2,100,A. Deshpande\n"
        + "2025-03-16,Orbital Fastners,I3,100,anil deshpande\n"
        + "2025-03-17,Unknown Traders,I4,100,Nobody Here\n",
    )
    vendors = _write(
        tmp_path, "Vendor Code,Vendor Name\nV001,Orbital Fasteners Pvt Ltd\n", "vendors.csv"
    )
    staff = _write(tmp_path, "Emp ID,Full Name\nS001,Mr. Anil Deshpande\n", "staff.csv")
    rows = link_ledger(load_ledger(ledger)[0], load_vendors(vendors)[0], load_staff(staff)[0])
    assert [r.vendor_id for r in rows] == ["V001", "V001", "V001", None]
    assert "vendor_spelling_variant" in rows[1].quality_flags
    assert "vendor_fuzzy_match" in rows[2].quality_flags
    assert "vendor_unlinked" in rows[3].quality_flags
    assert [r.approver_id for r in rows] == ["S001", "S001", "S001", None]
    assert "approver_initials_match" in rows[1].quality_flags
    assert "approver_unlinked" in rows[3].quality_flags
