"""Six stages wired together: ingest -> propose -> resolve -> test -> critique/gate -> write/render.

Each function is looked up at call time through REGISTRY: the real module if it exists and exports
the name, otherwise casefile.stubs.<group>. A real module replaces a stub by landing on main; no
stage code changes. CASEFILE_FORCE_STUBS=rules,agents forces stubs for those keys.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from casefile.audit.payloads import default_store as payload_store
from casefile.schemas import (
    CaseFile,
    Direction,
    EvidenceObject,
    Finding,
    Hypothesis,
    StaffRecord,
    Typology,
    VendorRecord,
    Verdict,
)

# key -> (real module, stub module)
REGISTRY: dict[str, tuple[str, str]] = {
    "audit": ("casefile.audit.log", "casefile.stubs.audit"),
    "ingest": ("casefile.ingest", "casefile.stubs.ingest"),
    "stats": ("casefile.ingest.stats", "casefile.stubs.ingest"),
    "crustdata": ("casefile.crustdata.client", "casefile.stubs.crustdata"),
    "resolve": ("casefile.resolve", "casefile.stubs.crustdata"),
    "propose": ("casefile.agents.propose", "casefile.stubs.agents"),
    "match": ("casefile.agents.match", "casefile.stubs.agents"),
    "critique": ("casefile.agents.critique", "casefile.stubs.agents"),
    "gate": ("casefile.agents.gate", "casefile.stubs.agents"),
    "write": ("casefile.agents.write", "casefile.stubs.agents"),
    "graph": ("casefile.graph", "casefile.stubs.graph"),
    "rules": ("casefile.rules", "casefile.stubs.rules"),
    "rules_context": ("casefile.rules.context", "casefile.stubs.rules"),
    "thresholds": ("casefile.rules.config", "casefile.stubs.rules"),
    "rank": ("casefile.rules.rank", "casefile.stubs.rules"),
    "registry": ("casefile.rules.registry", "casefile.stubs.rules"),
    "check": ("casefile.report.check", "casefile.stubs.report"),
    "render": ("casefile.report.render", "casefile.stubs.report"),
}

STUBBED: set[str] = set()

VERDICT_ORDER = {Verdict.Substantiated: 0, Verdict.Unfounded: 1, Verdict.Unsubstantiated: 2}


class CitationError(RuntimeError):
    """The case file has sentences without valid evidence ids; render refused."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} citation error(s): " + "; ".join(errors[:5]))
        self.errors = errors


def impl(key: str, attr: str) -> Any:
    """The real `attr` for stage `key` if it has landed, else the stub's."""
    real, stub = REGISTRY[key]
    forced = {k.strip() for k in os.environ.get("CASEFILE_FORCE_STUBS", "").split(",")}
    if key not in forced and real.split(".")[1] not in forced:
        try:
            return getattr(importlib.import_module(real), attr)
        except ModuleNotFoundError as e:
            # only a missing module falls back; a broken import inside a real module raises
            if e.name is None or not real.startswith(e.name):
                raise
        except AttributeError:
            pass
    STUBBED.add(key)
    return getattr(importlib.import_module(stub), attr)


def _set_agents_audit(audit: Any) -> None:
    """Route a2's model_call and gate records into this run's log (no-op until agents land)."""
    if "agents" in os.environ.get("CASEFILE_FORCE_STUBS", ""):
        return
    try:
        from casefile.agents import set_audit
    except ImportError:
        return
    set_audit(audit)
    if audit is not None:
        try:
            from casefile.agents.client import reset_usage_totals
        except ImportError:
            return
        reset_usage_totals()  # per-run token totals; the eval harness runs cases in one process


def _model_errors() -> tuple[type[BaseException], ...]:
    """Errors that mean "the model gave no usable answer"; the gate then decides without it."""
    try:
        from casefile.agents.client import ModelCallError
    except ImportError:
        return ()
    return (ModelCallError,)


