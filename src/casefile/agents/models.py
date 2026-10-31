"""Wire models: the JSON each model call must return (strict schemas sent via output_config.format).

These stay inside `agents/`. Each call site converts its wire model into the contract object from
`casefile.schemas` (Hypothesis, MatchDecision, CriticOutput) before returning it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from casefile.schemas import MatchVerdict, Origin, Typology, Verdict

ALL_TEST_IDS = [f"T{n:02d}" for n in range(1, 18)]


def registry_test_ids() -> list[str]:
    """Test ids from b3's registry when it has landed, else the contract's T01..T17."""
    try:
        from casefile.rules.registry import TESTS  # type: ignore[import-not-found]

        return sorted(TESTS) or ALL_TEST_IDS
    except Exception:
        return ALL_TEST_IDS


def test_families() -> dict[str, list[str]]:
    """Test id -> families, from the registry when available, else contract section 6."""
    try:
        from casefile.rules.registry import TESTS  # type: ignore[import-not-found]

        fams = {tid: list(t.families) for tid, t in TESTS.items()}
        if fams:
            return fams
    except Exception:
        pass
    return dict(CONTRACT_FAMILIES)


CONTRACT_FAMILIES: dict[str, list[str]] = {
    "T01": ["identity"],
    "T02": ["footprint"],
    "T03": ["timing"],
    "T04": ["billing"],
    "T05": ["billing"],
    "T06": ["billing"],
    "T07": ["billing"],
    "T08": ["statistical"],
    "T09": ["control"],
    "T10": ["timing"],
    "T11": ["control"],
    "T12": ["billing"],
    "T13": ["footprint"],
    "T14": ["identity"],
    "T15": ["identity"],
    "T16": ["graph"],
    "T17": ["identity"],
}


class ProposedHypothesis(BaseModel):
    typology: Typology
    statement: str
    subjects: list[str] = Field(description="staff ids, e.g. S004; may be empty")
    objects: list[str] = Field(description="vendor ids, e.g. V017")
    tests_to_run: list[str] = Field(description="test ids from the registry, e.g. T15")
    prior_score: float = Field(ge=0, le=1)
    origin: Origin
    rationale: str


class ProposeOutput(BaseModel):
    hypotheses: list[ProposedHypothesis]


class MatchWire(BaseModel):
    decision: MatchVerdict
    index: int | None = Field(description="candidate index when decision is yes, else null")
    reason: str


class CritiqueSentence(BaseModel):
    text: str
    evidence_ids: list[str] = Field(
        description="ids of the evidence this sentence states, e.g. E12"
    )


class CritiqueWire(BaseModel):
    model_verdict: Verdict
    rationale: list[CritiqueSentence]
    strongest_counter: str | None = Field(
        description="evidence id that most weakens the hypothesis, or null"
    )
    missing_tests: list[str] = Field(description="test ids that would settle open questions")
