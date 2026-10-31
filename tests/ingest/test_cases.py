"""Every planted case in cases/ loads with zero exceptions, links every row, and plants what
its case.json expects (see cases/README.md)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from casefile.ingest import link_ledger, load_ledger, load_staff, load_tip, load_vendors
from casefile.schemas import CaseSpec

CASES = Path(__file__).resolve().parents[2] / "cases"
NAMES = sorted(p.name for p in CASES.iterdir() if (p / "case.json").exists())


def _load(name: str):
    d = CASES / name
    spec = CaseSpec.model_validate_json((d / "case.json").read_text(encoding="utf-8"))
    rows, ln = load_ledger(d / spec.inputs.ledger)
    vendors, vn = load_vendors(d / spec.inputs.vendors)
    staff, sn = load_staff(d / spec.inputs.staff)
    rows = link_ledger(rows, vendors, staff)
    tip = load_tip(d / spec.inputs.tip)
    return spec, rows, vendors, staff, tip, ln + vn + sn


def test_six_cases_present():
    assert set(NAMES) >= {
        "career_overlap",
        "shell_vendor",
        "false_lead",
        "duplicate_billing",
        "clean_controls",
        "shared_office_honest",
    }


@pytest.mark.parametrize("name", NAMES)
def test_case_loads_and_links(name):
    spec, rows, vendors, staff, tip, notes = _load(name)
    assert spec.name == name
    assert rows and all(r.vendor_id and r.approver_id for r in rows)
    assert all(r.quality_flags for r in rows[:10]) or any(r.quality_flags for r in rows)
    assert any("blank row" in n for n in notes) and any("repeated header" in n for n in notes)
    assert 80 <= len(tip.text.split()) <= 150
    ids = {v.vendor_id for v in vendors} | {s.staff_id for s in staff}
    for e in spec.expected:
        assert set(e.subjects) | set(e.objects) <= ids
    assert set(spec.must_clear) <= {v.vendor_id for v in vendors}
    assert not {o for e in spec.expected for o in e.objects if e.verdict == "Substantiated"} & set(
        spec.must_clear
    )


def test_career_overlap_plant():
    _, rows, vendors, staff, _, _ = _load("career_overlap")
    s4 = next(s for s in staff if s.staff_id == "S004")
    assert s4.linkedin_url and "tejash-chauhan" in s4.linkedin_url
    v17 = sorted((r for r in rows if r.vendor_id == "V017"), key=lambda r: r.date)
    assert len(v17) >= 6 and {r.approver_id for r in v17} == {"S004"}
    # billing starts when S004's DocRack role does (2026-03-01) and grows every month
    assert v17[0].date >= date(2026, 3, 1)
    assert all(a.amount < b.amount for a, b in zip(v17, v17[1:], strict=False))
    assert all(r.amount < s4.approval_limit * Decimal("0.95") for r in v17)
    # other vendors keep billing through the extended ledger
    assert max(r.date for r in rows if r.vendor_id != "V017") >= date(2026, 9, 1)
    v17 = next(v for v in vendors if v.vendor_id == "V017")
    assert v17.website is None  # docrack.ai resolves to another Crustdata record
    # ordinary vendor file: no thin-footprint, new-vendor or segregation-of-duties signal
    assert v17.address_type == "commercial" and v17.phone
    assert v17.created_by == "mdm.admin"
    assert min(r.date for r in rows if r.vendor_id == "V017") - v17.created_on > timedelta(days=90)


def test_shell_plant():
    _, rows, vendors, staff, _, _ = _load("shell_vendor")
    v = next(v for v in vendors if v.vendor_id == "V023")
    s = next(s for s in staff if s.staff_id == "S003")
    assert v.phone == s.phone and v.created_by == s.email.split("@")[0]
    inv = [r for r in rows if r.vendor_id == "V023"]
    assert len(inv) == 8 and all(r.amount % 1000 == 0 for r in inv)
    assert all(r.amount < s.approval_limit for r in inv)


def test_false_lead_plant():
    _, rows, _, staff, tip, _ = _load("false_lead")
    s5 = next(s for s in staff if s.staff_id == "S005")
    assert s5.linkedin_url and s5.approval_limit is None
    assert "Kedar Sharma" in tip.text and "HCLTech" in tip.text
    assert not any(r.approver_id == "S005" for r in rows)


def test_duplicate_plant():
    _, rows, vendors, *_ = _load("duplicate_billing")
    v3, v44 = (next(v for v in vendors if v.vendor_id == i) for i in ("V003", "V044"))
    assert v44.website == v3.website and v44.name_norm != v3.name_norm
    paid: dict[tuple, set[str]] = {}
    for r in rows:
        if r.vendor_id in ("V003", "V044"):
            paid.setdefault((r.invoice_no, r.amount), set()).add(r.vendor_id)
    assert [ids for ids in paid.values() if len(ids) == 2] == [{"V003", "V044"}]
    assert sum(1 for r in rows if r.vendor_id == "V044") == 1


def test_shared_office_plant():
    _, rows, vendors, *_ = _load("shared_office_honest")
    pair = [v for v in vendors if v.vendor_id in ("V041", "V042")]
    assert len(pair) == 2 and all(v.address_type == "coworking" for v in pair)
    assert pair[0].phone == pair[1].phone is None and pair[0].bank_account is None
