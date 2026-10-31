"""Vendor and staff resolution decision tables, against a fake client. No network, no model."""

from __future__ import annotations

from typing import Any

import pytest

from casefile.crustdata.client import CrustdataError, PermissionDenied
from casefile.resolve import resolve_staff, resolve_vendors, vendor_people
from casefile.resolve._common import domain_of, domain_stem_matches, plausible, strip_suffixes
from casefile.resolve.staff import display_name, infer_company
from casefile.schemas import (
    CompanyFacts,
    IdentifyResult,
    MatchDecision,
    MatchVerdict,
    PersonBrief,
    PersonCandidate,
    PersonFacts,
    StaffRecord,
    VendorRecord,
)


def cand(cid: str, name: str, score: float, dom: str | None = None, ecr: str | None = None):
    return {
        "crustdata_company_id": cid,
        "name": name,
        "confidence_score": score,
        "primary_domain": dom,
        "all_domains": [dom] if dom else [],
        "employee_count_range": ecr,
    }


class FakeClient:
    def __init__(
        self,
        by_domain: dict[str, list[dict]] | None = None,
        by_name: dict[tuple[str, bool], list[dict]] | None = None,
        search: dict[tuple[str, str | None], list[PersonCandidate]] | None = None,
        profiles: dict[str, PersonFacts | None] | None = None,
        identify_enabled: bool = False,
        fail: set[str] | None = None,
    ) -> None:
        self.by_domain, self.by_name = by_domain or {}, by_name or {}
        self.search, self.profiles = search or {}, profiles or {}
        self.identify_enabled, self.fail = identify_enabled, fail or set()
        self.scope: dict[str, Any] = {}
        self.calls, self.credits_spent = 0, 0.0
        self.log: list[tuple[str, Any]] = []

    def _go(self, name: str, arg: Any) -> None:
        self.log.append((name, arg))
        self.calls += 1
        if name in self.fail:
            raise CrustdataError(f"{name} down")

    def describe_scope(self, dataset: str) -> dict:
        self.scope[f"/{dataset}/x"] = {}
        return {}

    def enabled(self, path: str) -> bool:
        return self.identify_enabled

    def record_id_for(self, request_id: str | None) -> str | None:
        return f"rec-{request_id}" if request_id else None

    def identify_companies(self, names, exact=True, by="names"):
        self._go(f"identify_{by}", (list(names), exact))
        out = []
        for q in names:
            cands = (
                self.by_domain.get(q, []) if by == "domains" else self.by_name.get((q, exact), [])
            )
            out.append(IdentifyResult(query=q, candidates=cands, request_id=f"{by}-{exact}"))
        return out

    def enrich_companies(self, ids, fields=None):
        self._go("enrich", list(ids))
        return [
            CompanyFacts(
                crustdata_company_id=i, name=f"Co {i}", updated_at="t", source_request_id="e"
            )
            for i in ids
        ]

    def search_person(self, name, employer=None, location=None, limit=5):
        self._go("search", (name, employer))
        return self.search.get((name, employer), [])

    def enrich_persons_status(self, urls):
        self._go("enrich_persons", list(urls))
        return {u: self.profiles.get(u) for u in urls}

    def identify_persons(self, emails):
        self._go("identify_persons", list(emails))
        raise PermissionDenied("403")


def vendor(vid: str, name: str, website: str | None = None, email: str | None = None):
    return VendorRecord(
        vendor_id=vid, name_raw=name, name_norm=name.lower(), website=website, email=email
    )


def judge_says(decision: str, index: int | None = None):
    calls: list[tuple] = []

    def judge(query, candidates, kind):
        calls.append((query, candidates, kind))
        return MatchDecision(
            decision=MatchVerdict(decision), index=index, reason="r", log_record_id="J1"
        )

    judge.calls = calls  # type: ignore[attr-defined]
    return judge


# ---------------------------------------------------------------- helpers


def test_name_and_domain_helpers() -> None:
    assert strip_suffixes("Tata Steel Limited") == "Tata Steel"
    assert strip_suffixes("Brindora Engineering Traders Pvt Ltd") == "Brindora Engineering Traders"
    assert domain_of("https://www.TataSteel.com/en") == "tatasteel.com"
    assert domain_of("brindora.traders@gmail.example") is None  # free mail says nothing
    assert domain_of("ap@orbital-fasteners.in") == "orbital-fasteners.in"
    assert domain_stem_matches("Pune Metrology", "punemetrology.in")
    assert not domain_stem_matches("Infosys", "metaveosconsultancy.com")
    assert plausible("Zentravik Industrial Supplies", "ZENTRAVIK INDUSTRIAL")
    assert not plausible("Zentravik Industrial Supplies", "Zamil Industrial")


