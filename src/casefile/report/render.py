"""Render a CaseFile to Markdown in the ACFE report order.

The template only lays out text that is already in the CaseFile; nothing is generated here.
`render` refuses (CitationError, exit code 2) unless `check_citations` returns no errors.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from casefile.report.check import check_citations
from casefile.report.redact import NoRedaction, Redactor
from casefile.schemas import CaseFile, EvidenceObject, Finding, Hypothesis, Sentence, Verdict

TEMPLATES = Path(__file__).parent / "templates"
VERDICT_ORDER = {Verdict.Substantiated: 0, Verdict.Unfounded: 1, Verdict.Unsubstantiated: 2}
METRIC_LABELS = {
    "wall_seconds": "Wall time (s)",
    "crustdata_calls": "Crustdata calls",
    "credits_used": "Crustdata credits used",
    "cache_hits": "Crustdata cache hits",
    "model_calls": "Model calls",
    "tokens_in": "Model tokens in",
    "tokens_out": "Model tokens out",
    "log_records": "Audit log records",
    "rule_tests": "Rule tests run",
    "cache_read": "Model tokens read from prompt cache",
}


class CitationError(SystemExit):
    """Raised by render when the citation check fails; exits the process with code 2."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(2)
        self.errors = errors

    def __str__(self) -> str:
        return "case file not rendered, citation check failed:\n" + "\n".join(
            f"  - {e}" for e in self.errors
        )


def inr(amount: Decimal | float | int | None) -> str:
    """Indian digit grouping: INR 1,23,45,678.50."""
    if amount is None:
        return "not quantified"
    q = Decimal(str(amount)).quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    whole, frac = f"{abs(q):.2f}".split(".")
    if len(whole) > 3:
        head, groups = whole[:-3], [whole[-3:]]
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups)
    return f"INR {sign}{whole}" + ("" if frac == "00" else f".{frac}")


def anchor(evidence_id: str) -> str:
    return evidence_id.lower()


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _threshold_meta() -> dict[str, Any]:
    try:
        from casefile.rules.config import THRESHOLDS  # b3; optional until it lands
    except Exception:  # noqa: BLE001 - any import failure just means no extra columns
        return {}
    return dict(THRESHOLDS)


def _test_names() -> dict[str, str]:
    try:
        from casefile.rules.registry import TESTS  # b3; optional until it lands
    except Exception:  # noqa: BLE001
        return {}
    return {tid: getattr(t, "name", "") for tid, t in TESTS.items()}


def _hypotheses(case: CaseFile, hypotheses: Iterable[Hypothesis] | None) -> dict[str, Hypothesis]:
    hyps = list(hypotheses or getattr(case, "hypotheses", None) or [])
    return {h.hypothesis_id: h for h in hyps}


