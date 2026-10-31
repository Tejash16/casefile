"""Master-data and Crustdata tests T01-T03, T13-T15, T17: positive and negative examples."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rules_factory import (
    Book,
    Employment,
    PersonBrief,
    company,
    ctx_for,
    of,
    person,
    resolved,
    staff,
    th,
    vendor,
)

from casefile.rules.config import STRENGTH
from casefile.rules.tests_ import (
    t01_identifier_match,
    t02_thin_footprint,
    t03_vendor_age,
    t13_existence,
    t14_lookalike,
    t15_career_overlap,
    t17_founders,
)
from casefile.schemas import Resolution

S003_ADDR = "Flat 7, Shivneri Apartments, Karve Road, Kothrud, Pune 411038"
V023_ADDR = "Flat No. 7, Shivneri Apts, Karve Rd, Kothrud, Pune - 411038"
WEWORK = "WeWork, Embassy 247, LBS Marg, Vikhroli West, Mumbai 400083"


def _book(*vids: str) -> Book:
    b = Book()
    for i, vid in enumerate(vids):
        b.add(vid, date(2025, 1, 18 + i), 490000, approver_id="S003")
    return b


# ---------------------------------------------------------------- T01


def test_t01_vendor_shares_staff_address_and_phone():
    v = vendor("V023", address=V023_ADDR, phone="+91 98220 41736")
    s = staff("S003", "Anil Deshpande", address=S003_ADDR, phone="9822041736")
    evs = t01_identifier_match.run(ctx_for(_book("V023"), [v], [s]))
    assert len(evs) == 1
    e = evs[0]
    assert e.direction == "supports" and e.subject_ids == ["S003"] and e.object_ids == ["V023"]
    assert e.strength == pytest.approx(STRENGTH["t01_phone"] + STRENGTH["t01_extra_match"])
    assert '"+91 98220 41736"' in e.quote and "address" in e.quote


def test_t01_shared_coworking_address_is_neutral():
    a = vendor("V200", address=WEWORK, phone="02240001111")
    b = vendor("V201", address="WeWork Embassy 247, L.B.S. Marg, Vikhroli (W), Mumbai 400083")
    evs = t01_identifier_match.run(ctx_for(_book("V200"), [a, b]))
    assert [(e.direction, e.strength) for e in evs] == [("neutral", STRENGTH["t01_coworking"])]
    assert evs[0].object_ids == ["V200", "V201"]


def test_t01_coworking_plus_same_bank_supports():
    a = vendor("V200", address=WEWORK, bank_account="50100234567891")
    b = vendor("V201", address=WEWORK, bank_account="0050100234567891")
    evs = t01_identifier_match.run(ctx_for(_book("V200"), [a, b]))
    assert [(e.direction, e.strength) for e in evs] == [("supports", STRENGTH["t01_bank"])]


def test_t01_unrelated_records_do_not_match():
    v = vendor(
        "V001", address="Bombay House, 24 Homi Mody Street, Fort, Mumbai", phone="2266658282"
    )
    s = staff("S003", address=S003_ADDR, phone="9822041736")
    city_only = staff("S004", address="Kothrud, Pune")  # subset of S003's tokens, too short
    assert t01_identifier_match.run(ctx_for(_book("V001"), [v], [s, city_only])) == []


# ---------------------------------------------------------------- T02


def test_t02_residential_with_personal_mail_supports():
    v = vendor("V023", address=V023_ADDR, phone="+91 98220 41736", email="x@gmail.example")
    evs = t02_thin_footprint.run(ctx_for(_book("V023"), [v]))
    assert len(evs) == 1 and evs[0].direction == "supports"
    assert evs[0].strength == pytest.approx(STRENGTH["t02_address"] + STRENGTH["t02_extra_signal"])
    assert "(residential)" in evs[0].quote


def test_t02_missing_contact_supports():
    evs = t02_thin_footprint.run(ctx_for(_book("V300"), [vendor("V300", address="MIDC Bhosari")]))
    assert [e.strength for e in evs] == [STRENGTH["t02_no_contact"]]


def test_t02_coworking_alone_is_not_a_signal():
    v = vendor("V200", address=WEWORK, website="acme.example", phone="02240001111")
    evs = t02_thin_footprint.run(ctx_for(_book("V200"), [v]))
    assert [(e.direction, e.strength) for e in evs] == [("neutral", STRENGTH["t02_coworking"])]


def test_t02_established_vendor_has_no_evidence():
    v = vendor("V001", address="Bombay House, Fort, Mumbai", website="tatasteel.com", tax_id="27X")
    assert t02_thin_footprint.run(ctx_for(_book("V001"), [v])) == []


# ---------------------------------------------------------------- T03


def test_t03_created_just_before_first_invoice():
    v = vendor("V023", created_on=date(2025, 1, 10))
    evs = t03_vendor_age.run(ctx_for(_book("V023"), [v]))
    assert [e.strength for e in evs] == [STRENGTH["t03_new"]]
    assert "created_on 2025-01-10" in evs[0].quote and "L000001" in evs[0].quote


def test_t03_founded_after_first_payment():
    cd = company("C9", "New Co", year_founded=2026)
    v = vendor("V024", created_on=date(2019, 1, 1), resolution=resolved(), crustdata=cd)
    evs = t03_vendor_age.run(ctx_for(_book("V024"), [v]))
    assert [e.strength for e in evs] == [STRENGTH["t03_paid_before_founded"]]
    assert cd.citation in evs[0].source.refs


def test_t03_old_vendor_has_no_evidence():
    v = vendor("V001", created_on=date(2019, 4, 1))
    assert t03_vendor_age.run(ctx_for(_book("V001"), [v])) == []


# ---------------------------------------------------------------- T13


def test_t13_unresolved_supports_with_data_gap():
    v = vendor("V008", resolution=Resolution(status="unresolved", candidates_considered=3))
    evs = t13_existence.run(ctx_for(_book("V008"), [v]))
    assert [(e.direction, e.strength) for e in evs] == [("supports", STRENGTH["t13_unresolved"])]
    assert "unresolved" in evs[0].summary


def test_t13_tiny_company_and_volume_support():
    head = th("shell_headcount_max")
    cd = company("C1", "Tiny", headcount_total=head)
    v = vendor("V023", resolution=resolved(), crustdata=cd)
    b = Book()
    per_head = th("volume_per_head_max_inr")
    b.add("V023", date(2025, 1, 18), per_head * head + 1)
    evs = t13_existence.run(ctx_for(b, [v]))
    assert sorted(e.strength for e in evs) == sorted([STRENGTH["t13_thin"], STRENGTH["t13_volume"]])
    assert all(e.source.refs == [cd.citation] and e.source.as_of == cd.updated_at for e in evs)


def test_t13_established_company_refutes():
    cd = company(
        "5042",
        "Tata Steel",
        headcount_total=th("established_headcount_min") * 100,
        website="https://www.tatasteel.com",
    )
    v = vendor("V001", resolution=resolved(), crustdata=cd)
    evs = t13_existence.run(ctx_for(_book("V001"), [v]))
    assert [(e.direction, e.strength) for e in evs] == [("refutes", STRENGTH["t13_refute"])]
    assert evs[0].quote.startswith("crustdata:company:5042@")


def test_t13_range_only_headcount_refutes():
    cd = company("77", "Mid Co", employee_count_range="51-200", primary_domain="mid.example")
    v = vendor("V002", resolution=resolved(), crustdata=cd)
    evs = t13_existence.run(ctx_for(_book("V002"), [v]))
    assert [e.direction for e in evs] == ["refutes"]


# ---------------------------------------------------------------- T14


def test_t14_lookalike_names_and_shared_tax_id():
    a = vendor("V100", name_raw="Orbital Fasteners Pvt Ltd", tax_id="27AAACO1234F1Z5")
    b = vendor("V101", name_raw="Orbital Fastners Private Limited")
    c = vendor("V102", name_raw="Kestrel Tools", tax_id="27aaaco1234f1z5")
    evs = t14_lookalike.run(ctx_for(_book("V100"), [a, b, c]))
    assert {(tuple(e.object_ids), e.strength) for e in evs} == {
        (("V100", "V101"), STRENGTH["t14_lookalike"]),
        (("V100", "V102"), STRENGTH["t14_same_tax_id"]),
    }


def test_t14_distinct_names_do_not_match():
    a, b = vendor("V001", name_raw="Tata Steel Ltd"), vendor("V002", name_raw="Tata Motors Ltd")
    assert t14_lookalike.run(ctx_for(_book("V001"), [a, b])) == []


# ---------------------------------------------------------------- T15


def _v017():
    cd = company("C17", "Persistent Systems", primary_domain="persistent.com")
    return vendor(
        "V017", name_raw="Persistent Systems Limited", resolution=resolved(), crustdata=cd
    )


def _s004(employment, confidence=0.95):
    p = person("rohan-j", "Rohan Joshi", employment)
    return staff("S004", "Rohan Joshi", resolution=resolved(confidence), crustdata=p)


def _v017_book() -> Book:
    b = Book()
    b.add("V017", date(2025, 3, 6), 218400, approver_id="S004")
    b.add("V017", date(2026, 1, 29), 468900, approver_id="S004")
    return b


def test_t15_recent_employment_at_vendor_supports():
    emp = Employment(
        company_name="Persistent Systems",
        crustdata_company_id="C17",
        title="Analyst",
        start_date=date(2021, 6, 1),
        end_date=date(2024, 11, 30),
    )
    evs = t15_career_overlap.run(ctx_for(_v017_book(), [_v017()], [_s004([emp])]))
    sup = of(evs, "T15", "supports", "V017", "S004")
    assert len(sup) == 1 and sup[0].strength == STRENGTH["t15_overlap"]
    assert (
        "employment[0]: Persistent Systems, Analyst, 2021-06-01 to 2024-11-30; "
        "first payment 2025-03-06" in sup[0].quote
    )
    assert sup[0].source.kind == "crustdata_person" and sup[0].source.as_of


def test_t15_match_by_domain_and_current_job():
    emp = Employment(company_name="PSL", company_domain="www.persistent.com", is_current=True)
    evs = t15_career_overlap.run(ctx_for(_v017_book(), [_v017()], [_s004([emp])]))
    assert of(evs, "T15", "supports")[0].strength == STRENGTH["t15_overlap"]


def test_t15_old_employment_is_neutral():
    emp = Employment(
        company_name="Persistent Systems Ltd",
        start_date=date(2010, 1, 1),
        end_date=date(2015, 1, 1),
    )
    evs = t15_career_overlap.run(ctx_for(_v017_book(), [_v017()], [_s004([emp])]))
    assert [(e.direction, e.strength) for e in evs] == [("neutral", STRENGTH["t15_old_employment"])]


def test_t15_resolved_person_elsewhere_refutes_even_without_approvals():
    """The tip-named staff member never approved the vendor; T15 still clears them."""
    b = _v017_book()
    b.add("V031", date(2025, 4, 1), 100000, approver_id="S001")
    v031 = vendor("V031", name_raw="Cummins India Ltd", resolution=resolved())
    p = person(
        "rahul-v", "Rahul Verma", [Employment(company_name="Infosys", end_date=date(2023, 1, 1))]
    )
    s005 = staff("S005", "Rahul Verma", resolution=resolved(), crustdata=p)
    evs = t15_career_overlap.run(ctx_for(b, [_v017(), v031], [s005]))
    ref = of(evs, "T15", "refutes", "V031", "S005")
    assert len(ref) == 1 and ref[0].strength == STRENGTH["t15_refute"]
    assert "[0] Infosys" in ref[0].quote


def test_t15_low_confidence_refutes_weakly_and_unresolved_is_a_gap():
    emp = Employment(company_name="Infosys")
    low = _s004([emp], confidence=th("identify_accept") - 0.1)
    evs = t15_career_overlap.run(ctx_for(_v017_book(), [_v017()], [low]))
    assert [e.strength for e in evs] == [STRENGTH["t15_refute_low_confidence"]]
    unresolved = staff("S004", "Rohan Joshi", resolution=Resolution(status="unresolved"))
    evs = t15_career_overlap.run(ctx_for(_v017_book(), [_v017()], [unresolved]))
    assert [(e.direction, e.strength, e.source.kind) for e in evs] == [
        ("neutral", 0.0, "staff_list")
    ]


# ---------------------------------------------------------------- T17


def _vendor_with(people):
    cd = company("C23", "Brindora", founders=people)
    return vendor("V023", resolution=resolved(), crustdata=cd)


def test_t17_founder_with_same_profile_supports():
    p = PersonBrief(
        name="Anil Deshpande", title="Founder", linkedin_url="https://linkedin.com/in/anil-d"
    )
    s = staff("S003", "Mr. Anil Deshpande", linkedin_url="https://www.linkedin.com/in/anil-d/")
    evs = t17_founders.run(ctx_for(_book("V023"), [_vendor_with([p])], [s]))
    assert [(e.direction, e.strength) for e in evs] == [("supports", STRENGTH["t17_same_profile"])]


def test_t17_namesake_is_neutral_and_name_only_is_weak():
    p = PersonBrief(name="Anil Deshpande", linkedin_url="https://linkedin.com/in/someone-else")
    other = staff("S003", "Anil Deshpande", linkedin_url="https://linkedin.com/in/anil-d")
    evs = t17_founders.run(ctx_for(_book("V023"), [_vendor_with([p])], [other]))
    assert [(e.direction, e.strength) for e in evs] == [("neutral", STRENGTH["t17_namesake"])]
    no_profile = staff("S003", "Anil Deshpande")
    evs = t17_founders.run(ctx_for(_book("V023"), [_vendor_with([p])], [no_profile]))
    assert [(e.direction, e.strength) for e in evs] == [("supports", STRENGTH["t17_name_only"])]


def test_t17_different_names_do_not_match():
    p = PersonBrief(name="Natarajan Chandrasekaran")
    evs = t17_founders.run(
        ctx_for(_book("V023"), [_vendor_with([p])], [staff("S003", "Anil Deshpande")])
    )
    assert evs == []


def test_limits_are_decimals_from_staff():
    assert isinstance(staff("S1", approval_limit=Decimal("500000")).approval_limit, Decimal)


def test_t01_neighbours_in_one_estate_do_not_match():
    """Same estate, different plot numbers: different premises, not a shared address."""
    a = vendor("V001", address="Plot 3, Sector 3, MIDC Bhosari, Pune 411026")
    b = vendor("V002", address="Plot 10, Sector 3, MIDC Bhosari, Pune 411026")
    c = vendor("V003", address="Plot 3, Sector 3, MIDC Bhosari, Pune")  # no PIN: still matches a
    evs = t01_identifier_match.run(ctx_for(_book("V001"), [a, b, c]))
    assert [e.object_ids for e in evs] == [["V001", "V003"]]


def test_t14_numbered_names_are_not_lookalikes():
    a, b = vendor("V001", name_raw="Plant 1 Services"), vendor("V002", name_raw="Plant 2 Services")
    assert t14_lookalike.run(ctx_for(_book("V001"), [a, b])) == []


def test_t15_joining_vendor_after_steering_payments_supports():
    """DocRack case: S004 approved V017 from 2025-06, co-founded it from 2026-03 (current)."""
    b = Book()
    b.add("V017", date(2025, 6, 12), 218400, approver_id="S004")
    b.add("V017", date(2025, 12, 1), 300000, approver_id="S004")
    emp = Employment(
        company_name="DocRack",
        crustdata_company_id="C17",
        title="Co-Founder",
        start_date=date(2026, 3, 1),
        is_current=True,
    )
    evs = t15_career_overlap.run(ctx_for(b, [_v017()], [_s004([emp])]))
    sup = of(evs, "T15", "supports", "V017", "S004")
    assert len(sup) == 1 and sup[0].strength == STRENGTH["t15_overlap"]
    assert "starting 90 days after the last payment" in sup[0].summary
    assert "DocRack, Co-Founder, 2026-03-01 to present" in sup[0].quote


def test_t15_non_approver_career_link_is_below_allegation_grade():
    b = _v017_book()
    emp = Employment(
        company_name="Persistent Systems",
        crustdata_company_id="C17",
        start_date=date(2025, 6, 1),
        is_current=True,
    )
    p = person("kedar", "Kedar Sharma", [emp])
    s005 = staff("S005", "Kedar Sharma", resolution=resolved(), crustdata=p)
    evs = t15_career_overlap.run(ctx_for(b, [_v017()], [_s004([]), s005]))
    sup = of(evs, "T15", "supports", "V017", "S005")
    assert [e.strength for e in sup] == [STRENGTH["t15_non_approver"]]
    assert "approved none of its invoices" in sup[0].summary


def test_t01_coworking_plus_shared_mailbox_supports():
    """Review finding: two vendors in one virtual office sharing a mailbox is the ring case."""
    regus = "Regus, Level 5, Tower B, Cyber City, Gurugram 122002"
    a = vendor("V1", address=regus, email="accounts.vk@gmail.com")
    b = vendor("V2", address=regus, email="Accounts.VK@gmail.com")
    evs = t01_identifier_match.run(ctx_for(_book("V1"), [a, b]))
    assert [(e.direction, e.strength) for e in evs] == [("supports", STRENGTH["t01_email"])]


def test_t15_past_job_without_end_date_is_not_open_ended():
    """Review finding: a 2008 job with no end date must not 'overlap' 2025 payments."""
    emp = Employment(
        company_name="Persistent Systems",
        crustdata_company_id="C17",
        start_date=date(2008, 1, 1),
        end_date=None,
        is_current=False,
    )
    evs = t15_career_overlap.run(ctx_for(_v017_book(), [_v017()], [_s004([emp])]))
    assert [(e.direction, e.strength) for e in evs] == [("neutral", STRENGTH["t15_old_employment"])]
