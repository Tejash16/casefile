"""Name, phone, website and URL normalisation. `name_raw` is never touched; these build keys."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from cleanco import basename

# Indian and common legal suffixes cleanco may leave behind; longest first, matched at the end.
_COMPANY_SUFFIXES = [
    "private limited",
    "pvt limited",
    "pvt ltd",
    "pvt",
    "public limited company",
    "limited",
    "ltd",
    "llp",
    "opc",
    "and company",
    "and co",
    "& co",
    "co",
    "inc",
    "llc",
    "corporation",
    "corp",
    "plc",
    "gmbh",
]
_HONORIFICS = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "prof",
    "shri",
    "sri",
    "smt",
    "kum",
    "km",
    "er",
    "ca",
}


def _fold(raw: str) -> str:
    return unicodedata.normalize("NFKC", raw).casefold()


def normalize_company_name(raw: str) -> str:
    """`BRINDORA ENGINEERING TRADERS PRIVATE LIMITED` -> `brindora engineering traders`."""
    s = _fold(raw or "").replace("’", "'")
    s = re.sub(r"[.,()\[\]\"']", " ", s)
    s = " ".join(s.split())
    s = _fold(basename(s)) if s else s
    s = re.sub(r"[.,]", " ", s)
    s = " ".join(s.split())
    changed = True
    while changed and s:
        changed = False
        for suf in _COMPANY_SUFFIXES:
            if s.endswith(" " + suf) and len(s) > len(suf) + 1:
                s = s[: -len(suf) - 1].rstrip(" &-")
                changed = True
                break
    s = s.replace("&", " and ")
    return " ".join(s.split())


def normalize_person_name(raw: str) -> str:
    """`Mr. Anil  Deshpande` -> `anil deshpande`; `A. Deshpande` -> `a deshpande`."""
    s = _fold(raw or "")
    s = re.sub(r"[.,'’\-]", " ", s)
    tokens = s.split()
    while tokens and tokens[0] in _HONORIFICS:
        tokens = tokens[1:]
    return " ".join(tokens)


def initials_compatible(a: str, b: str) -> bool:
    """True when two normalised names differ only by initials (`a deshpande` ~ `anil deshpande`)."""
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb) or len(ta) < 2 or ta[-1] != tb[-1]:
        return False
    for x, y in zip(ta[:-1], tb[:-1], strict=True):
        if x == y:
            continue
        if (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y)):
            continue
        return False
    return ta != tb


def normalize_phone(raw: str | None) -> str | None:
    """Indian numbers to `+91XXXXXXXXXX`; anything else to digits (keeping a leading `+`)."""
    s = (raw or "").strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "+91" + digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return ("+" if s.startswith("+") else "") + digits if digits else None


def normalize_website(raw: str | None) -> str | None:
    """`https://www.TataSteel.com/en/` -> `tatasteel.com`."""
    s = (raw or "").strip().lower()
    if not s:
        return None
    if "//" not in s:
        s = "//" + s
    host = urlsplit(s).hostname or ""
    return host.removeprefix("www.") or None


def normalize_linkedin_url(raw: str | None) -> str | None:
    """Drop query string, fragment and trailing slash; force `https://www.linkedin.com`."""
    s = (raw or "").strip()
    if not s:
        return None
    parts = urlsplit(s if "//" in s else "https://" + s)
    host = (parts.hostname or "").lower()
    if not host.endswith("linkedin.com"):
        return s
    return "https://www.linkedin.com" + parts.path.rstrip("/")
