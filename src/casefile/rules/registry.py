"""Test registry (docs/contract.md section 6) and the logged runner (b3)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from casefile.rules.context import RuleContext
from casefile.rules.tests_ import (
    t01_identifier_match,
    t02_thin_footprint,
    t03_vendor_age,
    t04_duplicates,
    t05_threshold,
    t06_round_amounts,
    t07_sequential,
    t08_benford,
    t09_off_hours,
    t10_dormant,
    t11_segregation,
    t12_velocity,
    t13_existence,
    t14_lookalike,
    t15_career_overlap,
    t16_graph_path,
    t17_founders,
)
from casefile.schemas import Direction, EvidenceObject


@dataclass(frozen=True)
class Test:
    id: str
    name: str
    families: tuple[str, ...]
    typologies: tuple[str, ...]
    fn: Callable[[RuleContext], list[EvidenceObject]]
    # typologies this test's *refuting* evidence bears on (docs/typologies.md "Refuted by")
    refutes: tuple[str, ...] = field(default=())

    __test__ = False  # not a pytest class


SHELL, PASS, COI, KICK = "shell_company", "pass_through", "conflict_of_interest", "kickback"
NAV, DUP, THRESH, GHOST = (
    "non_accomplice_vendor",
    "duplicate_billing",
    "threshold_structuring",
    "ghost_vendor",
)

_TESTS = [
    Test(
        "T01",
        "vendor_staff_identifier_match",
        ("identity",),
        (SHELL, PASS, GHOST),
        t01_identifier_match.run,
        # a staff-owned vendor is no third party: refutes bribery and the unknowing-vendor scheme
        refutes=(KICK, NAV),
    ),
    Test("T02", "thin_vendor_footprint", ("footprint",), (SHELL, GHOST), t02_thin_footprint.run),
    Test("T03", "vendor_age_vs_first_payment", ("timing",), (SHELL,), t03_vendor_age.run),
    Test(
        "T04",
        "duplicate_invoices",
        ("billing",),
        (DUP, NAV),
        t04_duplicates.run,
        refutes=(DUP, NAV),
    ),
    Test(
        "T05",
        "threshold_structuring",
        ("billing",),
        (THRESH, KICK, COI, NAV),
        t05_threshold.run,
        refutes=(THRESH,),
    ),
    Test(
        "T06",
        "round_amounts",
        ("billing",),
        (SHELL, KICK, NAV, THRESH),
        t06_round_amounts.run,
        refutes=(SHELL,),
    ),
    Test(
        "T07",
        "sequential_invoice_numbers",
        ("billing",),
        (SHELL, GHOST),
        t07_sequential.run,
        refutes=(SHELL,),
    ),
    Test("T08", "benford_population", ("statistical",), (), t08_benford.run),
    Test("T09", "off_hours_postings", ("control",), (SHELL, KICK), t09_off_hours.run),
    Test("T10", "dormant_vendor_reactivated", ("timing",), (GHOST,), t10_dormant.run),
    Test("T11", "segregation_of_duties", ("control",), (SHELL, GHOST, THRESH), t11_segregation.run),
    Test(
        "T12",
        "velocity_and_share",
        ("billing",),
        (KICK, COI),
        t12_velocity.run,
        refutes=(KICK, COI),
    ),
    Test(
        "T13",
        "existence_and_capacity",
        ("footprint",),
        (SHELL, PASS, GHOST),
        t13_existence.run,
        refutes=(SHELL, PASS, GHOST),
    ),
    Test("T14", "lookalike_vendor_names", ("identity",), (DUP, GHOST), t14_lookalike.run),
    Test(
        "T15",
        "career_overlap",
        ("identity",),
        (COI, PASS),  # not kickback: a career link is the interest itself, not a bribe
        t15_career_overlap.run,
        refutes=(COI,),
    ),
    # a staff-vendor relationship bears on the typologies defined by one (docs/typologies.md)
    Test("T16", "graph_path", ("graph",), (SHELL, PASS, COI), t16_graph_path.run),
    Test("T17", "founders_match", ("identity",), (SHELL, PASS, COI), t17_founders.run),
]

TESTS: dict[str, Test] = {t.id: t for t in _TESTS}


def tests_for(typology: str) -> list[str]:
    """Every test whose evidence can count for or against `typology`. Running all of them for a
    hypothesis, not only the ones the proposer picked, makes its verdict a function of the data:
    a refutation (e.g. T06 "no round amounts" against shell_company) is never missed because the
    model left that test out on one run."""
    return sorted(
        tid for tid, t in TESTS.items() if typology in t.typologies or typology in t.refutes
    )


def bears_on(evidence: EvidenceObject, typology: str) -> bool:
    """Does this evidence speak to `typology` in its direction? The same rule as
    pipeline._bears_on: supports count for the test's `typologies`, refutes for its `refutes`,
    neutral for either. So T05's "no threshold clustering" says nothing against
    conflict_of_interest, and T13's "tiny company" says nothing for it."""
    test = TESTS.get(evidence.test_id)
    if test is None:
        return True
    if evidence.direction == Direction.supports:
        return typology in test.typologies
    if evidence.direction == Direction.refutes:
        return typology in test.refutes
    return typology in test.typologies or typology in test.refutes


def family(test_id: str) -> str:
    test = TESTS.get(test_id)
    return test.families[0] if test else "other"


class _NullAudit:
    def pre(self, action_type: str, detail: dict[str, Any]) -> str:
        return f"noaudit-{uuid.uuid4()}"

    def post(self, parent_record_id: str, outcome: dict[str, Any]) -> str:
        return f"noaudit-{uuid.uuid4()}"


def run_tests(test_ids: list[str], ctx: RuleContext) -> list[EvidenceObject]:
    """Run each test inside an audit pre/post pair; assign evidence ids E1, E2, ... in order.

    A test that raises is logged with `status: error` and skipped so one bad rule cannot stop
    the run; its tests in tests/rules are what keep that from happening.
    """
    audit = ctx.audit or _NullAudit()
    out: list[EvidenceObject] = []
    for tid in test_ids:
        test = TESTS.get(tid)
        rid = audit.pre("rule_test", {"name": tid, "test": test.name if test else None})
        if test is None:
            audit.post(rid, {"status": "error", "error": f"unknown test {tid}", "evidence_ids": []})
            continue
        try:
            found = test.fn(ctx)
        except Exception as exc:  # noqa: BLE001 - logged, run continues
            audit.post(
                rid,
                {"status": "error", "error": f"{type(exc).__name__}: {exc}", "evidence_ids": []},
            )
            continue
        ids: list[str] = []
        for ev in found:
            ctx.evidence_counter += 1
            eid = f"E{ctx.evidence_counter}"
            out.append(ev.model_copy(update={"evidence_id": eid, "log_record_id": rid}))
            ids.append(eid)
        audit.post(rid, {"status": "ok", "evidence_ids": ids})
    return out
