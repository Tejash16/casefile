"""Stage 6: write the case file narrative with the Citations API over `search_result` blocks.

This is the only call that uses citations (it cannot share a call with structured output). Each
EvidenceObject becomes one search result whose `source` is `evidence:<id>|<sha256>`; the writer
never sees raw tool output. The response is split into sentences; each sentence takes the evidence
ids of the citations on the text it overlaps. Sentences with no citation are dropped and logged.
If the call fails, the summary falls back to deterministic sentences built from the evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from casefile.agents import client
from casefile.agents._audit import AuditSink, get_audit
from casefile.agents.gate import GATE_ASSUMPTIONS
from casefile.schemas import CaseFile, EvidenceObject, Finding, Hypothesis, Sentence, Tip, Verdict

VERDICT_ORDER = {Verdict.Substantiated: 0, Verdict.Unfounded: 1, Verdict.Unsubstantiated: 2}
SOURCE_PREFIX = "evidence:"
PREDICATION_CHARS = 400
# Share of a sentence's non-space characters that must lie inside cited text for it to be kept;
# stops an uncited clause ("..., and he steered contracts to it") riding on a cited one.
MIN_CITED_SHARE = 0.6
_TRIM = set(" \t\r\n-*•")
ABBREVIATIONS = {"pvt", "ltd", "inc", "co", "corp", "llp", "no", "rs", "mr", "ms", "dr", "st", "vs"}

_HEADING = re.compile(r"^\s*#{1,4}\s*(.+?)\s*$")
_FINDING = re.compile(r"\bfinding\s+(H\d+)\b", re.IGNORECASE)
_BOUNDARY = re.compile(r"[.!?]+(?=\s+[A-Z0-9\"'“(])")


def _eid_key(eid: str) -> tuple[int, str]:
    digits = re.sub(r"\D", "", eid)
    return (int(digits) if digits else 0, eid)


def source_id(e: EvidenceObject) -> str:
    return f"{SOURCE_PREFIX}{e.evidence_id}|{e.sha256}"


def search_result(e: EvidenceObject) -> dict[str, Any]:
    ref = f"Source: {e.source.kind} {', '.join(e.source.refs)}"
    if e.source.as_of:
        ref += f" (as of {e.source.as_of})"
    return {
        "type": "search_result",
        "source": source_id(e),
        "title": f"{e.evidence_id}: {e.summary}",
        # the API rejects empty text blocks, so a blank quote must not disable the whole writer
        # summary first so derived facts (e.g. "within 5% under the limit") are citable too
        "content": [
            {"type": "text", "text": e.summary.strip() or "(no summary)"},
            {"type": "text", "text": e.quote.strip() or "(empty quote)"},
            {"type": "text", "text": ref},
        ],
        "citations": {"enabled": True},
    }


def _sort_findings(findings: Sequence[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: VERDICT_ORDER.get(f.verdict, 3))


def cited_ids(f: Finding) -> list[str]:
    ids = list(f.supporting_evidence) + list(f.counter_evidence)
    ids += [i for s in f.rationale for i in s.evidence_ids]
    return list(dict.fromkeys(ids))


def build_request(
    findings: Sequence[Finding],
    evidence: Sequence[EvidenceObject],
    hypotheses: Mapping[str, Hypothesis],
) -> tuple[list[str], list[dict[str, Any]]]:
    system_text, instructions = client.load_prompt("write")
    lines = []
    for f in findings:
        h = hypotheses.get(f.hypothesis_id)
        typology = f' typology="{escape(str(h.typology))}"' if h else ""
        lines.append(f'<finding id="{f.hypothesis_id}"{typology} verdict="{f.verdict}">')
        if h:
            lines.append(f"allegation: {h.statement}")
        lines.append(f"supporting evidence: {', '.join(f.supporting_evidence) or 'none'}")
        lines.append(f"counter-evidence: {', '.join(f.counter_evidence) or 'none'}")
        if f.data_gaps:
            lines.append(f"data gaps: {'; '.join(f.data_gaps)}")
        lines.append("</finding>")
    content: list[dict[str, Any]] = [search_result(e) for e in evidence]
    content.append(
        {
            "type": "text",
            "text": "<findings>\n" + "\n".join(lines) + f"\n</findings>\n\n{instructions}",
        }
    )
    return [system_text], [{"role": "user", "content": content}]


# ---------------------------------------------------------------- response parsing


def _citation_ids(
    block: Any, order: Sequence[EvidenceObject], index: Mapping[str, EvidenceObject]
) -> list[str]:
    ids = []
    for c in getattr(block, "citations", None) or []:
        src = getattr(c, "source", "") or ""
        eid = None
        if src.startswith(SOURCE_PREFIX):
            eid, _, sha = src[len(SOURCE_PREFIX) :].partition("|")
            if eid not in index or index[eid].sha256 != sha:
                eid = None
        if eid is None:
            i = getattr(c, "search_result_index", None)
            if isinstance(i, int) and 0 <= i < len(order) and src == source_id(order[i]):
                eid = order[i].evidence_id
        if eid:
            ids.append(eid)
    return ids


def split_sentences(line: str) -> list[tuple[int, int]]:
    """Sentence spans in one line. Splits at . ! ? followed by whitespace and an uppercase letter,
    digit or quote, except after abbreviations (Pvt., Ltd., Rs., single initials)."""
    spans = []
    start = 0
    for m in _BOUNDARY.finditer(line):
        word = re.search(r"([A-Za-z]+)\.?$", line[start : m.start() + 1])
        token = word.group(1).lower() if word else ""
        if token in ABBREVIATIONS or len(token) == 1:
            continue
        spans.append((start, m.end()))
        start = m.end()
    if line[start:].strip():
        spans.append((start, len(line)))
    return [(s, e) for s, e in spans if line[s:e].strip()]


def parse_sections(
    message: Any,
    order: Sequence[EvidenceObject],
    finding_ids: set[str] | None = None,
) -> tuple[dict[str, list[Sentence]], list[str]]:
    """Split the cited response into {section: [Sentence]} and a list of dropped texts.

    Sections are "summary" and the hypothesis ids from "## Finding H<n>" headings (only ids in
    `finding_ids` when given). A sentence is kept only if at least MIN_CITED_SHARE of its
    non-space characters lie inside cited text blocks; it then carries those blocks' evidence ids.
    """
    index = {e.evidence_id: e for e in order}
    full = ""
    spans: list[tuple[int, int, list[str]]] = []
    for b in getattr(message, "content", []):
        if getattr(b, "type", None) != "text":
            continue
        start = len(full)
        full += b.text
        ids = _citation_ids(b, order, index)
        if ids:
            spans.append((start, len(full), ids))

    sections: dict[str, list[Sentence]] = {}
    dropped: list[str] = []
    section = "summary"
    offset = 0
    for line in full.splitlines(keepends=True):
        line_start = offset
        offset += len(line)
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(1)
            m = _FINDING.search(title)
            section = (
                m.group(1).upper() if m else ("summary" if "summary" in title.lower() else "other")
            )
            continue
        for s, e in split_sentences(line):
            # trim whitespace and bullet characters so a cited block's trailing space cannot
            # lend its citation to the next sentence
            while s < e and line[s] in _TRIM:
                s += 1
            while e > s and line[e - 1].isspace():
                e -= 1
            text = re.sub(r"\s+", " ", line[s:e]).strip()
            if not text:
                continue
            a, z = line_start + s, line_start + e
            hit = [(max(a, bs), min(z, be), bids) for (bs, be, bids) in spans if bs < z and be > a]
            cited = sum(1 for (x, y, _) in hit for c in full[x:y] if not c.isspace())
            total = sum(1 for c in full[a:z] if not c.isspace())
            ids = sorted(dict.fromkeys(i for (_, _, bids) in hit for i in bids), key=_eid_key)
            known = section == "summary" or (
                section != "other" and (finding_ids is None or section in finding_ids)
            )
            if ids and known and total and cited / total >= MIN_CITED_SHARE:
                sections.setdefault(section, []).append(
                    Sentence(text=text, evidence_ids=ids, require_citation=True)
                )
            else:
                dropped.append(text)
    return sections, dropped


# ---------------------------------------------------------------- deterministic fallbacks


def _fallback_summary(
    findings: Sequence[Finding],
    index: Mapping[str, EvidenceObject],
    hypotheses: Mapping[str, Hypothesis],
) -> list[Sentence]:
    out = []
    for f in findings:
        ids = [i for i in (f.supporting_evidence + f.counter_evidence) if i in index]
        if not ids:
            continue
        lead = (
            index[ids[0]]
            if f.verdict != Verdict.Unfounded or not f.counter_evidence
            else index.get(f.counter_evidence[0], index[ids[0]])
        )
        h = hypotheses.get(f.hypothesis_id)
        label = f"{f.hypothesis_id} ({h.typology})" if h else f.hypothesis_id
        key = lead.summary.rstrip(".")
        out.append(
            Sentence(
                text=f"Allegation {label} is {f.verdict}; key evidence: {key}.",
                evidence_ids=[lead.evidence_id],
                require_citation=True,
            )
        )
    return out


def _fallback_rationale(f: Finding, index: Mapping[str, EvidenceObject]) -> list[Sentence]:
    ids = [i for i in (f.supporting_evidence + f.counter_evidence) if i in index][:3]
    return [Sentence(text=index[i].summary, evidence_ids=[i], require_citation=True) for i in ids]


def _predication(tip: Tip | str | None) -> Sentence:
    if tip is None:
        return Sentence(text="No tip was supplied; the investigation was predicated on screening.")
    text = tip.text if isinstance(tip, Tip) else str(tip)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > PREDICATION_CHARS:
        text = text[:PREDICATION_CHARS].rsplit(" ", 1)[0] + " …"
    when = f" received {tip.received_at}" if isinstance(tip, Tip) else ""
    return Sentence(text=f'An insider tip{when} alleged: "{text}"')


# ---------------------------------------------------------------- entry point


def write_case_file(
    findings: Sequence[Finding],
    evidence: Sequence[EvidenceObject],
    meta: Mapping[str, Any],
    *,
    audit: AuditSink | None = None,
) -> CaseFile:
    audit = get_audit(audit)
    findings = _sort_findings(findings)
    index = {e.evidence_id: e for e in evidence}
    hypotheses = {h.hypothesis_id: h for h in meta.get("hypotheses", []) or []}
    referenced = sorted({i for f in findings for i in cited_ids(f) if i in index}, key=_eid_key)
    order = [index[i] for i in referenced]

    sections: dict[str, list[Sentence]] = {}
    dropped: list[str] = []
    error = None
    truncated = False
    if order:
        system_blocks, messages = build_request(findings, order, hypotheses)
        try:
            result = client.call(
                "write",
                system_blocks,
                messages,
                model=client.MODEL_STRONG,
                temperature=0,
                effort="low",  # 7.5 s vs 17 s at medium, same cited content
                audit=audit,
            )
            sections, dropped = parse_sections(
                result.message, order, {f.hypothesis_id for f in findings}
            )
            if getattr(result.message, "stop_reason", None) == "max_tokens" and sections:
                # the last sentence may be cut mid-claim; later sections fall back
                truncated = True
                last = list(sections)[-1]
                dropped.append(sections[last].pop().text)
                if not sections[last]:
                    del sections[last]
        except client.ModelCallError as e:
            error = str(e)

    summary = sections.get("summary") or _fallback_summary(findings, index, hypotheses)
    final_findings = []
    for f in findings:
        narrative = sections.get(f.hypothesis_id) or f.rationale or _fallback_rationale(f, index)
        final_findings.append(f.model_copy(update={"rationale": list(narrative)}))

    rid = audit.pre("render", {"name": "writer_citation_filter", "sections": sorted(sections)})
    audit.post(
        rid,
        {
            "status": "ok" if error is None else "fallback",
            "error": error,
            "truncated": truncated,
            "kept_sentences": sum(len(v) for v in sections.values()),
            "dropped_sentences": len(dropped),
            "dropped": [d[:200] for d in dropped],
            "summary_source": "writer" if sections.get("summary") else "fallback",
        },
    )

    exhibit_ids = {i for s in summary for i in s.evidence_ids}
    for f in final_findings:
        exhibit_ids |= set(cited_ids(f))
    metrics = dict(meta.get("metrics", {}) or {})
    totals = client.usage_totals()
    for k in ("model_calls", "tokens_in", "tokens_out", "cache_read"):
        metrics[k] = totals[k]

    return CaseFile(
        case_id=meta["case_id"],
        company_name=meta["company_name"],
        generated_at=meta["generated_at"],
        predication=_predication(meta.get("tip")),
        executive_summary=summary,
        scope=list(meta.get("scope", []) or []),
        approach=list(meta.get("approach", []) or []),
        hypotheses=list(meta.get("hypotheses", []) or []),
        findings=final_findings,
        data_quality=list(meta.get("data_quality", []) or []),
        assumptions={**GATE_ASSUMPTIONS, **dict(meta.get("assumptions", {}) or {})},
        exhibits=[index[i] for i in sorted(exhibit_ids & index.keys(), key=_eid_key)],
        metrics=metrics,
        merkle_root=meta.get("merkle_root", ""),
        verify_command=meta.get("verify_command", ""),
    )
