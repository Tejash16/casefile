"""Stub for casefile.report (a3): minimal markdown, minimal citation check."""

from __future__ import annotations

import json
from pathlib import Path

from casefile.schemas import CaseFile, EvidenceObject, Sentence


def _cite(s: Sentence) -> str:
    return s.text + "".join(f" [{i}]" for i in s.evidence_ids)


def check_citations(case: CaseFile, evidence_index: dict[str, EvidenceObject]) -> list[str]:
    errors: list[str] = []
    sentences = list(case.executive_summary) + [s for f in case.findings for s in f.rationale]
    for s in sentences:
        if not s.evidence_ids:
            errors.append(f"uncited sentence: {s.text!r}")
        errors += [f"unknown evidence id {i} in {s.text!r}" for i in s.evidence_ids
                   if i not in evidence_index]
    return errors


def render(case: CaseFile, out_dir: str | Path, redact: bool = False) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Case file {case.case_id}: {case.company_name}",
        "",
        f"Generated {case.generated_at}. Merkle root `{case.merkle_root}`. "
        f"Verify: `{case.verify_command}`",
        "",
        "## 1. Predication",
        "",
        case.predication.text,
        "",
        "## 2. Executive summary",
        "",
        *[f"- {_cite(s)}" for s in case.executive_summary],
        "",
        "## 5. Findings",
        "",
    ]
    for f in case.findings:
        lines += [f"### {f.hypothesis_id}: {f.verdict} ({f.verdict_by})", ""]
        lines += [f"- {_cite(s)}" for s in f.rationale] + [""]
    lines += ["## 9. Exhibits", ""]
    lines += [f"- **{e.evidence_id}** {e.test_id} {e.direction} {e.strength}: `{e.quote}`"
              for e in case.exhibits]
    path = out / "case_file.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "findings.json").write_text(
        json.dumps([f.model_dump(mode="json") for f in case.findings], indent=2), encoding="utf-8"
    )
    return path