# ---------------------------------------------------------------- vendors


def test_domain_is_a_hard_match_and_enrich_is_one_batch() -> None:
    c = FakeClient(
        by_domain={
            "tatasteel.com": [cand("5042", "Tata Steel", 1.0, "tatasteel.com")],
            "bharatforge.com": [cand("646", "Bharat Forge Ltd", 1.0, "bharatforge.com")],
        }
    )
    out = resolve_vendors(
        [
            vendor("V1", "Tata Steel Limited", "tatasteel.com"),
            vendor("V2", "Bharat Forge", "https://bharatforge.com"),
        ],
        c,
    )
    assert [v.resolution.status for v in out] == ["resolved", "resolved"]
    assert (
        out[0].resolution.method == "domain"
        and out[0].resolution.log_record_id == "rec-domains-True"
    )
    assert out[0].crustdata is not None and out[0].crustdata.crustdata_company_id == "5042"
    assert [x for x in c.log if x[0] == "enrich"] == [("enrich", ["5042", "646"])]
    assert not [x for x in c.log if x[0] == "identify_names"]


def test_tied_names_never_take_matches_zero_and_domain_stem_breaks_the_tie() -> None:
    infosys = [
        cand("24602744", "Infosys", 1.0, "metaveosconsultancy.com", "201-500"),
        cand("2199", "Infosys", 1.0, "infosys.com", "10001+"),
        cand("24602742", "Infosys", 1.0, None, "2-10"),
    ]
    c = FakeClient(by_name={("Infosys", True): infosys})
    v = resolve_vendors([vendor("V1", "Infosys Ltd")], c)[0]
    assert v.resolution.status == "resolved" and v.resolution.method == "identify_exact"
    assert v.crustdata is not None and v.crustdata.crustdata_company_id == "2199"
    assert v.resolution.candidates_considered == 3


@pytest.mark.parametrize(
    ("decision", "index", "status", "method"),
    [
        ("yes", 1, "resolved", "llm_judge"),
        ("no", None, "unresolved", None),
        ("unsure", None, "ambiguous", None),
    ],
)
def test_unbreakable_tie_goes_to_the_judge(decision, index, status, method) -> None:
    tie = [cand("1", "Acme Tools", 1.0, None), cand("2", "Acme Tools", 1.0, None)]
    c = FakeClient(by_name={("Acme Tools", True): tie})
    judge = judge_says(decision, index)
    v = resolve_vendors([vendor("V1", "Acme Tools Pvt Ltd")], c, judge=judge)[0]
    assert v.resolution.status == status and v.resolution.method == method
    assert len(judge.calls) == 1 and judge.calls[0][2] == "company"
    assert judge.calls[0][0]["name"] == "Acme Tools Pvt Ltd"  # the judge sees the vendor row
    if status == "resolved":
        assert v.crustdata is not None and v.crustdata.crustdata_company_id == "2"
        assert v.resolution.log_record_id == "J1"


def test_tie_without_judge_is_ambiguous_not_resolved() -> None:
    tie = [cand("1", "Acme Tools", 1.0), cand("2", "Acme Tools", 0.95)]
    c = FakeClient(by_name={("Acme Tools", True): tie})
    v = resolve_vendors([vendor("V1", "Acme Tools")], c)[0]
    assert v.resolution.status == "ambiguous" and v.crustdata is None
    assert not [x for x in c.log if x[0] == "enrich"]


def test_middle_band_single_leader_needs_the_judge() -> None:
    c = FakeClient(
        by_name={("Pune Metrology", False): [cand("7", "PUNE METROLOGY", 0.8, "punemetrology.in")]}
    )
    judge = judge_says("yes", 0)
    v = resolve_vendors([vendor("V6", "Pune Metrology")], c, judge=judge)[0]
    assert v.resolution.status == "resolved" and v.resolution.method == "llm_judge"
    assert v.resolution.confidence == 0.8


def test_exact_then_fuzzy_and_fuzzy_single_leader_above_accept() -> None:
    c = FakeClient(by_name={("Bharat Forge", False): [cand("646", "Bharat Forge", 0.9)]})
    v = resolve_vendors([vendor("V2", "Bharat Forge Ltd")], c)[0]
    assert v.resolution.method == "identify_fuzzy"
    exacts = [a[1] for n, a in c.log if n == "identify_names"]
    assert exacts == [True, False]


