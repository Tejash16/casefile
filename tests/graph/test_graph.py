"""Graph build, path evidence (T16) and centrality: positive and negative examples."""

from __future__ import annotations

from datetime import date

from rules_factory import Book, Employment, PersonBrief, company, person, resolved, staff, vendor

from casefile.graph import build, centrality, path_evidence
from casefile.report.check import check_evidence
from casefile.rules.config import STRENGTH

S003_ADDR = "Flat 7, Shivneri Apartments, Karve Road, Kothrud, Pune 411038"
V023_ADDR = "Flat No. 7, Shivneri Apts, Karve Rd, Kothrud, Pune - 411038"
WEWORK = "WeWork, Embassy 247, LBS Marg, Vikhroli West, Mumbai 400083"


def _rows(*pairs):
    b = Book()
    for i, (sid, vid) in enumerate(pairs):
        b.add(vid, date(2025, 1, 1 + i), 1000 + i, approver_id=sid)
    return b.rows


def test_shared_phone_path_supports():
    v = vendor("V023", address=V023_ADDR, phone="+91 98220 41736")
    s = staff("S003", "Anil Deshpande", address=S003_ADDR, phone="9822041736")
    G = build(_rows(("S003", "V023")), [v], [s])
    e = path_evidence(G, "S003", "V023")
    assert e is not None and e.direction == "supports"
    assert e.strength == STRENGTH["t16_identifier"]  # phone beats the address link
    assert e.quote.startswith("staff:S003 -[phone:") and e.quote.endswith("vendor:V023")
    assert e.source.kind == "graph" and e.source.refs[0] == "staff:S003"
    e = e.model_copy(update={"evidence_id": "E1", "log_record_id": "r1"})
    assert check_evidence(e, {}, require_payloads=True) == []


def test_fuzzy_equal_addresses_share_one_node():
    v = vendor("V023", address=V023_ADDR)
    s = staff("S003", address=S003_ADDR)
    G = build([], [v], [s])
    addr = [n for n in G if n.startswith("addr:")]
    assert len(addr) == 1
    assert G.has_edge("vendor:V023", addr[0]) and G.has_edge("staff:S003", addr[0])


def test_career_path_through_crustdata_ids():
    cd = company("C17", "Persistent Systems")
    v = vendor("V017", resolution=resolved(), crustdata=cd)
    emp = Employment(
        company_name="Persistent Systems",
        crustdata_company_id="C17",
        start_date=date(2021, 6, 1),
        end_date=date(2024, 11, 30),
        title="Analyst",
    )
    p = person("rj", "Rohan Joshi", [emp])
    s = staff("S004", "Rohan Joshi", resolution=resolved(), crustdata=p)
    G = build(_rows(("S004", "V017")), [v], [s])
    e = path_evidence(G, "S004", "V017")
    assert e is not None and e.strength == STRENGTH["t16_career"]
    assert "employment[0]: Persistent Systems, Analyst, 2021-06-01 to 2024-11-30" in e.quote
    assert e.source.refs == ["staff:S004", "cdperson:rj", "cdco:C17", "vendor:V017"]


def test_founder_profile_path():
    p = PersonBrief(name="Anil Deshpande", linkedin_url="https://linkedin.com/in/anil-d")
    v = vendor("V023", resolution=resolved(), crustdata=company("C23", "Brindora", founders=[p]))
    s = staff("S003", "Anil Deshpande", linkedin_url="https://www.linkedin.com/in/anil-d/")
    e = path_evidence(build([], [v], [s]), "S003", "V023")
    assert e is not None and e.strength == STRENGTH["t16_career"]


def test_coworking_only_path_is_neutral():
    v = vendor("V200", address=WEWORK)
    s = staff("S010", address=WEWORK)
    e = path_evidence(build([], [v], [s]), "S010", "V200")
    assert e is not None and e.direction == "neutral"
    assert e.strength == STRENGTH["t16_coworking"]


def test_approval_alone_is_not_a_path():
    v = vendor("V001", address="Bombay House, 24 Homi Mody Street, Fort, Mumbai")
    s = staff("S001", address=S003_ADDR, phone="9850012001")
    G = build(_rows(("S001", "V001")), [v], [s])
    assert G.edges["staff:S001", "vendor:V001"]["weight"] == 1
    assert path_evidence(G, "S001", "V001") is None
    assert path_evidence(G, "S404", "V001") is None  # unknown staff


def test_centrality_ranks_the_connected_vendor_first():
    vs = [vendor(f"V{i}") for i in range(4)]
    rows = _rows(("S1", "V0"), ("S1", "V1"), ("S2", "V0"), ("S2", "V2"), ("S3", "V0"))
    c = centrality(build(rows, vs, [staff("S1"), staff("S2"), staff("S3")]))
    assert set(c) == {"V0", "V1", "V2", "V3"}
    assert max(c, key=c.get) == "V0" and c["V3"] == 0.0


def test_centrality_without_links_is_zero():
    c = centrality(build([], [vendor("V1"), vendor("V2")], []))
    assert c == {"V1": 0.0, "V2": 0.0}


def test_old_job_is_a_weak_link_not_a_career_path():
    """Review finding: T16 ignored dates; a 2008-2012 job scored 0.75 against 2025 payments."""
    cd = company("C17", "Persistent Systems")
    v = vendor("V017", resolution=resolved(), crustdata=cd)
    emp = Employment(
        company_name="Persistent Systems",
        crustdata_company_id="C17",
        start_date=date(2008, 1, 1),
        end_date=date(2012, 1, 1),
    )
    s = staff("S1", resolution=resolved(), crustdata=person("p1", "Someone", [emp]))
    e = path_evidence(build(_rows(("S1", "V017")), [v], [s]), "S1", "V017")
    assert e is not None and e.direction == "neutral"
    assert e.strength == STRENGTH["t16_stale_career"]
    assert "not near the payments" in e.quote and "employment far from the payments" in e.summary
