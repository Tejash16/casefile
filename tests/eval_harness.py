"""Eval harness: every planted case in cases/, three runs each, against case.json.

    uv run python tests/eval_harness.py                 # all cases, 3 runs
    uv run python tests/eval_harness.py --runs 1 --case career_overlap

Run 1 is live (it fills the Crustdata cache); runs 2 and 3 are --offline from that cache.
A case passes only if every run gets every expected verdict, turns away no must_clear vendor,
renders (citations valid) and leaves a log that verifies. Writes out/eval/eval.md and
eval.json; exits 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

from casefile.schemas import CaseFile, CaseSpec, ExpectedFinding, Hypothesis, Verdict

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunResult:
    run: int
    ok: bool = False
    error: str | None = None
    expected_total: int = 0
    expected_correct: int = 0
    planted: int = 0  # expected Substantiated
    planted_caught: int = 0
    turned_away: list[str] = field(default_factory=list)  # must_clear vendors with Substantiated
    substantiated: int = 0
    substantiated_correct: int = 0
    findings: int = 0
    unsubstantiated: int = 0
    citation_validity: float | None = None
    log_verifies: bool = False
    wall_seconds: float | None = None
    credits: float = 0
    stubbed: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)


def _matches(exp: ExpectedFinding, h: Hypothesis, exact: bool) -> bool:
    if h.typology != exp.typology:
        return False
    for want, got in ((exp.subjects, h.subjects), (exp.objects, h.objects)):
        if want and (set(want) != set(got) if exact else not set(want) <= set(got)):
            return False
    return True


def score(case: CaseFile, spec: CaseSpec, run: int = 1) -> RunResult:
    """Compare one run's findings to case.json by (typology, subjects, objects) -> verdict."""
    res = RunResult(run=run)
    hyps = {h.hypothesis_id: h for h in case.hypotheses}
    pairs = [(f, hyps[f.hypothesis_id]) for f in case.findings if f.hypothesis_id in hyps]
    res.findings = len(case.findings)
    res.unsubstantiated = sum(1 for f in case.findings if f.verdict == Verdict.Unsubstantiated)
    expected_subst: list[ExpectedFinding] = []

    for exp in spec.expected:
        res.expected_total += 1
        is_planted = exp.verdict == Verdict.Substantiated
        res.planted += is_planted
        if is_planted:
            expected_subst.append(exp)
        matched = [(f, h) for f, h in pairs if _matches(exp, h, exact=True)] or [
            (f, h) for f, h in pairs if _matches(exp, h, exact=False)
        ]
        label = f"{exp.typology.value} {exp.subjects or ''}{exp.objects or ''}".strip()
        if not matched:
            res.mismatches.append(f"{label}: expected {exp.verdict.value}, no such hypothesis")
            continue
        verdicts = [f.verdict for f, _ in matched]
        stray = not is_planted and Verdict.Substantiated in verdicts
        if exp.verdict in verdicts and not stray:
            res.expected_correct += 1
            res.planted_caught += is_planted
        else:
            got = ", ".join(f"{h.hypothesis_id}={f.verdict.value}" for f, h in matched)
            res.mismatches.append(f"{label}: expected {exp.verdict.value}, got {got}")

    for f, h in pairs:
        if f.verdict != Verdict.Substantiated:
            continue
        res.substantiated += 1
        if any(_matches(e, h, exact=False) for e in expected_subst):
            res.substantiated_correct += 1
        elif not any(set(h.objects) & set(e.objects) for e in expected_subst):
            # a Substantiated allegation against a vendor nobody planted is a false accusation,
            # even if that vendor is not on must_clear (another typology on a planted vendor
            # only costs precision)
            res.mismatches.append(
                f"unexpected Substantiated {h.hypothesis_id} {h.typology.value} "
                f"{h.subjects}{h.objects}"
            )
        for v in sorted(set(h.objects) & set(spec.must_clear)):
            if v not in res.turned_away:
                res.turned_away.append(v)
                res.mismatches.append(
                    f"must_clear {v} turned away: "
                    f"{h.hypothesis_id} {h.typology.value} Substantiated"
                )
    res.ok = not res.mismatches
    return res