def test_fictional_vendor_ends_unresolved_without_exception() -> None:
    junk = [
        cand(str(i), n, 0.6)
        for i, n in enumerate(["Zamil Industrial", "FPT Industrial", "iA Financial"])
    ]
    c = FakeClient(by_name={("Zentravik Industrial Supplies", False): junk})
    judge = judge_says("yes", 0)
    v = resolve_vendors([vendor("V8", "Zentravik Industrial Supplies Pvt Ltd")], c, judge=judge)[0]
    assert v.resolution.status == "unresolved" and v.crustdata is None
    assert v.resolution.candidates_considered == 3
    assert judge.calls == []  # nothing plausible, nothing to judge


def test_low_score_is_unresolved_without_judge_call() -> None:
    c = FakeClient(by_name={("Acme", False): [cand("1", "Acme", 0.4)]})
    judge = judge_says("yes", 0)
    v = resolve_vendors([vendor("V1", "Acme")], c, judge=judge)[0]
    assert v.resolution.status == "unresolved" and judge.calls == []


def test_spellings_of_one_vendor_share_one_identify_query() -> None:
    c = FakeClient(by_name={("Orbital Fasteners", True): [cand("9", "Orbital Fasteners", 1.0)]})
    vs = [
        vendor("V1", "Orbital Fasteners Pvt Ltd"),
        vendor("V2", "ORBITAL FASTENERS"),
        vendor("V3", "Orbital Fastners"),
    ]
    out = resolve_vendors(vs, c)
    names_sent = [a[0] for n, a in c.log if n == "identify_names"]
    assert names_sent == [["Orbital Fasteners"]]
    assert {v.crustdata.crustdata_company_id for v in out if v.crustdata} == {"9"}


def test_judge_failure_is_ambiguous() -> None:
    def broken(*_: Any) -> MatchDecision:
        raise RuntimeError("model down")

    tie = [cand("1", "Acme", 1.0), cand("2", "Acme", 1.0)]
    v = resolve_vendors(
        [vendor("V1", "Acme")], FakeClient(by_name={("Acme", True): tie}), judge=broken
    )[0]
    assert v.resolution.status == "ambiguous"


def test_crustdata_outage_marks_not_attempted_and_does_not_raise() -> None:
    c = FakeClient(fail={"identify_domains", "identify_names"})
    out = resolve_vendors([vendor("V1", "Tata Steel", "tatasteel.com"), vendor("V2", "Acme")], c)
    assert [v.resolution.status for v in out] == ["not_attempted", "not_attempted"]


# ---------------------------------------------------------------- staff


def staff(sid: str, name: str, email: str | None = None, url: str | None = None) -> StaffRecord:
    return StaffRecord(
        staff_id=sid, name_raw=name, name_norm=name.lower(), email=email, linkedin_url=url
    )


def person(pid: str, url: str) -> PersonFacts:
    return PersonFacts(
        crustdata_person_id=pid,
        name="P",
        profile_url=url,
        updated_at="2026-10-28T16:13:35Z",
        source_request_id=f"pe-{pid}",
    )


def pc(name: str, url: str, rid: str = "s1") -> PersonCandidate:
    return PersonCandidate(name=name, profile_url=url, request_id=rid)


def test_staff_helpers() -> None:
    assert display_name(staff("S3", "Mr. Anil Deshpande")) == "Anil Deshpande"
    assert display_name(staff("S9", "rahul verma")) == "Rahul Verma"
    roster = [
        staff("S1", "A", "a@halvexa.example"),
        staff("S2", "B", "b@halvexa.example"),
        staff("S3", "C", "c@gmail.com"),
    ]
    assert infer_company(roster) == "Halvexa"


def test_linkedin_url_resolves_directly_and_skips_search() -> None:
    url = "https://www.linkedin.com/in/b"
    c = FakeClient(profiles={url: person("77", url)})
    s = resolve_staff([staff("S5", "Rahul Verma", "r@halvexa.example", url)], c)[0]
    assert s.resolution.status == "resolved" and s.resolution.method == "linkedin_url"
    assert s.crustdata is not None and s.crustdata.crustdata_person_id == "77"
    assert s.resolution.log_record_id == "rec-pe-77" and s.resolution.candidates_considered == 1
    assert not [x for x in c.log if x[0] in ("search", "identify_persons")]


def test_linkedin_url_not_found_is_unresolved() -> None:
    c = FakeClient(profiles={})
    s = resolve_staff([staff("S5", "X Y", url="https://www.linkedin.com/in/nobody")], c)[0]
    assert s.resolution.status == "unresolved" and s.crustdata is None


