"""Stage 3 helper: zero-shot yes / no / unsure entity match on a short candidate list (fast model).

b2's resolver calls `judge_candidates` only for shortlists that thresholds cannot settle. Candidate
indices are the 0-based positions in the `candidates` list.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from casefile.agents import client
from casefile.agents._audit import AuditSink
from casefile.agents.models import MatchWire
from casefile.audit.log import jsonable
from casefile.schemas import MatchDecision, MatchVerdict

MAX_CANDIDATES = 5


def _fields(record: Mapping[str, Any]) -> str:
    lines = []
    for k, v in record.items():
        if v is None or v == "" or v == []:
            continue
        val = v if isinstance(v, str) else json.dumps(jsonable(v), ensure_ascii=False)
        lines.append(f"{k}: {val}")
    return "\n".join(lines)


def build_request(
    query: str | Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    kind: Literal["company", "person"],
) -> tuple[list[str], list[dict[str, Any]]]:
    system_text, instructions = client.load_prompt("match")
    query_text = query if isinstance(query, str) else _fields(query)
    cands = "\n".join(
        f'<candidate index="{i}">\n{_fields(c)}\n</candidate>' for i, c in enumerate(candidates)
    )
    user = (
        f'<query kind="{kind}">\n{query_text.strip()}\n</query>\n\n'
        f"<candidates>\n{cands}\n</candidates>\n\n{instructions}"
    )
    return [system_text], [{"role": "user", "content": user}]


def judge_candidates(
    query: str | Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    kind: Literal["company", "person"] = "company",
    *,
    audit: AuditSink | None = None,
) -> MatchDecision:
    if not candidates:
        return MatchDecision(decision=MatchVerdict.no, index=None, reason="no candidates")
    candidates = list(candidates)[:MAX_CANDIDATES]
    n = len(candidates)

    def validate(out: MatchWire) -> None:
        if out.decision == MatchVerdict.yes:
            if out.index is None or not 0 <= out.index < n:
                raise ValueError(f"decision yes needs an index in 0..{n - 1}, got {out.index}")
        elif out.index is not None:
            raise ValueError(f"index must be null when decision is {out.decision}")

    system_blocks, messages = build_request(query, candidates, kind)
    result = client.call(
        "match",
        system_blocks,
        messages,
        model=client.MODEL_FAST,
        output_schema=MatchWire,
        validate=validate,
        temperature=0,
        effort="low",
        max_tokens=4000,
        audit=audit,
    )
    out: MatchWire = result.output
    return MatchDecision(
        decision=out.decision,
        index=out.index,
        reason=out.reason.strip(),
        log_record_id=result.log_record_id,
    )
