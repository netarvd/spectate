from __future__ import annotations

import typer

from spectate import __version__

app = typer.Typer(
    name="spectate",
    help="A drift detector for AI-generated code.",
    no_args_is_help=True,
    add_completion=False,
)

spec_app = typer.Typer(
    name="spec",
    help="Spec authoring commands.",
    no_args_is_help=True,
)
app.add_typer(spec_app, name="spec")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"spectate {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    pass


@spec_app.command("init")
def spec_init(english: str = typer.Argument(..., help="English description of intent.")) -> None:
    """Draft a Spec from an English description."""
    typer.echo("not implemented yet")


@spec_app.command("transcribe")
def spec_transcribe(path: str = typer.Argument(..., help="Path to existing code.")) -> None:
    """Bootstrap a draft Spec from existing code."""
    typer.echo("not implemented yet")


@app.command("review")
def review(path: str = typer.Argument(".", help="Path to review.")) -> None:
    """Watch + Critique + Bulletin in one command."""
    typer.echo("not implemented yet")


@app.command("accept")
def accept(finding_id: str = typer.Argument(..., help="Finding ID to accept.")) -> None:
    """Accept a Finding into the Spec."""
    typer.echo("not implemented yet")


if __name__ == "__main__":
    app()
