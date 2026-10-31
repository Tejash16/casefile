"""Stage 5: an independent critic weighs one hypothesis against its evidence (fresh context).

The critic sees the hypothesis statement, typology and ids, and the evidence objects only: never the
proposer's rationale or prior score. Its verdict is a recommendation; `agents.gate` decides.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from html import escape

from casefile.agents import client
from casefile.agents._audit import AuditSink
from casefile.agents.models import CritiqueWire, registry_test_ids
from casefile.schemas import CriticOutput, EvidenceObject, Hypothesis, Sentence, Verdict

MAX_WORKERS = 4


def _attr(v: object) -> str:
    return escape(str(v), quote=True)


def render_hypothesis(h: Hypothesis) -> str:
    return (
        f'<hypothesis id="{_attr(h.hypothesis_id)}" typology="{_attr(h.typology)}">\n'
        f"statement: {h.statement}\n"
        f"subjects (staff): {', '.join(h.subjects) or 'none'}\n"
        f"objects (vendors): {', '.join(h.objects) or 'none'}\n"
        "</hypothesis>"
    )


def render_evidence(e: EvidenceObject) -> str:
    source = f"{e.source.kind}: {', '.join(e.source.refs)}"
    if e.source.as_of:
        source += f" (as of {e.source.as_of})"
    return (
        f'<evidence id="{_attr(e.evidence_id)}" test="{_attr(e.test_id)}" '
        f'direction="{_attr(e.direction)}" strength="{e.strength:.2f}">\n'
        f"summary: {e.summary}\nquote: {e.quote}\nsource: {source}\n</evidence>"
    )


def build_request(
    hypothesis: Hypothesis, evidence: Sequence[EvidenceObject]
) -> tuple[list[str], list[dict]]:
    system_text, instructions = client.load_prompt("critique")
    ev = "\n".join(render_evidence(e) for e in evidence)
    user = (
        f"{render_hypothesis(hypothesis)}\n\n"
        f"<evidence_list>\n{ev}\n</evidence_list>\n\n{instructions}"
    )
    return [system_text], [{"role": "user", "content": user}]


def _validator(evidence_ids: set[str], test_ids: set[str]):
    def validate(out: CritiqueWire) -> None:
        errors = []
        if not out.rationale:
            errors.append("rationale is empty")
        for i, s in enumerate(out.rationale, 1):
            if not s.evidence_ids:
                errors.append(f"sentence {i} cites no evidence id")
            unknown = [x for x in s.evidence_ids if x not in evidence_ids]
            if unknown:
                errors.append(f"sentence {i} cites unknown evidence ids {unknown}")
        if out.strongest_counter is not None and out.strongest_counter not in evidence_ids:
            errors.append(f"strongest_counter {out.strongest_counter} is not a given evidence id")
        bad = [t for t in out.missing_tests if t not in test_ids]
        if bad:
            errors.append(f"unknown test ids in missing_tests {bad}")
        if errors:
            raise ValueError("; ".join(errors))

    return validate


def critique(
    hypothesis: Hypothesis,
    evidence: Sequence[EvidenceObject],
    *,
    audit: AuditSink | None = None,
) -> CriticOutput:
    if not evidence:
        # Nothing to weigh: no model call; the gate will return Unsubstantiated.
        return CriticOutput(
            hypothesis_id=hypothesis.hypothesis_id,
            model_verdict=Verdict.Unsubstantiated,
            missing_tests=list(hypothesis.tests_to_run),
        )
    system_blocks, messages = build_request(hypothesis, evidence)
    result = client.call(
        "critique",
        system_blocks,
        messages,
        model=client.MODEL_STRONG,
        output_schema=CritiqueWire,
        validate=_validator({e.evidence_id for e in evidence}, set(registry_test_ids())),
        temperature=0,
        effort="high",
        audit=audit,
    )
    out: CritiqueWire = result.output
    return CriticOutput(
        hypothesis_id=hypothesis.hypothesis_id,
        model_verdict=out.model_verdict,
        rationale=[
            Sentence(
                text=s.text.strip(),
                evidence_ids=list(dict.fromkeys(s.evidence_ids)),
                require_citation=True,
            )
            for s in out.rationale
        ],
        strongest_counter=out.strongest_counter,
        missing_tests=list(dict.fromkeys(out.missing_tests)),
        log_record_id=result.log_record_id,
    )


def critique_all(
    items: Sequence[tuple[Hypothesis, Sequence[EvidenceObject]]],
    *,
    audit: AuditSink | None = None,
    max_workers: int = MAX_WORKERS,
) -> dict[str, CriticOutput]:
    """Critique several hypotheses in parallel. A critique that fails after its retries becomes an
    empty Unsubstantiated recommendation (the failure is already in the audit log)."""

    def one(item: tuple[Hypothesis, Sequence[EvidenceObject]]) -> CriticOutput:
        h, ev = item
        try:
            return critique(h, ev, audit=audit)
        except client.ModelCallError:
            return CriticOutput(
                hypothesis_id=h.hypothesis_id, model_verdict=Verdict.Unsubstantiated
            )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(one, items))
    return {h.hypothesis_id: r for (h, _), r in zip(items, results, strict=True)}
