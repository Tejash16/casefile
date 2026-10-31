"""T15 on b1's canned person enrich, and the full rule set on the fixture CSVs (b1's planted
facts in fixtures/README.md). The CSV test skips until casefile.ingest's loaders land."""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path

import pytest
from rules_factory import Book, company, ctx_for, of, resolved, staff, vendor

from casefile.rules import TESTS, run_tests
from casefile.rules.config import STRENGTH
from casefile.rules.tests_ import t15_career_overlap
from casefile.schemas import Employment, PersonFacts

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _day(s: str | None) -> date | None:
    return datetime.fromisoformat(s).date() if s else None


def canned_people() -> dict[str, PersonFacts]:
    """Profile URL -> PersonFacts from fixtures/crustdata/person_enrich_team.json, mapping only
    the fields T15 reads (a stand-in until b2's response parser is on main)."""
    try:
        from casefile.crustdata.parse import person_facts  # type: ignore[import-not-found]
    except ImportError:
        person_facts = None
    raw = json.loads((FIXTURES / "crustdata" / "person_enrich_team.json").read_text("utf-8"))
    out: dict[str, PersonFacts] = {}
    for rec in raw:
        m = rec["matches"][0]
        if person_facts is not None:
            out[rec["matched_on"]] = person_facts(m)
            continue
        p = m["person_data"]
        details = p["experience"]["employment_details"]
        emp = [
            Employment(
                company_name=e["name"],
                crustdata_company_id=str(e["crustdata_company_id"])
                if e.get("crustdata_company_id")
                else None,
                company_domain=e.get("company_website_domain"),
                title=e.get("title"),
                start_date=_day(e.get("start_date")),
                end_date=_day(e.get("end_date")),
                is_current=kind == "current",
            )
            for kind in ("current", "past")
            for e in details.get(kind, [])
        ]
        out[rec["matched_on"]] = PersonFacts(
            crustdata_person_id=str(p["crustdata_person_id"]),
            name=p["basic_profile"]["name"],
            profile_url=rec["matched_on"],
            employment=emp,
            updated_at="2026-10-31",
            source_request_id="fixture",
        )
    return out


def _team():
    people = canned_people()
    tejash = next(p for p in people.values() if p.name == "Tejash Chauhan")
    kedar = next(p for p in people.values() if p.name == "Kedar Sharma")
    s004 = staff("S004", "Tejash Chauhan", resolution=resolved(1.0), crustdata=tejash)
    s005 = staff("S005", "Kedar Sharma", resolution=resolved(1.0), crustdata=kedar)
    v017 = vendor(
        "V017", name_raw="DocRack", resolution=resolved(), crustdata=company("71095782", "DocRack")
    )
    v031 = vendor(
        "V031", name_raw="HCLTech", resolution=resolved(), crustdata=company("1910", "HCLTech")
    )
    b = Book()
    for d in ("2025-06-12", "2025-08-20", "2025-10-15", "2025-12-10", "2026-02-02", "2026-03-19"):
        b.add("V017", date.fromisoformat(d), 250000, approver_id="S004")
    b.add("V031", date(2025, 7, 1), 1200000, approver_id="S001")
    return ctx_for(b, [v017, v031], [s004, s005, staff("S001", "Meera Kulkarni")])


def test_t15_canned_profile_supports_docrack_and_clears_false_lead():
    evs = t15_career_overlap.run(_team())
    sup = of(evs, "T15", "supports", "V017", "S004")
    assert [e.strength for e in sup] == [STRENGTH["t15_overlap"]]
    assert "DocRack, Co-Founder, 2026-03-01 to present" in sup[0].quote
    assert sup[0].source.refs[0] == "crustdata:person:177265563@2026-10-31"
    # false lead: tip names S005 at V031; Crustdata shows no HCLTech employment
    ref = of(evs, "T15", "refutes", "V031", "S005")
    assert [e.strength for e in ref] == [STRENGTH["t15_refute"]]
    # noise: S005 co-founded V017 but approved none of its invoices
    noise = of(evs, "T15", "supports", "V017", "S005")
    assert [e.strength for e in noise] == [STRENGTH["t15_non_approver"]]


def _load_fixture():
    ingest = pytest.importorskip("casefile.ingest")
    if not all(hasattr(ingest, f) for f in ("load_ledger", "load_vendors", "load_staff")):
        pytest.skip("casefile.ingest loaders not on main yet")
    rows, _ = ingest.load_ledger(FIXTURES / "ledger.csv")
    vendors, _ = ingest.load_vendors(FIXTURES / "vendors.csv")
    staff_list, _ = ingest.load_staff(FIXTURES / "staff.csv")
    rows = ingest.link_ledger(rows, vendors, staff_list)
    return rows, vendors, staff_list


def test_fixture_planted_facts_and_speed():
    rows, vendors, staff_list = _load_fixture()
    from casefile.rules.context import build_context

    t0 = time.perf_counter()
    evs = run_tests(sorted(TESTS), build_context(rows, vendors, staff_list))
    assert time.perf_counter() - t0 < 2.0
    supported = {(e.test_id, o) for e in evs if e.direction == "supports" for o in e.object_ids}
    for tid in ("T01", "T02", "T03", "T05", "T06", "T07", "T09", "T11"):
        assert (tid, "V023") in supported, f"{tid} missed the V023 shell"
    assert ("T04", "V003") in supported  # SFL/24-25/0457 paid twice
    t01 = of(evs, "T01", "supports", "V023", "S003")
    assert t01 and "phone" in t01[0].quote
