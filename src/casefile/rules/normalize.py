"""Identifier normalisation shared by the master tests and the graph (pure string functions)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from casefile.rules.config import THRESHOLDS
from casefile.schemas import AddressType

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ADDRESS_ABBREV = {
    "rd": "road",
    "nr": "near",
    "opp": "opposite",
    "bldg": "building",
    "apt": "apartment",
    "apts": "apartments",
    "flr": "floor",
    "hsg": "housing",
    "soc": "society",
    "ind": "industrial",
    "est": "estate",
}
_PO_BOX = ("p.o. box", "po box", "p o box", "post box", "p.b. no", "post bag")
_RESIDENTIAL = ("flat", "apartment", "house no", "h.no", "h no", "bungalow", "residency")
_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "sri", "kumari", "prof"}
_COMPANY_SUFFIXES = (
    "private limited",
    "pvt ltd",
    "pvt",
    "limited",
    "ltd",
    "llp",
    "inc",
    "llc",
    "and company",
    "and co",
    "co",
    "corporation",
    "corp",
)


def digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def phone(s: str | None) -> str | None:
    """Digits only, last 10 (drops +91 / 0 trunk prefixes); None if too short to identify."""
    d = digits(s)
    return d[-10:] if len(d) >= 7 else None


def bank_account(s: str | None) -> str | None:
    a = re.sub(r"[^A-Z0-9]", "", (s or "").upper()).lstrip("0")
    return a if len(a) >= 6 else None


def tax_id(s: str | None) -> str | None:
    t = re.sub(r"[^A-Z0-9]", "", (s or "").upper())
    return t or None


def email(s: str | None) -> str | None:
    e = (s or "").strip().lower()
    return e if "@" in e else None


def email_domain(s: str | None) -> str | None:
    e = email(s)
    return e.rsplit("@", 1)[1] if e else None


def domain(s: str | None) -> str | None:
    """`https://www.acme.co.in/about` -> `acme.co.in`."""
    if not s:
        return None
    d = s.strip().lower()
    d = re.sub(r"^[a-z]+://", "", d).split("/")[0].split("?")[0]
    d = d.removeprefix("www.")
    return d or None


def address(s: str | None) -> str | None:
    """Lowercase, punctuation to spaces, common abbreviations expanded (rd -> road, nr -> near)."""
    if not s:
        return None
    tokens = _NON_ALNUM.sub(" ", s.lower()).split()
    out = " ".join(_ADDRESS_ABBREV.get(t, t) for t in tokens)
    return out or None


def is_coworking(raw_address: str | None, markers: Iterable[str] | None = None) -> bool:
    if not raw_address:
        return False
    text = " ".join(raw_address.lower().split())
    marks = markers if markers is not None else THRESHOLDS["coworking_markers"].value
    return any(m in text for m in marks)


def address_type(raw_address: str | None, declared: AddressType | str | None = None) -> AddressType:
    """Coworking markers win (judges' shared-office rule), then the master's own type, then a
    text heuristic for PO boxes and residences."""
    if is_coworking(raw_address):
        return AddressType.coworking
    if declared and AddressType(declared) != AddressType.unknown:
        return AddressType(declared)
    text = " ".join((raw_address or "").lower().split())
    if not text:
        return AddressType.unknown
    if any(m in text for m in _PO_BOX):
        return AddressType.po_box
    if any(m in text for m in _RESIDENTIAL):
        return AddressType.residential
    return AddressType.unknown


def person_name(s: str | None) -> str:
    tokens = _NON_ALNUM.sub(" ", (s or "").lower()).split()
    return " ".join(t for t in tokens if t not in _HONORIFICS)


def company_name(s: str | None) -> str:
    """Lowercase, punctuation stripped, legal suffixes removed (repeatedly, from the end)."""
    text = " ".join(_NON_ALNUM.sub(" ", (s or "").lower().replace("&", " and ")).split())
    changed = True
    while changed:
        changed = False
        for suf in _COMPANY_SUFFIXES:
            if text.endswith(" " + suf):
                text = text[: -len(suf) - 1].rstrip()
                changed = True
    return text


def profile_url(s: str | None) -> str | None:
    """LinkedIn URL reduced to `linkedin.com/in/<slug>` for comparison."""
    if not s:
        return None
    u = re.sub(r"^[a-z]+://", "", s.strip().lower()).removeprefix("www.").rstrip("/")
    u = u.split("?")[0]
    return u or None
