"""Crustdata HTTP client: rate limits, disk cache, retries, offline mode, audit records.

The only module that talks to api.crustdata.com. Every call goes through `_call`, which
(1) writes an audit `pre` record, (2) answers from `.cache/crustdata/<sha256>.json` if the
same {method, path, body} was fetched before, else waits for the per-endpoint limiter and
sends the request with retries on 429/5xx, (3) caches the raw body with `X-Credits-Used` and
`X-Request-Id`, and (4) writes the audit `post` record. `offline=True` never opens a socket:
a cache miss raises `OfflineMiss`.

Facts we verified against the live API on 2026-10-31 (see docs/research-brief.md section 3):
- Company Enrich returns `updated_at: null` even when the field is requested, so the citation
  timestamp of a company record falls back to `metadata.updated_at`, then to the time we fetched
  it (`fetched_at`, stored in the cache entry, so `--offline` reproduces the same citation).
- `POST /person/identify` is 403 on our plan; `preview: true` on Person Enrich is 400.
- Person Enrich carries a top-level `updated_at`; Person Search carries `metadata.updated_at`.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from tenacity import RetryCallState, Retrying, retry_if_exception_type, stop_after_attempt

from casefile.audit.log import canonical, hash_json, sha256_hex
from casefile.schemas import (
    CompanyFacts,
    Employment,
    IdentifyResult,
    PersonBrief,
    PersonCandidate,
    PersonFacts,
)

BASE_URL = "https://api.crustdata.com"
API_VERSION = "2025-11-01"
BATCH = 25
MAX_TRIES = 5

# Requests per minute, per endpoint (docs/research-brief.md section 3, confirmed by
# GET /account/endpoints for our key).
RATE_LIMITS: dict[str, int] = {
    "/company/identify": 30,
    "/company/enrich": 15,
    "/person/search": 30,
    "/person/enrich": 15,
    "/person/identify": 30,
    "/web/search/live": 10,
    "/web/enrich/live": 10,
    "/account/credits": 300,
    "/account/endpoints": 300,
}
DEFAULT_RPM = 10

# Enrich only what resolution and the rules read. The bare `people` group returns up to 300
# full decision-maker profiles (6 MB for a large company), so people are requested field by field.
_FOUNDER_JOB = (
    "employer_company_id",
    "employer_name",
    "employee_title",
    "employee_start_date",
    "employee_end_date",
)
COMPANY_FIELDS: list[str] = [
    "basic_info",
    "updated_at",
    "metadata",
    "headcount.total",
    "headcount.timeseries",
    "locations.city",
    "locations.state",
    "locations.country",
    "locations.headquarters",
    "locations.street_address",
    "funding.total_investment_usd",
    "people.founders.crustdata_person_id",
    "people.founders.basic_profile.name",
    "people.founders.basic_profile.current_title",
    "people.founders.social_handles.professional_network_identifier.profile_url",
    *(
        f"people.founders.experience.employment_details.{when}.{f}"
        for when in ("current", "past")
        for f in _FOUNDER_JOB
    ),
    "people.founders.updated_at",
    "people.decision_makers.crustdata_person_id",
    "people.decision_makers.basic_profile.name",
    "people.decision_makers.basic_profile.current_title",
    "people.decision_makers.social_handles.professional_network_identifier.profile_url",
]
PERSON_FIELDS: list[str] = [
    "crustdata_person_id",
    "basic_profile",
    "social_handles",
    "experience",
    "updated_at",
]
SEARCH_FIELDS: list[str] = [
    "crustdata_person_id",
    "basic_profile.name",
    "basic_profile.current_title",
    "basic_profile.location",
    "social_handles.professional_network_identifier.profile_url",
    "experience.employment_details.current.name",
    "experience.employment_details.past.name",
    "metadata",
]
SCOPE_PATHS: dict[str, list[str]] = {
    "company": ["/company/identify", "/company/enrich"],
    "person": ["/person/search", "/person/enrich", "/person/identify"],
}
_KEPT_HEADERS = ("x-credits-used", "x-request-id", "x-search-id")


# ---------------------------------------------------------------- errors


class CrustdataError(RuntimeError):
    """Any failed Crustdata call."""

    def __init__(self, message: str, status: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.request_id = request_id


class CreditsExhausted(CrustdataError):
    """402: the account has no credits left. Never retried."""


class PermissionDenied(CrustdataError):
    """403: endpoint or field not on our plan. Never retried."""


class OfflineMiss(CrustdataError):
    """offline=True and the request is not in the cache."""


class RateLimited(CrustdataError):
    """429 (retried until MAX_TRIES)."""

    def __init__(self, message: str, retry_after: float | None, **kw: Any):
        super().__init__(message, status=429, **kw)
        self.retry_after = retry_after


class TransientError(CrustdataError):
    """5xx or transport failure (retried)."""


# ---------------------------------------------------------------- limiter


class RateLimiter:
    """Sliding 60-second window per endpoint, the same rule the server applies.

    A token bucket with capacity = RPM lets 2*RPM through in the first minute (a full bucket plus
    refill), which the server's sliding window answers with 429; this never sends more than RPM
    requests in any 60-second span.
    """

    def __init__(
        self,
        limits: dict[str, int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        window: float = 60.0,
    ) -> None:
        self.limits = dict(RATE_LIMITS if limits is None else limits)
        self.clock, self.sleep, self.window = clock, sleep, window
        self._sent: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, path: str) -> float:
        """Block until `path` may be called; returns seconds waited."""
        rpm = self.limits.get(path, DEFAULT_RPM)
        waited = 0.0
        while True:
            with self._lock:
                now = self.clock()
                sent = self._sent.setdefault(path, deque())
                while sent and now - sent[0] >= self.window:
                    sent.popleft()
                if len(sent) < rpm:
                    sent.append(now)
                    return waited
                delay = self.window - (now - sent[0]) + 0.01
            self.sleep(delay)
            waited += delay

    def penalise(self, path: str, seconds: float) -> None:
        """After a 429, treat the window as full for `seconds` (server knows best)."""
        with self._lock:
            now = self.clock()
            rpm = self.limits.get(path, DEFAULT_RPM)
            start = now + seconds - self.window
            self._sent[path] = deque([start] * rpm)


# ---------------------------------------------------------------- response


@dataclass
class Response:
    method: str
    path: str
    body: Any
    status: int
    request_id: str | None
    credits_used: float
    fetched_at: str
    cache_hit: bool
    log_record_id: str | None
    result_sha256: str
    headers: dict[str, str] = field(default_factory=dict)


class _NullAudit:
    def pre(self, action_type: str, detail: dict[str, Any]) -> str:
        return ""

    def post(self, parent_record_id: str, outcome: dict[str, Any]) -> str:
        return ""


def cache_key(method: str, path: str, body: Any) -> str:
    """SHA-256 of the RFC 8785 canonical JSON of {method, path, body}."""
    return sha256_hex(canonical({"method": method.upper(), "path": path, "body": body}))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _chunks(items: list[Any], n: int = BATCH) -> Iterable[list[Any]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _retry_after(headers: httpx.Headers) -> float | None:
    for name in ("retry-after", "x-ratelimit-reset"):
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            return max(0.0, float(raw))
        except ValueError:
            continue
    return None


def _wait(state: RetryCallState) -> float:
    exc = state.outcome.exception() if state.outcome else None
    if isinstance(exc, RateLimited) and exc.retry_after is not None:
        base = exc.retry_after
    else:
        base = min(2.0**state.attempt_number, 30.0)
    return base + random.uniform(0.0, 1.0)


# ---------------------------------------------------------------- client


class CrustdataClient:
    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | os.PathLike[str] = ".cache/crustdata",
        offline: bool = False,
        audit: Any = None,
        *,
        transport: httpx.BaseTransport | None = None,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        base_url: str = BASE_URL,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("CRUSTDATA_API_KEY")
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.audit = audit if audit is not None else _NullAudit()
        self.limiter = limiter or RateLimiter(sleep=sleep)
        self._sleep = sleep
        self._http: httpx.Client | None = None
        self._transport = transport
        self._base_url = base_url
        self.calls = 0
        self.cache_hits = 0
        self.credits_spent = 0.0
        self.scope: dict[str, dict[str, Any]] = {}
        self._record_ids: dict[str, str] = {}

    # ------------------------------------------------------------ plumbing

    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                base_url=self._base_url,
                headers={
                    "authorization": f"Bearer {self.api_key or ''}",
                    "x-api-version": API_VERSION,
                    "content-type": "application/json",
                },
                timeout=30.0,
                transport=self._transport,
            )
        return self._http

    def close(self) -> None:
        if self._http is not None:
            self._http.close()

    def record_id_for(self, request_id: str | None) -> str | None:
        """The audit `pre` record id of the call that returned `request_id`."""
        return self._record_ids.get(request_id or "")

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        p = self._cache_path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, key: str, entry: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._cache_path(key))

    def _send(self, method: str, path: str, body: Any) -> httpx.Response:
        self.limiter.acquire(path.split("?")[0])
        try:
            if method == "GET":
                r = self.http.get(path)
            else:
                r = self.http.request(method, path, json=body)
        except httpx.TransportError as e:
            raise TransientError(f"{method} {path}: {type(e).__name__}: {e}") from e
        rid = r.headers.get("x-request-id")
        if r.status_code == 429:
            after = _retry_after(r.headers)
            if after is not None:
                self.limiter.penalise(path.split("?")[0], after)
            raise RateLimited(f"{method} {path}: 429", retry_after=after, request_id=rid)
        if r.status_code >= 500:
            raise TransientError(f"{method} {path}: {r.status_code}", r.status_code, rid)
        return r

    def _fetch(self, method: str, path: str, body: Any) -> tuple[httpx.Response, int]:
        attempts = 0
        for attempt in Retrying(
            stop=stop_after_attempt(MAX_TRIES),
            wait=_wait,
            retry=retry_if_exception_type((RateLimited, TransientError)),
            sleep=self._sleep,
            reraise=True,
        ):
            with attempt:
                attempts += 1
                return self._send(method, path, body), attempts
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _raise_for(entry: dict[str, Any], method: str, path: str) -> None:
        status, rid = entry["status"], entry["headers"].get("x-request-id")
        if status < 400:
            return
        msg = f"{method} {path}: {status} {json.dumps(entry['body'])[:300]}"
        if status == 402:
            raise CreditsExhausted(msg, status, rid)
        if status == 403:
            raise PermissionDenied(msg, status, rid)
        raise CrustdataError(msg, status, rid)

    def _call(self, method: str, path: str, body: Any = None, *, cache: bool = True) -> Response:
        """One audited call. Cached: 2xx bodies and 400/403/404 (deterministic refusals)."""
        method = method.upper()
        key = cache_key(method, path, body)
        entry = self._read_cache(key) if cache else None
        hit = entry is not None
        rid = self.audit.pre(
            "tool_call",
            {
                "name": path,
                "method": method,
                "args_sha256": hash_json({"method": method, "path": path, "body": body}),
                "cache_key": key,
                "cache_hit": hit,
                "offline": self.offline,
            },
        )
        attempts = 0
        try:
            if entry is None:
                if self.offline:
                    raise OfflineMiss(f"offline and not cached: {method} {path} ({key[:12]})")
                r, attempts = self._fetch(method, path, body)
                try:
                    parsed: Any = r.json()
                except ValueError:
                    parsed = r.text
                entry = {
                    "request": {"method": method, "path": path, "body": body},
                    "status": r.status_code,
                    "headers": {
                        k: v
                        for k, v in r.headers.items()
                        if k.lower() in _KEPT_HEADERS or k.lower().startswith("x-ratelimit")
                    },
                    "body": parsed,
                    "fetched_at": _now(),
                }
                if cache and (r.status_code < 300 or r.status_code in (400, 403, 404)):
                    self._write_cache(key, entry)
            entry["headers"] = {k.lower(): v for k, v in entry["headers"].items()}
            self._raise_for(entry, method, path)
        except CrustdataError as e:
            self.audit.post(
                rid,
                {
                    "status": "error",
                    "http_status": e.status,
                    "request_id": e.request_id,
                    "error": f"{type(e).__name__}: {e}",
                    "credits_used": 0,
                    "attempts": attempts,
                },
            )
            raise

        credits = float(entry["headers"].get("x-credits-used") or 0)
        request_id = entry["headers"].get("x-request-id")
        result_sha = hash_json(entry["body"])
        self.calls += 1
        self.cache_hits += hit
        spent = 0.0 if hit else credits
        self.credits_spent += spent
        self.audit.post(
            rid,
            {
                "status": "ok",
                "http_status": entry["status"],
                "result_sha256": result_sha,
                "credits_used": spent,
                "credits_billed_originally": credits,
                "request_id": request_id,
                "fetched_at": entry["fetched_at"],
                "attempts": attempts,
            },
        )
        if request_id:
            self._record_ids[request_id] = rid
        return Response(
            method=method,
            path=path,
            body=entry["body"],
            status=entry["status"],
            request_id=request_id,
            credits_used=spent,
            fetched_at=entry["fetched_at"],
            cache_hit=hit,
            log_record_id=rid or None,
            result_sha256=result_sha,
            headers=entry["headers"],
        )

    # ------------------------------------------------------------ account

    def credits(self) -> dict[str, Any]:
        """Remaining credits (never cached; offline returns a marker)."""
        if self.offline:
            return {"offline": True, "spent_this_run": self.credits_spent}
        body = self._call("GET", "/account/credits", cache=False).body
        account = body.get("account", body) if isinstance(body, dict) else {}
        return {"credits": account.get("credits"), "spent_this_run": self.credits_spent}

    def describe_scope(self, dataset: str) -> dict[str, Any]:
        """Which endpoints and fields our key may use for `company` or `person` (logged)."""
        out: dict[str, Any] = {}
        for path in SCOPE_PATHS[dataset]:
            body = self._call("GET", f"/account/endpoints?path={path}").body
            eps = body.get("endpoints", []) if isinstance(body, dict) else []
            ep = eps[0] if eps else {"path": path, "status": "disabled"}
            fields = ep.get("fields") or {}
            out[path] = {
                "status": ep.get("status", "disabled"),
                "rpm": ep.get("effective_rate_limit_rpm"),
                "base_credits": ep.get("base_credits"),
                "enabled_fields": fields.get("enabled", []),
                "disabled_fields": fields.get("disabled", []),
            }
            self.scope[path] = out[path]
            if out[path]["rpm"]:
                self.limiter.limits[path] = int(out[path]["rpm"])
        return out

    def enabled(self, path: str) -> bool:
        """False only when describe_scope ran and said the endpoint is off."""
        s = self.scope.get(path)
        return s is None or s.get("status") == "enabled"

    # ------------------------------------------------------------ companies

    def identify_companies(
        self, names: list[str], exact: bool = True, by: str = "names"
    ) -> list[IdentifyResult]:
        """POST /company/identify (free), 25 per call; one IdentifyResult per input, in order.

        `by` is `names` or `domains`. `crustdata_company_id` on the result is set only when exactly
        one candidate holds the top confidence score; ranking is resolve's job, not this one's.
        """
        out: list[IdentifyResult] = []
        for chunk in _chunks(list(names)):
            body: dict[str, Any] = {by: chunk}
            if by == "names":
                body["exact_match"] = exact
            r = self._call("POST", "/company/identify", body)
            rows = r.body if isinstance(r.body, list) else []
            for i, q in enumerate(chunk):
                row = rows[i] if i < len(rows) else {}
                out.append(_identify_result(q, row, r))
        return out

    def enrich_companies(
        self, ids: list[str], fields: list[str] | None = None
    ) -> list[CompanyFacts]:
        """POST /company/enrich by crustdata_company_ids only (2 credits per match), 25 per call."""
        uniq = list(dict.fromkeys(str(i) for i in ids if i))
        out: list[CompanyFacts] = []
        for chunk in _chunks(uniq):
            body = {
                "crustdata_company_ids": [int(i) if i.isdigit() else i for i in chunk],
                "fields": fields or COMPANY_FIELDS,
            }
            r = self._call("POST", "/company/enrich", body)
            for row in r.body if isinstance(r.body, list) else []:
                for m in row.get("matches") or []:
                    cd = m.get("company_data") or {}
                    if cd.get("crustdata_company_id") is not None:
                        out.append(_company_facts(cd, r))
        return out

    # ------------------------------------------------------------ people

    def search_person(
        self,
        name: str,
        employer: str | None = None,
        location: str | None = None,
        limit: int = 5,
    ) -> list[PersonCandidate]:
        """POST /person/search, mode exact; employer matches current or past roles (word match)."""
        conds: list[dict[str, Any]] = [{"field": "basic_profile.name", "type": "=", "value": name}]
        if employer:
            conds.append(
                {
                    "field": "experience.employment_details.company_name",
                    "type": "(.)",
                    "value": employer,
                }
            )
        if location:
            conds.append(
                {"field": "basic_profile.location.full_location", "type": "(.)", "value": location}
            )
        filters = conds[0] if len(conds) == 1 else {"op": "and", "conditions": conds}
        body = {"filters": filters, "mode": "exact", "fields": SEARCH_FIELDS, "limit": limit}
        r = self._call("POST", "/person/search", body)
        profiles = r.body.get("profiles", []) if isinstance(r.body, dict) else []
        return [_person_candidate(p, r) for p in profiles if _profile_url(p)]

    def enrich_persons(self, profile_urls: list[str]) -> list[PersonFacts]:
        """POST /person/enrich by LinkedIn URL (1 credit per match), 25 per call.

        Inputs with `match_status` not_found or redacted are omitted; see `enrich_persons_status`.
        """
        return [f for f in self.enrich_persons_status(profile_urls).values() if f is not None]

    def enrich_persons_status(self, profile_urls: list[str]) -> dict[str, PersonFacts | None]:
        """Input URL -> PersonFacts, or None when not_found / redacted / no match."""
        uniq = list(dict.fromkeys(u for u in profile_urls if u))
        out: dict[str, PersonFacts | None] = {}
        for chunk in _chunks(uniq):
            body = {"professional_network_profile_urls": chunk, "fields": PERSON_FIELDS}
            r = self._call("POST", "/person/enrich", body)
            rows = r.body if isinstance(r.body, list) else []
            by_input = {row.get("matched_on"): row for row in rows}
            for i, url in enumerate(chunk):
                row = by_input.get(url) or (rows[i] if i < len(rows) else {})
                matches = row.get("matches") or []
                if row.get("match_status", "matched") != "matched" or not matches:
                    out[url] = None
                    continue
                out[url] = _person_facts(matches[0].get("person_data") or {}, url, r)
        return out

    def identify_persons(self, emails: list[str]) -> list[PersonCandidate]:
        """POST /person/identify by email. 403 on our plan: raises PermissionDenied."""
        out: list[PersonCandidate] = []
        for chunk in _chunks(list(emails)):
            r = self._call("POST", "/person/identify", {"emails": chunk})
            for row in r.body if isinstance(r.body, list) else []:
                if row.get("match_status", "matched") != "matched":
                    continue
                for m in row.get("matches") or []:
                    pd = m.get("person_data") or {}
                    if _profile_url(pd):
                        c = _person_candidate(pd, r)
                        out.append(c.model_copy(update={"score": m.get("confidence_score")}))
        return out


# ---------------------------------------------------------------- mapping


def _str_id(v: Any) -> str | None:
    if isinstance(v, list):
        v = v[0] if v else None
    return None if v is None else str(v)


def _date(v: Any) -> date | None:
    if not v:
        return None
    s = str(v)
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def _profile_url(p: dict[str, Any]) -> str | None:
    sh = p.get("social_handles") or {}
    return (sh.get("professional_network_identifier") or {}).get("profile_url")


def _identify_result(query: str, row: dict[str, Any], r: Response) -> IdentifyResult:
    cands: list[dict[str, Any]] = []
    for rank, m in enumerate(row.get("matches") or []):
        cd = m.get("company_data") or {}
        bi = cd.get("basic_info") or {}
        cands.append(
            {
                "rank": rank,
                "confidence_score": m.get("confidence_score"),
                "crustdata_company_id": _str_id(cd.get("crustdata_company_id")),
                "name": bi.get("name"),
                "primary_domain": bi.get("primary_domain"),
                "all_domains": bi.get("all_domains") or [],
                "website": bi.get("website"),
                "linkedin_url": bi.get("professional_network_url"),
                "employee_count_range": bi.get("employee_count_range"),
                "company_type": bi.get("company_type"),
                "year_founded": bi.get("year_founded"),
                "industries": bi.get("industries") or [],
            }
        )
    top = max((c["confidence_score"] or 0 for c in cands), default=None)
    leaders = [c for c in cands if (c["confidence_score"] or 0) == top]
    lead = leaders[0] if len(leaders) == 1 else None
    return IdentifyResult(
        query=query,
        crustdata_company_id=lead["crustdata_company_id"] if lead else None,
        name=lead["name"] if lead else None,
        primary_domain=lead["primary_domain"] if lead else None,
        confidence_score=top,
        candidates=cands,
        request_id=r.request_id,
        cache_hit=r.cache_hit,
    )


def _brief(p: dict[str, Any], company_id: str) -> PersonBrief:
    bp = p.get("basic_profile") or {}
    title, start, end = bp.get("current_title"), None, None
    ed = (p.get("experience") or {}).get("employment_details") or {}
    for job in [*(ed.get("current") or []), *(ed.get("past") or [])]:
        ids = job.get("employer_company_id") or []
        ids = [str(i) for i in (ids if isinstance(ids, list) else [ids])]
        if company_id in ids:
            title = job.get("employee_title") or title
            start, end = _date(job.get("employee_start_date")), _date(job.get("employee_end_date"))
            break
    return PersonBrief(
        name=bp.get("name") or "",
        title=title,
        linkedin_url=_profile_url(p),
        start_date=start,
        end_date=end,
    )


def _company_facts(cd: dict[str, Any], r: Response) -> CompanyFacts:
    cid = str(cd["crustdata_company_id"])
    bi = cd.get("basic_info") or {}
    hc = cd.get("headcount") or {}
    loc = cd.get("locations") or {}
    people = cd.get("people") or {}
    meta = cd.get("metadata") or {}
    series = []
    for pt in hc.get("timeseries") or []:
        d, n = _date(pt.get("date")), pt.get("employee_count")
        if d is not None and n is not None:
            series.append((d, int(n)))
    return CompanyFacts(
        crustdata_company_id=cid,
        name=bi.get("name") or "",
        primary_domain=bi.get("primary_domain"),
        website=bi.get("website"),
        linkedin_url=bi.get("professional_network_url"),
        year_founded=bi.get("year_founded"),
        status=bi.get("status") or cd.get("status"),
        employee_count_range=bi.get("employee_count_range"),
        headcount_total=hc.get("total"),
        headcount_timeseries=series,
        hq_city=loc.get("city"),
        hq_country=loc.get("country"),
        street_address=loc.get("street_address") or loc.get("headquarters"),
        founders=[_brief(p, cid) for p in people.get("founders") or [] if p.get("basic_profile")],
        decision_makers=[
            _brief(p, cid) for p in people.get("decision_makers") or [] if p.get("basic_profile")
        ],
        total_funding_usd=_decimal((cd.get("funding") or {}).get("total_investment_usd")),
        description=bi.get("description"),
        updated_at=cd.get("updated_at") or meta.get("updated_at") or r.fetched_at,
        source_request_id=r.request_id or "",
        cache_hit=r.cache_hit,
    )


def _person_candidate(p: dict[str, Any], r: Response) -> PersonCandidate:
    bp = p.get("basic_profile") or {}
    loc = bp.get("location") or {}
    current = ((p.get("experience") or {}).get("employment_details") or {}).get("current") or []
    return PersonCandidate(
        name=bp.get("name") or "",
        profile_url=_profile_url(p) or "",
        crustdata_person_id=_str_id(p.get("crustdata_person_id")),
        current_title=bp.get("current_title"),
        current_company=current[0].get("name") if current else None,
        location=loc.get("raw") or loc.get("full_location") if isinstance(loc, dict) else loc,
        request_id=r.request_id,
        cache_hit=r.cache_hit,
    )


def employers(p: dict[str, Any]) -> list[str]:
    """Current and past employer names from a raw search/enrich profile."""
    ed = (p.get("experience") or {}).get("employment_details") or {}
    return [j.get("name") or "" for j in [*(ed.get("current") or []), *(ed.get("past") or [])]]


def _person_facts(pd: dict[str, Any], url: str, r: Response) -> PersonFacts:
    bp = pd.get("basic_profile") or {}
    loc = bp.get("location") or {}
    ed = (pd.get("experience") or {}).get("employment_details") or {}
    jobs: list[Employment] = []
    for is_current, key in ((True, "current"), (False, "past")):
        for j in ed.get(key) or []:
            jobs.append(
                Employment(
                    company_name=j.get("name") or "",
                    crustdata_company_id=_str_id(j.get("crustdata_company_id")),
                    company_domain=j.get("company_website_domain"),
                    title=j.get("title"),
                    start_date=_date(j.get("start_date")),
                    end_date=_date(j.get("end_date")),
                    is_current=is_current,
                )
            )
    current = [j for j in jobs if j.is_current]
    return PersonFacts(
        crustdata_person_id=_str_id(pd.get("crustdata_person_id")) or "",
        name=bp.get("name") or "",
        profile_url=_profile_url(pd) or url,
        current_title=bp.get("current_title"),
        current_company=current[0].company_name if current else None,
        location=loc.get("raw") or loc.get("full_location") if isinstance(loc, dict) else loc,
        employment=jobs,
        updated_at=pd.get("updated_at") or (pd.get("metadata") or {}).get("updated_at") or "",
        source_request_id=r.request_id or "",
        cache_hit=r.cache_hit,
    )
