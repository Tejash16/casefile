"""Shared helpers for vendor and staff resolution: thresholds, name and domain normalisation."""

from __future__ import annotations

import re
import sys
from typing import Any
from urllib.parse import urlparse

from rapidfuzz import fuzz

# Defaults; rules/config.py (b3) overrides any of these names when it has landed.
DEFAULTS: dict[str, float] = {
    "identify_accept": 0.85,  # Crustdata confidence_score to auto-accept a single leader
    "identify_judge_min": 0.6,  # below this nothing is worth a judge call
    "identify_tie_margin": 0.1,  # candidates this close to the top are a tie
    "name_token_min": 85,  # brand token must fuzzy-match a token of the candidate name
    "vendor_collapse_min": 92,  # spellings of one vendor share one Identify query
}

FREE_MAIL = {
    "gmail",
    "googlemail",
    "yahoo",
    "ymail",
    "hotmail",
    "outlook",
    "live",
    "msn",
    "rediffmail",
    "rediff",
    "icloud",
    "aol",
    "proton",
    "protonmail",
    "zoho",
}
_SUFFIX = re.compile(
    r"[\s,.]*\b(private\s+limited|pvt\.?\s*ltd\.?|pvt\.?|limited|ltd\.?|llp|inc\.?|llc|"
    r"corporation|corp\.?|plc|gmbh|co\.?|&\s*co\.?|company)\s*$",
    re.IGNORECASE,
)
_GENERIC = {"the", "m/s", "ms", "new", "shree", "shri", "sri"}


def threshold(name: str) -> float:
    try:
        from casefile.rules.config import THRESHOLDS  # type: ignore[import-not-found]

        t = THRESHOLDS.get(name)
        if t is not None:
            return float(getattr(t, "value", t))
    except Exception:  # noqa: BLE001 - b3's config is optional here
        pass
    return DEFAULTS[name]


def strip_suffixes(name: str) -> str:
    """'Tata Steel Limited' -> 'Tata Steel' (case kept: Identify scores the bare name higher)."""
    prev, out = None, name.strip()
    while prev != out:
        prev, out = out, _SUFFIX.sub("", out).strip(" ,.-")
    return out or name.strip()


def norm(name: str | None) -> str:
    s = strip_suffixes(name or "").lower()
    s = re.sub(r"[^a-z0-9& ]+", " ", s)
    return " ".join(s.split())


def brand_token(name: str) -> str | None:
    for tok in norm(name).split():
        if len(tok) >= 3 and tok not in _GENERIC:
            return tok
    return None


def plausible(query: str, candidate_name: str | None) -> bool:
    """The query's brand word appears (fuzzily) in the candidate's name.

    Identify fills a fictional name's results with unrelated companies that share a generic word
    ('Industrial', 'Engineering') at 0.6; none of them carries the brand word.
    """
    brand = brand_token(query)
    if brand is None:
        return True
    toks = norm(candidate_name).split()
    return any(fuzz.ratio(brand, t) >= threshold("name_token_min") for t in toks)


def domain_of(value: str | None) -> str | None:
    """Bare lowercase host from a website, URL or email; None for free-mail domains."""
    if not value:
        return None
    v = value.strip().lower()
    if "@" in v:
        v = v.rsplit("@", 1)[1]
    elif "://" in v:
        v = urlparse(v).hostname or ""
    else:
        v = v.split("/")[0]
    v = v.removeprefix("www.").strip(".")
    if not v or "." not in v or v.split(".")[0] in FREE_MAIL:
        return None
    return v


def domain_stem_matches(query: str, domain: str | None) -> bool:
    """'Pune Metrology' ~ punemetrology.in; 'Tata Steel' ~ tatasteel.com."""
    if not domain:
        return False
    compact = norm(query).replace(" ", "").replace("&", "")
    stem = domain.split(".")[0].replace("-", "")
    if len(stem) < 3 or len(compact) < 3:
        return False
    return (
        stem == compact or fuzz.ratio(stem, compact) >= 90 or (len(stem) >= 5 and stem in compact)
    )


def say(msg: str) -> None:
    print(f"[resolve] {msg}", file=sys.stderr)


def safe_judge(judge: Any, query: Any, candidates: list[dict[str, Any]], kind: str) -> Any:
    """Call a2's judge; any failure counts as 'unsure' (the caller marks the entity ambiguous)."""
    if judge is None or not candidates:
        return None
    try:
        return judge(query, candidates, kind)
    except Exception as e:  # noqa: BLE001 - a model outage must not stop resolution
        say(f"judge failed ({type(e).__name__}: {e}); marking ambiguous")
        return None
