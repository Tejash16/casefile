"""Casefile command line (skeleton; full commands land with pipeline.py)."""

import typer

app = typer.Typer(help="Casefile: autonomous forensic-audit agent.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the package version."""
    from casefile import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
