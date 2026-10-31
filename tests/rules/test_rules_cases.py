"""All 17 rules on every planted case in cases/ (b1): must_clear vendors never reach the gate's
support line, and each case's planted signal fires."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from casefile.agents.gate import SUPPORT_MIN_STRENGTH
from casefile.rules import TESTS, run_tests
from casefile.rules.context import build_context
from casefile.rules.registry import family

CASES = sorted(
    p
    for p in (Path(__file__).resolve().parents[2] / "cases").glob("*")
    if (p / "case.json").exists()
)


def _run(case: Path):
    ingest = pytest.importorskip("casefile.ingest")
    from casefile.graph import build

    rows, _ = ingest.load_ledger(case / "ledger.csv")
    vendors, _ = ingest.load_vendors(case / "vendors.csv")
    staff, _ = ingest.load_staff(case / "staff.csv")
    rows = ingest.link_ledger(rows, vendors, staff)
    t0 = time.perf_counter()
    G = build(rows, vendors, staff)
    evs = run_tests(sorted(TESTS), build_context(rows, vendors, staff, graph=G))
    return evs, time.perf_counter() - t0


@pytest.mark.skipif(not CASES, reason="cases/ not generated")
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_case_must_clear_and_speed(case):
    spec = json.loads((case / "case.json").read_text("utf-8"))
    evs, secs = _run(case)
    assert secs < 2.0
    clear = set(spec.get("must_clear", []))
    hits = [
        (e.test_id, e.object_ids, e.summary)
        for e in evs
        if e.direction == "supports"
        and e.strength >= SUPPORT_MIN_STRENGTH
        and set(e.object_ids) & clear
    ]
    assert hits == []


def _strong(evs, vid):
    return [
        e
        for e in evs
        if e.direction == "supports" and e.strength >= SUPPORT_MIN_STRENGTH and vid in e.object_ids
    ]


@pytest.mark.parametrize(
    "name,vid,tests",
    [
        ("shell_vendor", "V023", {"T01", "T05", "T06", "T07", "T09", "T11", "T16"}),
        ("duplicate_billing", "V003", {"T04"}),
    ],
)
def test_case_planted_signal_fires(name, vid, tests):
    case = next((c for c in CASES if c.name == name), None)
    if case is None:
        pytest.skip(f"cases/{name} not generated")
    evs, _ = _run(case)
    strong = _strong(evs, vid)
    assert tests <= {e.test_id for e in strong}
    if len(tests) > 1:
        assert len({family(e.test_id) for e in strong}) >= 2


def test_shared_office_pair_is_neutral():
    case = next((c for c in CASES if c.name == "shared_office_honest"), None)
    if case is None:
        pytest.skip("cases/shared_office_honest not generated")
    evs, _ = _run(case)
    pair = [e for e in evs if e.test_id == "T01" and set(e.object_ids) == {"V041", "V042"}]
    assert [e.direction for e in pair] == ["neutral"]