def test_email_identify_is_skipped_when_scope_says_disabled() -> None:
    c = FakeClient(identify_enabled=False)
    resolve_staff([staff("S1", "Asha Rao", "asha@halvexa.example")], c)
    assert not [x for x in c.log if x[0] == "identify_persons"]


def test_email_identify_403_falls_back_to_search() -> None:
    c = FakeClient(identify_enabled=True)
    s = resolve_staff([staff("S1", "Asha Rao", "asha@halvexa.example")], c)[0]
    assert [x[0] for x in c.log][:2] == ["identify_persons", "search"]
    assert s.resolution.status == "unresolved"


def test_single_hit_at_the_audited_company_is_accepted_and_enriched() -> None:
    url = "https://www.linkedin.com/in/rohan"
    c = FakeClient(
        search={("Rohan Joshi", "Halvexa"): [pc("Rohan Joshi", url, "s-r")]},
        profiles={url: person("12", url)},
    )
    s = resolve_staff([staff("S4", "Rohan Joshi", "rohan@halvexa.example")], c)[0]
    assert s.resolution.status == "resolved" and s.resolution.method == "person_search"
    assert s.resolution.log_record_id == "rec-s-r"
    assert s.crustdata is not None and s.crustdata.crustdata_person_id == "12"


def test_name_only_namesakes_are_never_auto_accepted() -> None:
    namesake = [pc("Rahul Verma", "https://www.linkedin.com/in/rv-cummins")]
    c = FakeClient(search={("Rahul Verma", None): namesake})
    s = resolve_staff([staff("S5", "Rahul Verma", "rahul@halvexa.example")], c)[0]
    assert s.resolution.status == "ambiguous" and s.crustdata is None
    assert s.resolution.candidates_considered == 1
    assert not [x for x in c.log if x[0] == "enrich_persons"]


def test_judge_rejects_namesakes_and_counts_them() -> None:
    namesakes = [pc("Rahul Verma", f"https://www.linkedin.com/in/rv{i}") for i in range(5)]
    c = FakeClient(search={("Rahul Verma", None): namesakes})
    judge = judge_says("no")
    s = resolve_staff([staff("S5", "Rahul Verma", "rahul@halvexa.example")], c, judge=judge)[0]
    assert s.resolution.status == "unresolved" and s.resolution.candidates_considered == 5
    assert judge.calls[0][2] == "person" and judge.calls[0][0]["employer"] == "Halvexa"


def test_several_hits_at_company_go_to_judge_and_yes_is_enriched() -> None:
    urls = ["https://www.linkedin.com/in/p1", "https://www.linkedin.com/in/p2"]
    c = FakeClient(
        search={("Priya Nair", "Halvexa"): [pc("Priya Nair", u) for u in urls]},
        profiles={urls[1]: person("2", urls[1])},
    )
    s = resolve_staff(
        [staff("S8", "Priya Nair", "p@halvexa.example")], c, judge=judge_says("yes", 1)
    )[0]
    assert s.resolution.method == "llm_judge" and s.crustdata is not None
    assert s.crustdata.profile_url == urls[1]


def test_no_profile_at_all_is_unresolved() -> None:
    s = resolve_staff([staff("S2", "Vikram Shah", "v@halvexa.example")], FakeClient())[0]
    assert s.resolution.status == "unresolved" and s.resolution.candidates_considered == 0


def test_search_outage_is_not_attempted() -> None:
    s = resolve_staff(
        [staff("S2", "Vikram Shah", "v@halvexa.example")], FakeClient(fail={"search"})
    )[0]
    assert s.resolution.status == "not_attempted"


# ---------------------------------------------------------------- founders


def test_vendor_people_founders_first_deduplicated() -> None:
    facts = CompanyFacts(
        crustdata_company_id="9",
        name="Orbital",
        updated_at="t",
        source_request_id="r",
        founders=[PersonBrief(name="Anil Deshpande", title="Founder")],
        decision_makers=[PersonBrief(name="anil  deshpande"), PersonBrief(name="X Y", title="CFO")],
    )
    v = vendor("V1", "Orbital").model_copy(update={"crustdata": facts})
    assert [p.name for p in vendor_people(v)] == ["Anil Deshpande", "X Y"]
    assert [p.name for p in vendor_people(v, include_decision_makers=False)] == ["Anil Deshpande"]
    assert vendor_people(vendor("V2", "Ghost")) == []
