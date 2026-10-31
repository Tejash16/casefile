"""Re-rank hypotheses by the evidence the rules found and the vendors' graph centrality (b3).

prior' = prior + w_s (1 - e^-S) - w_r (1 - e^-R) + w_c c / max(c), clamped to [0, 1], where S and
R are the summed strengths of supporting and refuting evidence bearing on the hypothesis (same
tests, overlapping subjects/objects, refutations only from tests that refute its typology) and c
is the highest centrality among its vendors. Weights: config.RANK_WEIGHTS.
"""

from __future__ import annotations

import math

from casefile.rules.config import RANK_WEIGHTS
from casefile.rules.registry import bears_on
from casefile.schemas import Direction, EvidenceObject, Hypothesis


def related(h: Hypothesis, e: EvidenceObject) -> bool:
    if h.hypothesis_id in e.hypothesis_ids:
        return True
    if e.test_id not in h.tests_to_run and e.test_id != "T16":
        return False
    objs, subs = set(e.object_ids), set(e.subject_ids)
    if not objs and not subs:
        return False
    if objs and h.objects and not objs & set(h.objects):
        return False
    return not (subs and h.subjects and not subs & set(h.subjects))


def rerank(
    hypotheses: list[Hypothesis], evidence: list[EvidenceObject], centrality: dict[str, float]
) -> list[Hypothesis]:
    top = max(centrality.values(), default=0.0) or 1.0
    scored: list[Hypothesis] = []
    for h in hypotheses:
        evs = [e for e in evidence if related(h, e) and bears_on(e, h.typology)]
        sup = sum(e.strength for e in evs if e.direction == Direction.supports)
        ref = sum(e.strength for e in evs if e.direction == Direction.refutes)
        cent = max((centrality.get(o, 0.0) for o in h.objects), default=0.0) / top
        score = (
            h.prior_score
            + RANK_WEIGHTS["support"] * (1 - math.exp(-sup))
            - RANK_WEIGHTS["refute"] * (1 - math.exp(-ref))
            + RANK_WEIGHTS["centrality"] * cent
        )
        scored.append(h.model_copy(update={"prior_score": round(min(max(score, 0.0), 1.0), 4)}))
    return sorted(scored, key=lambda h: (-h.prior_score, h.hypothesis_id))
