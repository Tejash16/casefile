"""Casefile command line: investigate, verify, credits.

Exit codes: 0 ok, 1 error, 2 citation check failed, 3 log verification failed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

app = typer.Typer(help="Casefile: autonomous forensic-audit agent.", no_args_is_help=True)
console = Console(highlight=False)

STAGE_LABELS = {
    "ingest": "1 ingest",
    "propose": "2 propose",
    "resolve": "3 resolve",
    "test": "4 test",
    "critique_gate": "5 critique+gate",
    "write": "6 write",
    "render": "6 render",
}


def _progress(start: float):
    def show(stage: str, msg: str) -> None:
        if msg == "start":
            return
        label = STAGE_LABELS.get(stage, stage)
        console.print(
            f"[dim]{time.perf_counter() - start:6.1f}s[/] [bold cyan]{label:<16}[/] {msg}"
        )

    return show


@app.command()
def investigate(
    tip: Path = typer.Option(..., exists=True, dir_okay=False, help="Insider tip, plain text"),
    ledger: Path = typer.Option(..., exists=True, dir_okay=False, help="Ledger CSV"),
    vendors: Path = typer.Option(..., exists=True, dir_okay=False, help="Vendor master CSV"),
    staff: Path = typer.Option(..., exists=True, dir_okay=False, help="Staff list CSV"),
    out: Path = typer.Option(..., help="Output directory for the case file and log"),
    offline: bool = typer.Option(False, help="Read Crustdata only from the disk cache"),
    redact: bool = typer.Option(False, help="Replace person names with initials in the output"),
    case_id: str | None = typer.Option(None, help="Case id (default: output directory name)"),
    company: str | None = typer.Option(
        None, help="Audited company (title block; employer for staff search). Default: inferred"
    ),
) -> None:
    """Run the six stages on one tip and write the case file."""
    load_dotenv(override=True)  # .env wins over stale shell keys
    from casefile import pipeline

    start = time.perf_counter()
    console.print(
        f"[bold]Casefile[/] investigating [cyan]{tip}[/] -> [cyan]{out}[/]"
        + (" [yellow](offline)[/]" if offline else "")
    )
    try:
        case = pipeline.run(
            tip,
            ledger,
            vendors,
            staff,
            out,
            offline=offline,
            redact=redact,
            case_id=case_id,
            company_name=company,
            progress=_progress(start),
        )
    except pipeline.CitationError as e:
        console.print(f"[bold red]RENDER REFUSED[/] {len(e.errors)} citation error(s):")
        for err in e.errors:
            console.print(f"  [red]-[/] {err}")
        raise typer.Exit(2) from None

    from casefile.report.metrics import print_metrics

    console.print()
    print_metrics(case, console)
    if case.metrics.get("stubbed"):
        console.print(f"[yellow]stubbed stages:[/] {', '.join(case.metrics['stubbed'])}")
    console.print(f"[bold green]Case file[/] {out / 'case_file.md'}")


@app.command()
def verify(
    log: Path = typer.Argument(..., exists=True, dir_okay=False, help="log.jsonl to verify"),
    root: str | None = typer.Option(None, help="Expected Merkle root (default: root.txt)"),
) -> None:
    """Recompute every record hash, the chain and the Merkle root."""
    try:
        from casefile.audit.verify import main as verify_main
    except ImportError:
        console.print("[red]casefile.audit.verify is not on this branch yet[/]")
        raise typer.Exit(1) from None
    code = verify_main([str(log)] + (["--root", root] if root else []))
    raise typer.Exit(3 if code else 0)


@app.command()
def credits() -> None:
    """Show remaining Crustdata credits."""
    load_dotenv(override=True)  # .env wins over stale shell keys
    from casefile.pipeline import impl

    client = impl("crustdata", "CrustdataClient")(
        api_key=os.environ.get("CRUSTDATA_API_KEY"), cache_dir=Path(".cache/crustdata")
    )
    console.print_json(json.dumps(client.credits(), default=str))


if __name__ == "__main__":
    app()
