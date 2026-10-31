"""Matching a Crustdata employment or person to our vendor and staff records (T15, T17, graph)."""

from __future__ import annotations

from rapidfuzz import fuzz

from casefile.rules import normalize as norm
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


def staff_profile(s: StaffRecord) -> str | None:
    """The staff member's LinkedIn profile, from Crustdata if resolved, else the staff list."""
    return norm.profile_url(s.crustdata.profile_url if s.crustdata else s.linkedin_url)


def name_score(a: str | None, b: str | None) -> int:
    return round(fuzz.token_sort_ratio(norm.person_name(a), norm.person_name(b)))
