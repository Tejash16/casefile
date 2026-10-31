"""CrustdataClient: limiter, cache, offline, retries, batching, mapping. No network."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from casefile.audit.log import AuditLog
from casefile.crustdata.client import (
    BATCH,
    COMPANY_FIELDS,
    CreditsExhausted,
    CrustdataClient,
    OfflineMiss,
    PermissionDenied,
    RateLimited,
    RateLimiter,
    cache_key,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "crustdata"
DATA = Path(__file__).resolve().parent / "data"


def _identify_row(query: str, *matches: tuple[int, str, float, str | None, str]) -> dict:
    return {
        "matched_on": query,
        "match_type": "name",
        "matches": [
            {
                "confidence_score": score,
                "company_data": {
                    "crustdata_company_id": cid,
                    "basic_info": {
                        "name": name,
                        "crustdata_company_id": cid,
                        "primary_domain": dom,
                        "employee_count_range": ecr,
                    },
                },
            }
            for cid, name, score, dom, ecr in matches
        ],
    }


class Fake:
    """httpx handler: answers by path, records every request."""

    def __init__(self, routes: dict[str, list[httpx.Response] | httpx.Response | object]):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes[request.url.path]
        if isinstance(route, list):
            return route.pop(0)
        if callable(route):
            return route(request)
        return route  # type: ignore[return-value]

    def bodies(self, path: str) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == path]


def ok(body: object, credits: str = "0", rid: str = "req-1") -> httpx.Response:
    return httpx.Response(200, json=body, headers={"x-credits-used": credits, "x-request-id": rid})


def make(tmp_path: Path, fake: Fake, offline: bool = False, audit: AuditLog | None = None):
    sleeps: list[float] = []
    now = [0.0]

    def sleep(s: float) -> None:  # fake time: sleeping advances the clock
        sleeps.append(s)
        now[0] += s

    client = CrustdataClient(
        api_key="test-key",
        cache_dir=tmp_path / "cache",
        offline=offline,
        audit=audit,
        transport=httpx.MockTransport(fake),
        limiter=RateLimiter(clock=lambda: now[0], sleep=sleep),
        sleep=sleep,
    )
    return client, sleeps


def records(log: AuditLog) -> list[dict]:
    log.close()
    return [json.loads(x) for x in log.path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------- limiter


def test_limiter_blocks_the_rpm_plus_first_call_until_the_window_frees() -> None:
    now = [0.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    lim = RateLimiter(limits={"/company/enrich": 15}, clock=lambda: now[0], sleep=sleep)
    for _ in range(15):
        assert lim.acquire("/company/enrich") == 0
    waited = lim.acquire("/company/enrich")
    assert 59.9 < waited < 60.1
    assert lim.acquire("/company/identify") == 0  # other endpoints have their own window


def test_limiter_never_exceeds_rpm_in_any_window() -> None:
    now = [0.0]

    def sleep(s: float) -> None:
        now[0] += s

    lim = RateLimiter(limits={"/p": 3}, clock=lambda: now[0], sleep=sleep)
    stamps = []
    for _ in range(10):
        lim.acquire("/p")
        stamps.append(now[0])
        now[0] += 1.0
    for i, t in enumerate(stamps):
        assert sum(1 for u in stamps[i:] if u - t < 60.0) <= 3


# ---------------------------------------------------------------- cache and offline


def test_headers_on_every_call(tmp_path: Path) -> None:
    fake = Fake({"/company/identify": ok([_identify_row("Acme")])})
    client, _ = make(tmp_path, fake)
    client.identify_companies(["Acme"])
    h = fake.requests[0].headers
    assert h["authorization"] == "Bearer test-key"
    assert h["x-api-version"] == "2025-11-01"
    assert h["content-type"] == "application/json"


def test_cache_miss_then_hit_and_audit_records(tmp_path: Path) -> None:
    fake = Fake(
        {
            "/company/identify": ok(
                [_identify_row("Acme", (7, "Acme", 1.0, "acme.com", "11-50"))], rid="r-7"
            )
        }
    )
    log = AuditLog(tmp_path / "log.jsonl")
    client, _ = make(tmp_path, fake, audit=log)
    a = client.identify_companies(["Acme"])
    b = client.identify_companies(["Acme"])
    assert len(fake.requests) == 1
    assert not a[0].cache_hit and b[0].cache_hit
    assert a[0].crustdata_company_id == b[0].crustdata_company_id == "7"
    body = {"names": ["Acme"], "exact_match": True}
    entry = json.loads(
        (tmp_path / "cache" / f"{cache_key('POST', '/company/identify', body)}.json").read_text()
    )
    assert entry["headers"]["x-request-id"] == "r-7"
    assert entry["request"]["body"] == body and entry["fetched_at"]
    recs = records(log)
    pres = [r for r in recs if r["record_phase"] == "pre_execution"]
    posts = [r for r in recs if r["record_phase"] == "post_execution"]
    assert [p["action_detail"]["cache_hit"] for p in pres] == [False, True]
    assert all(p["action_type"] == "tool_call" for p in pres)
    assert all(p["outcome"]["request_id"] == "r-7" and p["outcome"]["result_sha256"] for p in posts)
    assert client.record_id_for("r-7") == pres[1]["record_id"]


def test_offline_hit_never_touches_network(tmp_path: Path) -> None:
    fake = Fake({"/company/identify": ok([_identify_row("Acme")])})
    client, _ = make(tmp_path, fake)
    client.identify_companies(["Acme"])

    def boom(_: httpx.Request) -> httpx.Response:
        raise AssertionError("network used offline")

    offline, _ = make(tmp_path, Fake({"/company/identify": boom}), offline=True)
    assert offline.identify_companies(["Acme"])[0].cache_hit


def test_offline_miss_raises_and_logs_error(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "log.jsonl")
    client, _ = make(tmp_path, Fake({}), offline=True, audit=log)
    with pytest.raises(OfflineMiss):
        client.identify_companies(["Nobody"])
    post = records(log)[-1]
    assert post["outcome"]["status"] == "error" and "OfflineMiss" in post["outcome"]["error"]


def test_cache_hit_reports_zero_credits_spent(tmp_path: Path) -> None:
    fake = Fake({"/company/enrich": ok([], credits="2")})
    client, _ = make(tmp_path, fake)
    client.enrich_companies(["5"])
    client.enrich_companies(["5"])
    assert client.credits_spent == 2.0 and client.cache_hits == 1


# ---------------------------------------------------------------- retries and errors


def test_429_honours_reset_header_then_succeeds(tmp_path: Path) -> None:
    fake = Fake(
        {
            "/company/identify": [
                httpx.Response(429, json={"error": {}}, headers={"x-ratelimit-reset": "7"}),
                httpx.Response(429, json={"error": {}}, headers={"retry-after": "3"}),
                ok([_identify_row("Acme")]),
            ]
        }
    )
    client, sleeps = make(tmp_path, fake)
    assert client.identify_companies(["Acme"])[0].query == "Acme"
    assert len(fake.requests) == 3
    retry_sleeps = [s for s in sleeps if s >= 3]
    assert 7 <= retry_sleeps[0] <= 8 and 3 <= retry_sleeps[1] <= 4


def test_429_gives_up_after_five_tries(tmp_path: Path) -> None:
    fake = Fake(
        {"/company/identify": lambda r: httpx.Response(429, headers={"x-ratelimit-reset": "1"})}
    )
    client, _ = make(tmp_path, fake)
    with pytest.raises(RateLimited):
        client.identify_companies(["Acme"])
    assert len(fake.requests) == 5


def test_5xx_is_retried(tmp_path: Path) -> None:
    fake = Fake({"/company/identify": [httpx.Response(503), ok([_identify_row("Acme")])]})
    client, _ = make(tmp_path, fake)
    client.identify_companies(["Acme"])
    assert len(fake.requests) == 2


def test_402_raises_credits_exhausted_without_retry(tmp_path: Path) -> None:
    fake = Fake(
        {
            "/company/enrich": lambda r: httpx.Response(
                402, json={"error": {"type": "insufficient_credits"}}
            )
        }
    )
    client, _ = make(tmp_path, fake)
    with pytest.raises(CreditsExhausted):
        client.enrich_companies(["1"])
    assert len(fake.requests) == 1


def test_403_is_typed_cached_and_replayed_offline(tmp_path: Path) -> None:
    deny = httpx.Response(
        403, json={"error": {"type": "permission_error"}}, headers={"x-request-id": "d"}
    )
    client, _ = make(tmp_path, Fake({"/person/identify": deny}))
    with pytest.raises(PermissionDenied):
        client.identify_persons(["a@b.example"])
    offline, _ = make(tmp_path, Fake({}), offline=True)
    with pytest.raises(PermissionDenied):
        offline.identify_persons(["a@b.example"])


# ---------------------------------------------------------------- batching and mapping


def test_26_names_go_out_in_two_calls_in_order(tmp_path: Path) -> None:
    def echo(req: httpx.Request) -> httpx.Response:
        names = json.loads(req.content)["names"]
        return ok([_identify_row(n, (i, n, 1.0, None, None)) for i, n in enumerate(names)])

    fake = Fake({"/company/identify": echo})
    client, _ = make(tmp_path, fake)
    names = [f"Vendor {i}" for i in range(BATCH + 1)]
    out = client.identify_companies(names)
    sent = fake.bodies("/company/identify")
    assert [len(b["names"]) for b in sent] == [25, 1]
    assert [r.query for r in out] == names


def test_identify_leaves_id_empty_when_top_score_is_tied(tmp_path: Path) -> None:
    row = _identify_row(
        "Infosys",
        (2199, "Infosys", 1.0, "infosys.com", "10001+"),
        (99, "Infosys", 1.0, None, "2-10"),
    )
    client, _ = make(tmp_path, Fake({"/company/identify": ok([row])}))
    r = client.identify_companies(["Infosys"])[0]
    assert r.crustdata_company_id is None and len(r.candidates) == 2
    assert r.candidates[0]["primary_domain"] == "infosys.com"


def test_identify_by_domain_sends_domains_without_exact_flag(tmp_path: Path) -> None:
    fake = Fake(
        {"/company/identify": ok([_identify_row("acme.com", (7, "Acme", 1.0, "acme.com", None))])}
    )
    client, _ = make(tmp_path, fake)
    client.identify_companies(["acme.com"], by="domains")
    assert fake.bodies("/company/identify") == [{"domains": ["acme.com"]}]


def test_enrich_by_ids_only_with_explicit_fields_and_maps_recorded_body(tmp_path: Path) -> None:
    body = json.loads((FIXTURES / "company_enrich_tata_steel.json").read_text(encoding="utf-8"))
    body = body.get("body", body) if isinstance(body, dict) else body
    fake = Fake({"/company/enrich": ok(body, credits="2", rid="tata-1")})
    client, _ = make(tmp_path, fake)
    facts = client.enrich_companies(["5042", "5042"])
    sent = fake.bodies("/company/enrich")
    assert sent == [{"crustdata_company_ids": [5042], "fields": COMPANY_FIELDS}]
    f = facts[0]
    assert f.crustdata_company_id == "5042" and f.name
    assert f.source_request_id == "tata-1" and f.updated_at
    assert f.citation == f"crustdata:company:5042@{f.updated_at}"


def test_enrich_maps_slim_people_and_falls_back_to_fetch_time(tmp_path: Path) -> None:
    cd = {
        "crustdata_company_id": 42,
        "updated_at": None,
        "metadata": {"updated_at": None},
        "basic_info": {"name": "Orbital", "primary_domain": "orbital.in", "year_founded": 2024},
        "headcount": {"total": 3, "timeseries": [{"date": "2025-01-01", "employee_count": 2}]},
        "locations": {"city": "Pune", "country": "IND", "headquarters": "Kothrud, Pune"},
        "funding": {"total_investment_usd": None},
        "people": {
            "founders": [
                {
                    "crustdata_person_id": 1,
                    "basic_profile": {"name": "Anil Deshpande", "current_title": "Owner"},
                    "social_handles": {
                        "professional_network_identifier": {
                            "profile_url": "https://www.linkedin.com/in/ad"
                        }
                    },
                    "experience": {
                        "employment_details": {
                            "current": [
                                {
                                    "employer_company_id": ["42"],
                                    "employee_title": "Founder",
                                    "employee_start_date": "2024-12-01T00:00:00.000Z",
                                    "employee_end_date": None,
                                }
                            ]
                        }
                    },
                }
            ],
            "decision_makers": [{"basic_profile": {"name": "X Y", "current_title": "CFO"}}],
        },
    }
    fake = Fake(
        {
            "/company/enrich": ok(
                [{"matched_on": "42", "matches": [{"confidence_score": 1.0, "company_data": cd}]}]
            )
        }
    )
    client, _ = make(tmp_path, fake)
    f = client.enrich_companies(["42"])[0]
    assert f.headcount_total == 3 and f.headcount_timeseries[0][1] == 2
    assert f.street_address == "Kothrud, Pune"
    assert f.founders[0].title == "Founder" and str(f.founders[0].start_date) == "2024-12-01"
    assert f.decision_makers[0].title == "CFO"
    assert f.updated_at.endswith("Z")  # fetch time, because the record carries none


def test_person_search_body_and_candidates(tmp_path: Path) -> None:
    profile = json.loads((DATA / "person_search.json").read_text(encoding="utf-8"))
    fake = Fake({"/person/search": ok(profile, credits="0.23")})
    client, _ = make(tmp_path, fake)
    out = client.search_person("Bhupesh Naik", employer="Infosys")
    body = fake.bodies("/person/search")[0]
    assert body["mode"] == "exact" and body["limit"] == 5
    conds = body["filters"]["conditions"]
    assert conds[0] == {"field": "basic_profile.name", "type": "=", "value": "Bhupesh Naik"}
    assert conds[1]["field"] == "experience.employment_details.company_name"
    assert out[0].profile_url == "https://www.linkedin.com/in/bhupeshnaik"
    assert out[0].crustdata_person_id == "2029845" and out[0].current_company == "Infosys"


def test_person_enrich_maps_employment_and_skips_not_found(tmp_path: Path) -> None:
    body = json.loads((DATA / "person_enrich.json").read_text(encoding="utf-8"))
    fake = Fake({"/person/enrich": ok(body, credits="1", rid="p-1")})
    client, _ = make(tmp_path, fake)
    urls = [
        "https://www.linkedin.com/in/bhupeshnaik",
        "https://www.linkedin.com/in/zz-nobody-xq-9981",
    ]
    status = client.enrich_persons_status(urls)
    assert status[urls[1]] is None
    p = status[urls[0]]
    assert p is not None and p.updated_at == "2026-10-28T16:13:35Z" and p.source_request_id == "p-1"
    assert p.citation.startswith("crustdata:person:2029845@")
    past = [e for e in p.employment if not e.is_current]
    assert past and all(e.company_name for e in past)
    assert any(e.crustdata_company_id == "2199" and e.end_date for e in past)
    assert fake.bodies("/person/enrich")[0]["professional_network_profile_urls"] == urls