def run_case(case_dir: Path, spec: CaseSpec, runs: int, out_root: Path) -> list[RunResult]:
    from casefile import pipeline
    from casefile.audit import payloads
    from casefile.audit.verify import verify
    from casefile.report.check import citation_validity

    results = []
    for i in range(1, runs + 1):
        out = out_root / spec.name / f"run{i}"
        payloads.default_store.clear()
        t0 = time.perf_counter()
        try:
            case = pipeline.run(
                case_dir / spec.inputs.tip,
                case_dir / spec.inputs.ledger,
                case_dir / spec.inputs.vendors,
                case_dir / spec.inputs.staff,
                out,
                offline=i > 1,
                case_id=spec.name,
            )
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - a crashed run is a failed run
            res = RunResult(run=i, error=f"{type(exc).__name__}: {exc}".splitlines()[0][:300])
            res.mismatches.append(f"run crashed: {res.error}")
            res.wall_seconds = round(time.perf_counter() - t0, 2)
            (out / "error.txt").parent.mkdir(parents=True, exist_ok=True)
            (out / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            results.append(res)
            continue
        res = score(case, spec, run=i)
        # citation validity from the payloads written to disk only, not the live in-memory store
        store_dir = out / "payloads"
        index = payloads.PayloadStore.load(store_dir) if store_dir.is_dir() else {}
        payloads.default_store.clear()
        res.citation_validity = citation_validity(case, index)
        try:
            rep = verify(out / "log.jsonl")
            res.log_verifies = rep.ok
            if not rep.ok:
                res.mismatches.append("log does not verify: " + "; ".join(rep.lines()[:2]))
        except Exception as exc:  # noqa: BLE001 - a verifier crash fails this run, not the eval
            res.mismatches.append(f"verifier crashed: {type(exc).__name__}: {exc}")
        m = case.metrics
        res.wall_seconds = m.get("wall_seconds", round(time.perf_counter() - t0, 2))
        res.credits = m.get("credits_used", 0) or 0
        res.stubbed = list(m.get("stubbed", []))
        res.ok = not res.mismatches
        results.append(res)
    return results


def _pct(num: float, den: float) -> str:
    return "n/a" if not den else f"{100 * num / den:.0f}%"


def table(all_results: dict[str, list[RunResult]], runs: int) -> str:
    head = (
        "| Case | Fakes caught (per run) | Honest businesses turned away | Allegations correct "
        "| Precision | Citation validity | Unsubstantiated rate | Log verifies | Wall time (s) "
        "| Credits | Result |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    rows = []
    for name, rs in all_results.items():
        caught = ", ".join("crash" if r.error else f"{r.planted_caught}/{r.planted}" for r in rs)
        turned = sorted({v for r in rs for v in r.turned_away})
        ok_runs = [r for r in rs if not r.error]
        correct = sum(r.expected_correct for r in ok_runs)
        total = sum(r.expected_total for r in ok_runs)
        prec = _pct(
            sum(r.substantiated_correct for r in ok_runs), sum(r.substantiated for r in ok_runs)
        )
        cv = [r.citation_validity for r in ok_runs if r.citation_validity is not None]
        cit = f"{100 * sum(cv) / len(cv):.0f}%" if cv else "n/a"
        unsub = _pct(sum(r.unsubstantiated for r in ok_runs), sum(r.findings for r in ok_runs))
        verifies = f"{sum(r.log_verifies for r in rs)}/{len(rs)}"
        walls = [r.wall_seconds for r in rs if r.wall_seconds is not None]
        wall = f"{sum(walls) / len(walls):.1f}" if walls else "n/a"
        credits = f"{sum(r.credits for r in rs):g}"
        passed = sum(r.ok for r in rs)
        result = f"**pass {passed}/{runs}**" if passed == runs else f"FAIL {passed}/{runs}"
        turned_cell = f"{len(turned)} ({', '.join(turned)})" if turned else "0"
        rows.append(
            f"| {name} | {caught} | {turned_cell} "
            f"| {correct}/{total} | {prec} | {cit} | {unsub} | {verifies} | {wall} | {credits} "
            f"| {result} |"
        )
    return head + "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", default=str(ROOT / "cases"))
    ap.add_argument("--case", action="append", help="only these case names (repeatable)")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "out" / "eval"))
    args = ap.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)  # as the CLI does: .env wins over stale shell keys

    specs = []
    for cj in sorted(Path(args.cases).glob("*/case.json")):
        spec = CaseSpec.model_validate_json(cj.read_text(encoding="utf-8"))
        if not args.case or spec.name in args.case or cj.parent.name in args.case:
            specs.append((cj.parent, spec))
    if not specs:
        print(f"FAIL: no cases found under {args.cases}/*/case.json")
        return 1

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, list[RunResult]] = {}
    t0 = time.perf_counter()
    for case_dir, spec in specs:
        print(f"== {spec.name}: {args.runs} run(s)", flush=True)
        all_results[spec.name] = rs = run_case(case_dir, spec, args.runs, out_root)
        for r in rs:
            status = "ok" if r.ok else "FAIL"
            print(f"   run {r.run}: {status}  {r.wall_seconds}s", flush=True)
            for m in r.mismatches:
                print(f"      - {m}", flush=True)

    tbl = table(all_results, args.runs)
    failures = [
        f"- {name} run {r.run}: {m}"
        for name, rs in all_results.items()
        for r in rs
        for m in r.mismatches
    ]
    stubbed = sorted({s for rs in all_results.values() for r in rs for s in r.stubbed})
    md = [
        "# Eval: planted cases",
        "",
        f"{len(specs)} cases x {args.runs} runs; run 1 live, later runs from the Crustdata cache "
        f"(`--offline`). A case passes only if all {args.runs} runs are correct. "
        f"Total {time.perf_counter() - t0:.0f} s.",
        "",
        tbl,
        "**Fakes caught**: planted Substantiated allegations found Substantiated, per run. "
        "**Honest businesses turned away**: must-clear vendors with any Substantiated finding "
        "(target 0). **Precision**: Substantiated findings that match a planted allegation. "
        "**Citation validity**: share of cited sentences whose evidence ids resolve, whose payload "
        "hash verifies and whose quote is literally in the payload.",
        "",
    ]
    if stubbed:
        md += [f"Stages still stubbed during this eval: {', '.join(stubbed)}.", ""]
    if failures:
        md += ["## Mismatches", "", *failures, ""]
    (out_root / "eval.md").write_text("\n".join(md), encoding="utf-8")
    (out_root / "eval.json").write_text(
        json.dumps({k: [asdict(r) for r in v] for k, v in all_results.items()}, indent=2),
        encoding="utf-8",
    )
    print()
    print(tbl)
    if stubbed:
        print(f"stubbed stages: {', '.join(stubbed)}")
    if failures:
        print(f"EVAL FAILED: {len(failures)} mismatch(es); see {out_root / 'eval.md'}")
        return 1
    print(f"EVAL PASSED: all {len(specs)} cases correct on {args.runs}/{args.runs} runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