def build_view(
    case: CaseFile, hyps: Mapping[str, Hypothesis], r: Redactor | NoRedaction
) -> dict[str, Any]:
    """Everything the templates print, already redacted and formatted."""
    ex_by_id = {e.evidence_id: e for e in case.exhibits}
    tests = _test_names()

    def sentence(s: Sentence) -> str:
        links = " ".join(f"[[{e}]](#{anchor(e)})" for e in s.evidence_ids)
        return f"{r(s.text)} {links}".rstrip()

    def ev_ref(eid: str) -> dict[str, str]:
        ev = ex_by_id.get(eid)
        return {"id": eid, "anchor": anchor(eid), "summary": r(ev.summary) if ev else ""}

    def finding(f: Finding) -> dict[str, Any]:
        h = hyps.get(f.hypothesis_id)
        return {
            "id": f.hypothesis_id,
            "typology": h.typology.value if h else "",
            "statement": r(h.statement) if h else "",
            "subjects": h.subjects if h else [],
            "objects": h.objects if h else [],
            "origin": h.origin.value if h else "",
            "verdict": f.verdict.value,
            "verdict_by": f.verdict_by.value,
            "model_verdict": f.model_verdict.value if f.model_verdict else None,
            "confidence": f"{f.confidence:.2f}",
            "amount": inr(f.amount_at_issue_inr),
            "rationale": [sentence(s) for s in f.rationale],
            "supporting": [ev_ref(e) for e in f.supporting_evidence],
            "counter": [ev_ref(e) for e in f.counter_evidence],
            "data_gaps": [r(g) for g in f.data_gaps],
        }

    def exhibit(e: EvidenceObject) -> dict[str, Any]:
        quote = r(e.quote) or ""
        fence = "````" if "```" in quote else "```"
        return {
            "id": e.evidence_id,
            "anchor": anchor(e.evidence_id),
            "test_id": e.test_id,
            "test_name": tests.get(e.test_id, ""),
            "direction": e.direction.value,
            "strength": f"{e.strength:.2f}",
            "summary": r(e.summary),
            "quote": quote,
            "fence": fence,
            "source_kind": e.source.kind.value,
            "refs": e.source.refs,
            "as_of": e.source.as_of,
            "sha256": e.sha256,
            "log_record_id": e.log_record_id,
            "hypotheses": e.hypothesis_ids,
            "subjects": e.subject_ids,
            "objects": e.object_ids,
        }

    meta = _threshold_meta()
    assumptions = []
    for name, value in case.assumptions.items():
        t = meta.get(name)
        unit = getattr(t, "unit", "") or ""
        assumptions.append(
            {
                "name": _cell(name),
                "value": _cell(f"{value} {unit}".strip()),
                "rationale": _cell(getattr(t, "rationale", "") or ""),
                "source": _cell(getattr(t, "source_url", "") or ""),
            }
        )

    metrics = [
        {"label": _cell(METRIC_LABELS.get(k, k)), "value": _cell(v)}
        for k, v in case.metrics.items()
        if not isinstance(v, (dict, list))
    ]
    findings = sorted(case.findings, key=lambda f: VERDICT_ORDER.get(f.verdict, 9))
    log_records = case.metrics.get("log_records")
    return {
        "case_id": case.case_id,
        "company": r(case.company_name),
        "generated_at": case.generated_at,
        "merkle_root": case.merkle_root,
        "log_records": log_records,
        "verify_command": case.verify_command,
        "predication": sentence(case.predication),
        "executive_summary": [sentence(s) for s in case.executive_summary],
        "scope": [r(s) for s in case.scope],
        "approach": [r(s) for s in case.approach],
        "findings": [finding(f) for f in findings],
        "counts": {v.value: sum(1 for f in findings if f.verdict == v) for v in Verdict},
        "data_quality": [r(s) for s in case.data_quality],
        "assumptions": assumptions,
        "metrics": metrics,
        "exhibits": [exhibit(e) for e in case.exhibits],
        "redacted": not isinstance(r, NoRedaction),
    }


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def _findings_json(case: CaseFile, hyps: Mapping[str, Hypothesis], r: Any) -> list[dict]:
    out = []
    for f in case.findings:
        h = hyps.get(f.hypothesis_id)
        d = json.loads(f.model_dump_json())
        d["rationale"] = [{**s, "text": r(s["text"])} for s in d["rationale"]]
        d["data_gaps"] = [r(g) for g in d["data_gaps"]]
        d.update(
            typology=h.typology.value if h else None,
            subjects=h.subjects if h else [],
            objects=h.objects if h else [],
            statement=r(h.statement) if h else None,
        )
        out.append(d)
    return out


def _evidence_json(case: CaseFile, r: Any) -> list[dict]:
    out = []
    for e in case.exhibits:
        d = json.loads(e.model_dump_json())
        d["quote"], d["summary"] = r(d["quote"]), r(d["summary"])
        out.append(d)
    return out


def render(
    case: CaseFile,
    out_dir: str | Path,
    redact: bool = False,
    *,
    hypotheses: Iterable[Hypothesis] | None = None,
    evidence_index: Mapping[str, bytes] | None = None,
    people: Iterable[str] = (),
    require_payloads: bool = True,
    redaction_map_path: str | Path | None = None,
) -> Path:
    """Write case_file.md, exhibits.md, evidence.json, findings.json and root.txt to out_dir.

    `hypotheses` defaults to `case.hypotheses` when the schema carries it. `people` are the
    person names to redact (staff and Crustdata persons). With `redact=True` the name map goes
    to `redaction_map_path`, by default `<out_dir>/../.redaction/<out_dir name>.json`, outside
    the rendered files. Returns the path of case_file.md.
    """
    if evidence_index is None:
        from casefile.audit.payloads import default_store

        evidence_index = default_store
    errors = check_citations(case, evidence_index, require_payloads=require_payloads)
    if errors:
        err = CitationError(errors)
        print(str(err), file=sys.stderr)
        raise err

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hyps = _hypotheses(case, hypotheses)
    r: Redactor | NoRedaction = Redactor(people) if redact else NoRedaction()
    view = build_view(case, hyps, r)
    env = _env()

    case_md = out / "case_file.md"
    case_md.write_text(env.get_template("case_file.md.j2").render(**view), encoding="utf-8")
    (out / "exhibits.md").write_text(
        env.get_template("exhibits.md.j2").render(**view), encoding="utf-8"
    )
    (out / "evidence.json").write_text(
        json.dumps(_evidence_json(case, r), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "findings.json").write_text(
        json.dumps(_findings_json(case, hyps, r), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if case.merkle_root:
        size = view["log_records"]
        (out / "root.txt").write_text(
            f"{case.merkle_root}{f' {size}' if size is not None else ''}\n", encoding="utf-8"
        )
    if redact:
        map_path = (
            Path(redaction_map_path)
            if redaction_map_path
            else out.resolve().parent / ".redaction" / f"{out.resolve().name}.json"
        )
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(json.dumps(r.mapping, indent=2, ensure_ascii=False), encoding="utf-8")
    return case_md
