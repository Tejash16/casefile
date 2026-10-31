"""End-of-run terminal summary from CaseFile.metrics and findings (same numbers as section 8)."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from casefile.report.render import METRIC_LABELS, inr
from casefile.schemas import CaseFile, Verdict

VERDICT_STYLE = {
    Verdict.Substantiated: "bold red",
    Verdict.Unfounded: "green",
    Verdict.Unsubstantiated: "yellow",
}


def metrics_table(case: CaseFile) -> Table:
    t = Table(title=f"Casefile {case.case_id}: run metrics", show_header=True)
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    for key, value in case.metrics.items():
        if not isinstance(value, (dict, list)):
            t.add_row(METRIC_LABELS.get(key, key), str(value))
    if case.merkle_root:
        t.add_row("Merkle root", case.merkle_root[:16] + "...")
    return t


def findings_table(case: CaseFile) -> Table:
    hyps = {h.hypothesis_id: h for h in case.hypotheses}
    t = Table(title="Findings", show_header=True)
    for col in ("Id", "Typology", "Subjects", "Objects", "Verdict", "Amount"):
        t.add_column(col)
    for f in case.findings:
        h = hyps.get(f.hypothesis_id)
        t.add_row(
            f.hypothesis_id,
            h.typology.value if h else "",
            ", ".join(h.subjects) if h else "",
            ", ".join(h.objects) if h else "",
            f"[{VERDICT_STYLE.get(f.verdict, '')}]{f.verdict.value}[/]",
            inr(f.amount_at_issue_inr),
        )
    return t


def print_metrics(case: CaseFile, console: Console | None = None) -> None:
    console = console or Console()
    console.print(findings_table(case))
    console.print(metrics_table(case))
    if case.verify_command:
        console.print(f"Verify: [bold]{case.verify_command}[/]")
