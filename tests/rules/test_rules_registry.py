"""Registry, logged runner, payload integrity, bears_on, rerank, speed."""

from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pytest
from rules_factory import Book, ctx_for, staff, th, vendor

from casefile.audit.log import AuditLog
from casefile.audit.payloads import default_store
from casefile.report.check import check_evidence
from casefile.rules import TESTS, THRESHOLDS, bears_on, run_tests
from casefile.rules.rank import rerank
from casefile.schemas import Direction, EvidenceObject, Hypothesis, Source


def test_all_seventeen_tests_registered_with_families_and_typologies():
    assert sorted(TESTS) == [f"T{i:02d}" for i in range(1, 18)]
    for t in TESTS.values():
        assert t.families and callable(t.fn)
        assert t.typologies or t.id == "T08"  # Benford is screen-only
        assert set(t.refutes) <= set(t.typologies) or t.id == "T13"


#  Menu pairings deliberately not registered: a career link is the interest itself (conflict of
#  interest), not evidence that the vendor paid the approver; kickback rests on billing anomalies.
NOT_SUPPORTING = {("T15", "kickback")}


def test_registry_covers_the_typology_menu():
    """The proposer picks tests from docs/typologies.md and the pipeline drops supporting evidence
    whose test does not list the hypothesis's typology, so every menu pairing must be registered
    (bar the documented exceptions) and T16 bears only on the menu's relationship typologies."""
    import re
    from pathlib import Path

    menu = Path(__file__).resolve().parents[2] / "docs" / "typologies.md"
    t16: set[str] = set()
    for line in menu.read_text("utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        typ = cells[0].strip("`")
        for tid in re.findall(r"T\d\d", cells[5]):
            if (tid, typ) not in NOT_SUPPORTING:
                assert typ in TESTS[tid].typologies, f"{tid} must list {typ}"
            if tid == "T16":
                t16.add(typ)
    assert set(TESTS["T16"].typologies) == t16
    assert "kickback" not in TESTS["T15"].typologies


def test_tests_for_includes_supporting_and_refuting_tests():
    from casefile.rules import tests_for

    shell = tests_for("shell_company")
    assert {"T01", "T03", "T06", "T07", "T13", "T16", "T17"} <= set(shell)
    assert "T06" in shell  # refutes shell when amounts look like the population
    assert set(tests_for("duplicate_billing")) == {"T04", "T14"}
    assert "T15" in tests_for("conflict_of_interest") and "T15" not in tests_for("kickback")
    assert tests_for("no_such_typology") == []


def test_t16_leaves_hypothesis_pairs_to_the_pipeline():
    from casefile.graph import build

    b = Book()
    b.add("V023", date(2025, 1, 18), 490000, approver_id="S003")
    v = vendor("V023", phone="+91 98220 41736")
    s = staff("S003", phone="9822041736")
    G = build(b.rows, [v], [s])
    assert len(run_tests(["T16"], ctx_for(b, [v], [s], graph=G))) == 1
    h = Hypothesis(
        hypothesis_id="H1",
        typology="shell_company",
        statement="s",
        subjects=["S003"],
        objects=["V023"],
        tests_to_run=["T16"],
    )
    assert run_tests(["T16"], ctx_for(b, [v], [s], graph=G, hypotheses=[h])) == []


def test_thresholds_are_documented():
    for name, t in THRESHOLDS.items():
        assert t.name == name and t.unit and t.rationale
        assert t.source_url.startswith("https://")
    assert "wework" in THRESHOLDS["coworking_markers"].value


def _shell_book() -> Book:
    b = Book()
    b.background()
    for i in range(6):
        d = date(2025, 1, 18) + timedelta(days=25 * i)
        b.add("V023", d, 490000 + 1000 * i, f"BET/{i + 1:03d}", approver_id="S003")
    return b


def test_run_tests_logs_pre_and_post_and_numbers_evidence(tmp_path):
    log = AuditLog(tmp_path / "log.jsonl")
    staff_list = [staff("S003", "Anil Deshpande", approval_limit=500000), staff("S900")]
    ctx = ctx_for(
        _shell_book(), [vendor("V023", created_on=date(2025, 1, 10))], staff_list, audit=log
    )
    evs = run_tests(["T03", "T05", "T06", "T07", "T99"], ctx)
    log.close()
    assert [e.evidence_id for e in evs] == [f"E{i}" for i in range(1, len(evs) + 1)]
    recs = [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]
    pres = [r for r in recs if r["record_phase"] == "pre_execution"]
    posts = {r["parent_record_id"]: r for r in recs if r["record_phase"] == "post_execution"}
    assert [p["action_detail"]["name"] for p in pres] == ["T03", "T05", "T06", "T07", "T99"]
    assert all(p["action_type"] == "rule_test" for p in pres)
    by_pre = {p["record_id"]: posts[p["record_id"]]["outcome"] for p in pres}
    for e in evs:
        assert e.evidence_id in by_pre[e.log_record_id]["evidence_ids"]
    assert by_pre[pres[-1]["record_id"]]["status"] == "error"  # unknown test logged, skipped


def test_every_evidence_passes_the_citation_check():
    b = _shell_book()
    b.add("V023", date(2025, 9, 1), 490000, "BET/001", approver_id="S003")  # duplicate number
    v = vendor("V023", created_on=date(2025, 1, 10), address="Flat 7, Shivneri Apts, Pune 411038")
    s = staff("S003", "Anil Deshpande", address="Flat 7 Shivneri Apartments Pune 411038")
    evs = run_tests(sorted(TESTS), ctx_for(b, [v], [s, staff("S900")]))
    assert evs and len(default_store) > 0
    for e in evs:
        assert check_evidence(e, {}, require_payloads=True) == [], e.evidence_id


def test_a_raising_test_is_logged_and_skipped(monkeypatch, tmp_path):
    from casefile.rules import registry

    def boom(ctx):
        raise RuntimeError("bad rule")

    monkeypatch.setitem(
        registry.TESTS,
        "T06",
        registry.TESTS["T06"].__class__(
            "T06", "round_amounts", ("billing",), ("shell_company",), boom
        ),
    )
    log = AuditLog(tmp_path / "log.jsonl")
    evs = run_tests(["T06", "T07"], ctx_for(_shell_book(), audit=log))
    log.close()
    assert evs and all(e.test_id == "T07" for e in evs)
    assert "RuntimeError: bad rule" in (tmp_path / "log.jsonl").read_text()


def _ev(test_id: str, direction: str, strength: float, obj: str = "V1") -> EvidenceObject:
    return EvidenceObject(
        evidence_id="E1",
        test_id=test_id,
        object_ids=[obj],
        direction=direction,
        strength=strength,
        summary="s",
        quote="q",
        source=Source(kind="ledger_rows", refs=["L1"]),
        sha256="0" * 64,
        log_record_id="r",
    )


def test_bears_on_scopes_refutations_to_their_typologies():
    assert not bears_on(_ev("T05", Direction.refutes, 0.7), "conflict_of_interest")
    assert bears_on(_ev("T05", Direction.refutes, 0.7), "threshold_structuring")
    assert bears_on(_ev("T05", Direction.supports, 0.7), "conflict_of_interest")
    assert bears_on(_ev("T15", Direction.refutes, 0.75), "conflict_of_interest")


def test_rerank_orders_by_evidence_and_centrality():
    def h(hid, obj, typ="shell_company"):
        return Hypothesis(
            hypothesis_id=hid,
            typology=typ,
            statement="s",
            objects=[obj],
            tests_to_run=["T06", "T13"],
            prior_score=0.5,
        )

    evidence = [
        _ev("T06", Direction.supports, 0.7, "V1"),
        _ev("T13", Direction.refutes, 0.8, "V2"),
    ]
    out = rerank([h("H2", "V2"), h("H1", "V1"), h("H3", "V3")], evidence, {"V3": 1.0})
    assert [x.hypothesis_id for x in out] == ["H1", "H3", "H2"]
    assert out[0].prior_score > 0.5 > out[-1].prior_score


def _large_book(rows: int = 1500, vendors: int = 60, staff_n: int = 20) -> tuple:
    b = Book()
    for i in range(rows):
        v = i % vendors
        b.add(
            f"V{v:03d}",
            date(2024, 4, 1) + timedelta(days=(i * 7) % 700),
            round(1000 + (i * 7919) % 900000 + 0.37 * v, 2),
            f"INV-{v}-{i}",
            approver_id=f"S{i % staff_n:03d}",
        )
    vs = [
        vendor(f"V{v:03d}", address=f"Plot {v}, Sector {v % 7}, MIDC Bhosari, Pune")
        for v in range(vendors)
    ]
    ss = [staff(f"S{s:03d}", f"Person {s}", approval_limit=500000) for s in range(staff_n)]
    return b, vs, ss


@pytest.mark.parametrize("n", [th("benford_min_n") + 500])
def test_full_suite_is_fast(n):
    b, vs, ss = _large_book(rows=n)
    t0 = time.perf_counter()
    evs = run_tests(sorted(TESTS), ctx_for(b, vs, ss))
    assert time.perf_counter() - t0 < 2.0
    assert evs