def _people(staff: list[StaffRecord], vendors: list[VendorRecord]) -> list[str]:
    """Person names for --redact: staff, their Crustdata profiles, vendor founders and leaders."""
    names = [s.name_raw for s in staff] + [s.crustdata.name for s in staff if s.crustdata]
    for v in vendors:
        if v.crustdata:
            names += [p.name for p in [*v.crustdata.founders, *v.crustdata.decision_makers]]
    return names


def _vendor_names(vendors: list[VendorRecord]) -> list[str]:
    """Company names --redact must leave alone, even where they contain a person's name."""
    names = [v.name_raw for v in vendors] + [v.crustdata.name for v in vendors if v.crustdata]
    return sorted(set(names))


def _sha256_file(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _assumptions(thresholds: dict[str, Any]) -> dict[str, str]:
    out = {}
    for name, t in thresholds.items():
        value, unit = getattr(t, "value", t), getattr(t, "unit", "")
        out[name] = f"{value} {unit}".strip()
    return out


def _bears_on(h: Hypothesis, e: EvidenceObject, tests: dict[str, Any]) -> bool:
    """Does this test's evidence, in this direction, speak to h's typology? (b3's registry)

    A T05 refutation ("billing looks like the population") refutes threshold structuring, not a
    conflict of interest; supports count for the test's `typologies`, refutes for its `refutes`.
    """
    test = tests.get(e.test_id)
    if test is None:
        return True
    typ = str(h.typology)
    supports = {str(t) for t in getattr(test, "typologies", ())}
    refutes = {str(t) for t in getattr(test, "refutes", ())}
    if e.direction == Direction.supports:
        return typ in supports
    if e.direction == Direction.refutes:
        return typ in refutes
    return typ in supports | refutes


def _evidence_for(
    h: Hypothesis, evidence: list[EvidenceObject], tests: dict[str, Any] | None = None
) -> list[EvidenceObject]:
    """Evidence tagged with h, or from one of h's tests on one of h's subjects/objects that
    bears on h's typology in its direction."""
    out = []
    for e in evidence:
        if h.hypothesis_id in e.hypothesis_ids:
            out.append(e)
            continue
        if e.test_id not in h.tests_to_run and e.test_id != "T16":
            continue
        if not _bears_on(h, e, tests or {}):
            continue
        objs, subs = set(e.object_ids), set(e.subject_ids)
        if not objs and not subs:
            continue
        if objs and h.objects and not objs & set(h.objects):
            continue
        if subs and h.subjects and not subs & set(h.subjects):
            continue
        out.append(e)
    return out


def _next_id(evidence: list[EvidenceObject]) -> int:
    nums = [int(e.evidence_id[1:]) for e in evidence if e.evidence_id[1:].isdigit()]
    return max(nums, default=0) + 1


def _metrics_from_log(log_path: Path) -> dict[str, Any]:
    m = {
        "crustdata_calls": 0,
        "cache_hits": 0,
        "credits_used": 0.0,
        "model_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "rule_tests": 0,
        "log_records": 0,
    }
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        m["log_records"] += 1
        kind, detail, out = (
            rec.get("action_type"),
            rec.get("action_detail") or {},
            rec.get("outcome") or {},
        )
        if rec.get("record_phase") == "pre_execution":
            if kind == "tool_call":
                m["crustdata_calls"] += 1
                m["cache_hits"] += bool(detail.get("cache_hit"))
            elif kind == "model_call":
                m["model_calls"] += 1
            elif kind == "rule_test":
                m["rule_tests"] += 1
        else:
            m["credits_used"] = round(m["credits_used"] + float(out.get("credits_used") or 0), 2)
            m["tokens_in"] += int(out.get("tokens_in") or 0)
            m["tokens_out"] += int(out.get("tokens_out") or 0)
            m["cache_hits"] += bool(out.get("cache_hit"))
    return m


def run(
    tip_path: str | Path,
    ledger_path: str | Path,
    vendors_path: str | Path,
    staff_path: str | Path,
    out_dir: str | Path,
    offline: bool = False,
    redact: bool = False,
    case_id: str | None = None,
    company_name: str | None = None,
    progress: Callable[[str, str], None] | None = None,
) -> CaseFile:
    load_dotenv(override=True)  # .env wins over stale shell keys, for the CLI and the eval harness
    t0 = time.perf_counter()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    case_id = case_id or out.resolve().name
    stage_seconds: dict[str, float] = {}
    STUBBED.clear()

    info: dict[str, str] = {}

    def stage(name: str, msg: str) -> None:
        info[name] = msg  # shown when the stage finishes

    class _timed:
        def __init__(self, name: str) -> None:
            self.name = name

        def __enter__(self) -> None:
            self.t = time.perf_counter()
            if progress:
                progress(self.name, "start")

        def __exit__(self, *exc: object) -> None:
            stage_seconds[self.name] = secs = round(time.perf_counter() - self.t, 3)
            if progress and exc[0] is None:
                progress(self.name, f"{info.get(self.name, 'done')}  [dim]{secs:.2f}s[/]")

    # 0. audit log first, then hash the inputs
    log_path = out / "log.jsonl"
    for old in (log_path, out / "root.txt"):  # a new run starts a new chain
        old.unlink(missing_ok=True)
    audit = impl("audit", "AuditLog")(log_path)
    _set_agents_audit(audit)
    payload_store.clear()  # quote payloads are per run; the eval harness runs in one process
    try:
        inputs = {
            "tip": tip_path,
            "ledger": ledger_path,
            "vendors": vendors_path,
            "staff": staff_path,
        }
        for role, p in inputs.items():
            p = Path(p)
            sha, size = _sha256_file(p)
            rid = audit.pre("file_read", {"name": role, "path": p.as_posix(), "args_sha256": sha})
            audit.post(rid, {"status": "ok", "result_sha256": sha, "bytes": size})

        # 1. ingest
        with _timed("ingest"):
            tip = impl("ingest", "load_tip")(tip_path)
            rows, ledger_notes = impl("ingest", "load_ledger")(ledger_path)
            vendors, vendor_notes = impl("ingest", "load_vendors")(vendors_path)
            staff, staff_notes = impl("ingest", "load_staff")(staff_path)
            rows = impl("ingest", "link_ledger")(rows, vendors, staff)
            stats = impl("stats", "ledger_stats")(rows)
            data_quality = [*ledger_notes, *vendor_notes, *staff_notes]
            stage("ingest", f"{len(rows)} rows, {len(vendors)} vendors, {len(staff)} staff")

        # 2. propose
        with _timed("propose"):
            hypotheses: list[Hypothesis] = impl("propose", "propose")(
                tip, stats, vendors, staff, [t.value for t in Typology]
            )
            stage("propose", f"{len(hypotheses)} hypotheses")

        # 3. resolve
        with _timed("resolve"):
            client = impl("crustdata", "CrustdataClient")(
                api_key=os.environ.get("CRUSTDATA_API_KEY"),
                cache_dir=Path(".cache/crustdata"),
                offline=offline,
                audit=audit,
            )
            judge = impl("match", "judge_candidates")
            vendors = impl("resolve", "resolve_vendors")(vendors, client, judge=judge)
            resolve_staff = impl("resolve", "resolve_staff")
            if company_name and "company_name" in inspect.signature(resolve_staff).parameters:
                staff = resolve_staff(staff, client, judge=judge, company_name=company_name)
            else:  # b2 infers the employer from the staff list
                staff = resolve_staff(staff, client, judge=judge)
            n_res = sum(x.resolution.status == "resolved" for x in [*vendors, *staff])
            stage("resolve", f"{n_res}/{len(vendors) + len(staff)} entities resolved")

        # 4. test: rules + graph
        with _timed("test"):
            G = impl("graph", "build")(rows, vendors, staff)
            build_context = impl("rules_context", "build_context")
            ctx = (
                build_context(rows, vendors, staff, graph=G, audit=audit, hypotheses=hypotheses)
                if "hypotheses" in inspect.signature(build_context).parameters
                else build_context(rows, vendors, staff, graph=G, audit=audit)
            )
            test_ids = sorted({t for h in hypotheses for t in h.tests_to_run})
            evidence: list[EvidenceObject] = list(impl("rules", "run_tests")(test_ids, ctx))
            path_evidence = impl("graph", "path_evidence")
            for h in hypotheses:
                for s in h.subjects:
                    for v in h.objects:
                        rid = audit.pre("rule_test", {"name": "T16", "args": [s, v]})
                        e = path_evidence(G, s, v)
                        ids: list[str] = []
                        if e is not None:
                            e = e.model_copy(
                                update={
                                    "evidence_id": f"E{_next_id(evidence)}",
                                    "log_record_id": rid,
                                }
                            )
                            evidence.append(e)
                            ids = [e.evidence_id]
                        audit.post(rid, {"status": "ok", "evidence_ids": ids})
            centrality = impl("graph", "centrality")(G)
            hypotheses = impl("rank", "rerank")(hypotheses, evidence, centrality)
            # tag evidence with the hypotheses it bears on
            tests = impl("registry", "TESTS")
            linked = {h.hypothesis_id: _evidence_for(h, evidence, tests) for h in hypotheses}
            tags: dict[str, list[str]] = {}
            for hid, evs in linked.items():
                for e in evs:
                    tags.setdefault(e.evidence_id, []).append(hid)
            evidence = [
                e.model_copy(
                    update={
                        "hypothesis_ids": sorted({*e.hypothesis_ids, *tags.get(e.evidence_id, [])})
                    }
                )
                for e in evidence
            ]
            by_id = {e.evidence_id: e for e in evidence}
            linked = {hid: [by_id[e.evidence_id] for e in evs] for hid, evs in linked.items()}
            n_sup = sum(e.direction == Direction.supports for e in evidence)
            n_ref = sum(e.direction == Direction.refutes for e in evidence)
            stage(
                "test",
                f"{len(test_ids)} tests, {len(evidence)} evidence "
                f"({n_sup} support, {n_ref} refute)",
            )

        # 5. critique and gate
        with _timed("critique_gate"):
            critique = impl("critique", "critique")
            model_errors = _model_errors()

            def critique_or_none(h: Hypothesis) -> Any:
                # one refusal or bad output must not sink the run; gate.decide handles None
                try:
                    return critique(h, linked[h.hypothesis_id])
                except model_errors:
                    return None

            with ThreadPoolExecutor(max_workers=4) as pool:
                critics = list(pool.map(critique_or_none, hypotheses))
            resolutions = {v.vendor_id: v.resolution for v in vendors} | {
                s.staff_id: s.resolution for s in staff
            }
            ledger_amounts: dict[str, Decimal] = {r.row_id: r.amount for r in rows}
            decide = impl("gate", "decide")
            findings: list[Finding] = [
                decide(h, linked[h.hypothesis_id], c, resolutions, ledger_amounts=ledger_amounts)
                for h, c in zip(hypotheses, critics, strict=True)
            ]
            findings.sort(key=lambda f: VERDICT_ORDER[f.verdict])
            counts = {v.value: sum(f.verdict == v for f in findings) for v in Verdict}
            stage("critique_gate", ", ".join(f"{n} {v}" for v, n in counts.items()))

        # 6. write, check, render
        with _timed("write"):
            thresholds = impl("thresholds", "THRESHOLDS")
            metrics = _metrics_from_log(log_path) | {
                "wall_seconds": round(time.perf_counter() - t0, 2),
                "stage_seconds": stage_seconds,
                "stubbed": sorted(STUBBED),
            }
            meta = {
                "case_id": case_id,
                "company_name": company_name or "Audited company",
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "tip": tip,
                "hypotheses": hypotheses,
                "ledger_stats": stats,
                "scope": [
                    f"Ledger: {len(rows)} rows"
                    + (
                        f", {min(r.date for r in rows)} to {max(r.date for r in rows)}"
                        if rows
                        else ""
                    ),
                    f"Vendor master: {len(vendors)} vendors; staff list: {len(staff)} staff",
                    "External sources: Crustdata company and person records"
                    + (" (offline cache)" if offline else ""),
                ],
                "approach": [
                    "Ingest and normalise inputs",
                    f"Propose {len(hypotheses)} hypotheses from a fixed ACFE typology menu",
                    "Resolve vendors and staff against Crustdata",
                    f"Run deterministic tests: {', '.join(test_ids) or 'none'}; graph paths (T16)",
                    "Fresh-context critique; deterministic gate decides each verdict",
                ],
                "data_quality": data_quality,
                "assumptions": _assumptions(thresholds),
                "metrics": metrics,
                "merkle_root": audit.merkle_root(),
                "verify_command": f"python verify.py {log_path.as_posix()}",
            }
            case: CaseFile = impl("write", "write_case_file")(findings, evidence, meta)
            case = case.model_copy(update={"hypotheses": hypotheses})

        with _timed("render"):
            # every evidence object (cited or not) and the raw quote payloads hold unredacted
            # names, so under --redact they go next to the redaction map, not into `out`
            private = out.resolve().parent / ".private" / out.resolve().name if redact else out
            private.mkdir(parents=True, exist_ok=True)
            if redact:  # leftovers from an earlier unredacted run into the same dir
                (out / "evidence_all.json").unlink(missing_ok=True)
                shutil.rmtree(out / "payloads", ignore_errors=True)
            (private / "evidence_all.json").write_text(
                json.dumps([e.model_dump(mode="json") for e in evidence], indent=2),
                encoding="utf-8",
            )
            payload_store.dump(private / "payloads")
            render = impl("render", "render")
            errors = impl("check", "check_citations")(case, payload_store)
            if errors:
                raise CitationError(errors)
            # the case file's root covers every record up to here; root.txt (seal) covers all
            case.metrics.update(_metrics_from_log(log_path))
            case.metrics |= {
                "wall_seconds": round(time.perf_counter() - t0, 2),
                "stage_seconds": stage_seconds,
                "stubbed": sorted(STUBBED),
                "log_records": audit.seq,
            }
            case = case.model_copy(update={"merkle_root": audit.merkle_root()})
            rid = audit.pre("render", {"name": "case_file", "redact": redact})
            kwargs: dict[str, Any] = {
                "evidence_index": payload_store,
                "people": _people(staff, vendors),
            }
            if "keep" in inspect.signature(render).parameters:
                kwargs["keep"] = _vendor_names(vendors)  # vendors are never redacted
            try:
                path = render(case, out, redact=redact, **kwargs)
            except BaseException as e:  # a3's CitationError is a SystemExit
                audit.post(rid, {"status": "error", "error": f"{type(e).__name__}: {e}"})
                raise
            outcome: dict[str, Any] = {
                "status": "ok",
                "result_sha256": _sha256_file(Path(path))[0],
            }
            try:  # hash every rendered file, so verify catches edits to any of them
                from casefile.report.render import rendered_hashes

                outcome["files"] = rendered_hashes(out)
            except ImportError:
                pass
            audit.post(rid, outcome)

        case.metrics["wall_seconds"] = round(time.perf_counter() - t0, 2)
        return case
    finally:
        _set_agents_audit(None)
        audit.seal()  # a crashed run still gets root.txt, so tail truncation stays detectable
        audit.close()
