"""Matching a Crustdata employment or person to our vendor and staff records (T15, T17, graph)."""

from __future__ import annotations

import re
from datetime import date, timedelta

from rapidfuzz import fuzz

from casefile.rules import normalize as norm
from casefile.rules.config import THRESHOLDS
from casefile.schemas import Employment, StaffRecord, VendorRecord


def employment_at_vendor(emp: Employment, v: VendorRecord, fuzzy_min: int) -> str | None:
    """How `emp` matches vendor `v`: by Crustdata company id, else domain, else fuzzy name."""
    cd = v.crustdata
    if (
        cd
        and emp.crustdata_company_id
        and str(emp.crustdata_company_id) == str(cd.crustdata_company_id)
    ):
        return "crustdata_company_id"
    domains = {norm.domain(v.website)}
    if cd:
        domains |= {norm.domain(cd.primary_domain), norm.domain(cd.website)}
    domains.discard(None)
    if emp.company_domain and norm.domain(emp.company_domain) in domains:
        return "domain"
    emp_name = norm.company_name(emp.company_name)
    names = {norm.company_name(v.name_raw), norm.company_name(cd.name) if cd else ""} - {""}
    if emp_name and any(fuzz.token_sort_ratio(emp_name, n) >= fuzzy_min for n in names):
        return "name"
    return None


def _numbers(text: str) -> tuple[set[str], set[str]]:
    """(6-digit PIN codes, other tokens containing digits) of a normalised string."""
    nums = {t for t in text.split() if any(c.isdigit() for c in t)}
    pins = {t for t in nums if t.isdigit() and len(t) == 6}
    return pins, nums - pins


def numbers_agree(a: str, b: str) -> bool:
    """Plot 3 vs Plot 10 in the same estate are different places: when both sides carry house
    or plot numbers they must be the same; PIN codes are compared only when both have one."""
    pa, na = _numbers(a)
    pb, nb = _numbers(b)
    return (not (pa and pb) or pa == pb) and (not (na and nb) or na == nb)


def address_score(a: str | None, b: str | None, fuzzy_min: int, min_tokens: int) -> int | None:
    """Token set ratio of two normalised addresses if they match, else None."""
    if not a or not b or min(len(a.split()), len(b.split())) < min_tokens:
        return None
    if not numbers_agree(a, b):
        return None
    score = round(fuzz.token_set_ratio(a, b))
    return score if score >= fuzzy_min else None


def coworking_building_score(
    a: str | None, b: str | None, fuzzy_min: int, min_tokens: int
) -> int | None:
    """Two coworking addresses in one building: suite numbers dropped, spaced-out markers joined
    ("We Work" -> "wework"), then the usual token set ratio. Unit numbers differ between tenants
    of one building, which is exactly the shared-office case to recognise (and call neutral)."""
    na, nb = (_building(norm.address(x)) for x in (a, b))
    if not na or not nb or min(len(na.split()), len(nb.split())) < min_tokens:
        return None
    score = round(fuzz.token_set_ratio(na, nb))
    return score if score >= fuzzy_min else None


def _building(text: str | None) -> str:
    if not text:
        return ""
    for m in THRESHOLDS["coworking_markers"].value:
        compact = re.sub(r"[^a-z0-9]", "", m.lower())
        text = re.sub(r"\s*".join(map(re.escape, compact)), compact, text)
    return " ".join(t for t in text.split() if not any(c.isdigit() for c in t))


def employment_timing(e: Employment, first: date, last: date, gap: int) -> str | None:
    """How an employment sits against a payment window [first, last]: a phrase for the summary,
    or None when it is more than `gap` days away or its dates cannot place it.

    A past job without an end date has an unknown end, not an open one: it counts only when its
    start falls within `gap` days of the window."""
    start = e.start_date
    if not e.is_current and e.end_date is None:
        if start is None or not (
            first - timedelta(days=gap) <= start <= last + timedelta(days=gap)
        ):
            return None
        if start < first:
            return f"starting {(first - start).days} days before the first payment (end unknown)"
        if start > last:
            return f"starting {(start - last).days} days after the last payment (end unknown)"
        return "starting during the payment period (end unknown)"
    end = None if e.is_current else e.end_date
    if start is None and end is None:
        return None if not e.is_current else "current, overlapping the payment period"
    if (start is None or start <= last) and (end is None or end >= first):
        return "overlapping the payment period"
    if end is not None and 0 <= (first - end).days <= gap:
        return f"ending {(first - end).days} days before the first payment"
    if start is not None and 0 <= (start - last).days <= gap:
        return f"starting {(start - last).days} days after the last payment"
    return None


def staff_profile(s: StaffRecord) -> str | None:
    """The staff member's LinkedIn profile, from Crustdata if resolved, else the staff list."""
    return norm.profile_url(s.crustdata.profile_url if s.crustdata else s.linkedin_url)


def name_score(a: str | None, b: str | None) -> int:
    return round(fuzz.token_sort_ratio(norm.person_name(a), norm.person_name(b)))
