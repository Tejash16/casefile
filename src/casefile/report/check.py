"""Deterministic citation check run before any case file is rendered.

`check_citations(case, evidence_index) -> list[str]`: empty means the case may be rendered.
`evidence_index` maps an evidence's `sha256` (or its `evidence_id`) to the payload bytes its
quote was taken from; `casefile.audit.payloads.default_store` is the usual one.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

from casefile.schemas import CaseFile, EvidenceObject, Sentence, SourceKind

INLINE_ID = re.compile(r"\[(E\d+)\]")
CRUSTDATA_KINDS = {SourceKind.crustdata_company, SourceKind.crustdata_person}
CRUSTDATA_REF = re.compile(r"^crustdata:(company|person):[^@\s]+@\S+$")


def _short(text: str, n: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def cited_sentences(case: CaseFile) -> list[tuple[str, Sentence]]:
    """(location, sentence) for every sentence that must carry evidence ids."""
    out = [(f"executive_summary[{i}]", s) for i, s in enumerate(case.executive_summary)]
    for f in case.findings:
        out += [(f"findings[{f.hypothesis_id}].rationale[{i}]", s) for i, s in enumerate(f.rationale)]
    return out


def _payload(ev: EvidenceObject, index: Mapping[str, bytes]) -> bytes | None:
    for key in (ev.sha256, ev.evidence_id):
        if key in index:
            data = index[key]
            return data.encode("utf-8") if isinstance(data, str) else data
    return None


def check_evidence(ev: EvidenceObject, index: Mapping[str, bytes], require_payloads: bool) -> list[str]:
    errors: list[str] = []
    eid = ev.evidence_id
    if not ev.quote.strip():
        errors.append(f"{eid}: empty quote")
    payload = _payload(ev, index)
    if payload is None:
        if require_payloads:
            errors.append(f"{eid}: no stored payload for sha256 {ev.sha256[:12]}..., quote unverifiable")
    else:
        actual = hashlib.sha256(payload).hexdigest()
        if actual != ev.sha256:
            errors.append(f"{eid}: payload sha256 {actual[:12]}... != recorded {ev.sha256[:12]}...")
        elif ev.quote not in payload.decode("utf-8", errors="replace"):
            errors.append(f"{eid}: quote not found literally in its source payload: {_short(ev.quote)!r}")
    if ev.source.kind in CRUSTDATA_KINDS:
        if not ev.source.as_of:
            errors.append(f"{eid}: Crustdata source without updated_at (source.as_of)")
        if not ev.source.refs:
            errors.append(f"{eid}: Crustdata source without a record ref")
        for ref in ev.source.refs:
            if not CRUSTDATA_REF.match(ref):
                errors.append(f"{eid}: ref {ref!r} is not crustdata:<kind>:<id>@<updated_at>")
    elif not ev.source.refs:
        errors.append(f"{eid}: source has no refs")
    if not ev.log_record_id:
        errors.append(f"{eid}: no log_record_id")
    return errors


def check_citations(
    case: CaseFile,
    evidence_index: Mapping[str, bytes],
    require_payloads: bool = True,
) -> list[str]:
    """Every executive-summary and findings sentence cites >= 1 existing evidence id; every
    exhibit's quote appears literally in its hashed payload; Crustdata exhibits carry updated_at."""
    errors: list[str] = []
    ids: dict[str, EvidenceObject] = {}
    for ev in case.exhibits:
        if ev.evidence_id in ids:
            errors.append(f"{ev.evidence_id}: duplicate evidence id in exhibits")
        ids[ev.evidence_id] = ev

    for where, s in cited_sentences(case):
        if not s.evidence_ids:
            errors.append(f"{where}: uncited sentence: {_short(s.text)!r}")
        for eid in [*s.evidence_ids, *INLINE_ID.findall(s.text)]:
            if eid not in ids:
                errors.append(f"{where}: cites {eid}, which is not in the exhibits")

    for f in case.findings:
        for eid in [*f.supporting_evidence, *f.counter_evidence]:
            if eid not in ids:
                errors.append(f"findings[{f.hypothesis_id}]: lists {eid}, which is not in the exhibits")

    for ev in case.exhibits:
        errors += check_evidence(ev, evidence_index, require_payloads)
    return errors


def citation_validity(case: CaseFile, evidence_index: Mapping[str, bytes]) -> float:
    """Share of cited sentences whose every id resolves to an exhibit that passes its checks."""
    sentences = cited_sentences(case)
    if not sentences:
        return 1.0
    good_ids = {
        ev.evidence_id for ev in case.exhibits if not check_evidence(ev, evidence_index, True)
    }
    ok = sum(1 for _, s in sentences if s.evidence_ids and set(s.evidence_ids) <= good_ids)
    return ok / len(sentences)
