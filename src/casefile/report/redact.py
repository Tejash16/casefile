"""Person-name redaction for published case files: names become initials, ids stay.

Matches a full name in any case with spaces, dots, hyphens or underscores between the parts
(so LinkedIn slugs like `ravi-kumar-1234` are caught) and the `Last, First` form. Vendor names
are never passed in, so they stay. Staff ids (`S004`) and Crustdata record ids are untouched.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

SEP = r"[\s._-]+"


def initials(name: str) -> str:
    parts = [p for p in re.split(r"[\s._-]+", name.strip()) if p]
    return "".join(p[0].upper() + "." for p in parts)


class Redactor:
    """`keep` are names never to touch (vendor names), even when they contain a person's name,
    e.g. "Ravi Kumar Traders" stays whole when "Ravi Kumar" is redacted."""

    def __init__(self, people: Iterable[str], keep: Iterable[str] = ()) -> None:
        kept = sorted({" ".join(k.split()) for k in keep if k and k.strip()}, key=len, reverse=True)
        self._keep = [re.compile(rf"(?<![\w]){re.escape(k)}(?![\w])", re.I) for k in kept]
        names = sorted({" ".join(p.split()) for p in people if p and len(p.strip()) >= 3}, key=len)
        self.mapping: dict[str, str] = {}  # replacement -> original name
        by_name: dict[str, str] = {}
        for name in names:
            key = name.lower()
            if key in by_name:
                continue
            base = initials(name)
            label, n = base, 2
            while label in self.mapping:
                label, n = f"{base}{n}", n + 1
            self.mapping[label] = name
            by_name[key] = label
        patterns: list[tuple[re.Pattern[str], str]] = []
        for name in sorted(self.mapping.values(), key=len, reverse=True):
            parts = [re.escape(p) for p in re.split(r"[\s._-]+", name) if p]
            label = by_name[name.lower()]
            patterns.append((re.compile(rf"(?<![\w]){SEP.join(parts)}(?![\w])", re.I), label))
            if len(parts) >= 2:
                last_first = rf"(?<![\w]){parts[-1]},\s*{r'\s+'.join(parts[:-1])}(?![\w])"
                patterns.append((re.compile(last_first, re.I), label))
        self._patterns = patterns

    def __call__(self, text: str | None) -> str | None:
        if not text:
            return text
        held: list[str] = []

        def hold(m: re.Match[str]) -> str:
            held.append(m.group(0))
            return f"\x00{len(held) - 1}\x00"

        for pat in self._keep:
            text = pat.sub(hold, text)
        for pat, label in self._patterns:
            text = pat.sub(label, text)
        return re.sub("\x00(\\d+)\x00", lambda m: held[int(m.group(1))], text)


class NoRedaction:
    mapping: dict[str, str] = {}

    def __call__(self, text: str | None) -> str | None:
        return text
