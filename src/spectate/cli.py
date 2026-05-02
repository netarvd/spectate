from __future__ import annotations

from pathlib import Path

import typer

from spectate import __version__
from spectate.spec import (
    ClaudeNotFoundError,
    LLMClient,
    SkillClient,
    SkillInvocationError,
    validate,
)

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

DEFAULT_SPEC_PATH = Path(".spectate/spec.yaml")

_OUTPUT_OPTION = typer.Option(
    DEFAULT_SPEC_PATH,
    "--output",
    "-o",
    help="Output path for the Spec YAML.",
)
_YES_OPTION = typer.Option(
    False,
    "--yes",
    "-y",
    help="Skip confirmation and write the Spec immediately.",
)
_PLAN_PATH_ARGUMENT = typer.Argument(..., help="Path to a plan markdown file.")

_llm_client_factory: type[LLMClient] = SkillClient


def _set_llm_client_factory(factory: type[LLMClient]) -> None:
    """Test seam: override the LLM client constructor."""
    global _llm_client_factory
    _llm_client_factory = factory


def _build_client(skill: str) -> LLMClient:
    factory = _llm_client_factory
    if factory is SkillClient:
        return SkillClient(skill=skill)
    return factory()


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
def spec_init(
    english: str = typer.Argument(..., help="English description of intent."),
    yes: bool = _YES_OPTION,
    output: Path = _OUTPUT_OPTION,
) -> None:
    """Draft a Spec from an English description."""
    client = _build_client("spec-init")
    try:
        yaml_text = client.generate_spec(english)
    except ClaudeNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except SkillInvocationError as exc:
        typer.echo(f"spec-init skill failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    result = validate(yaml_text)
    if not result.ok:
        typer.echo("Generated Spec failed validation:", err=True)
        for err in result.errors:
            line = f"  {err.path}: {err.message}"
            if err.suggestion:
                line += f"  ({err.suggestion})"
            typer.echo(line, err=True)
        typer.echo("\n--- raw skill output ---", err=True)
        typer.echo(yaml_text, err=True)
        raise typer.Exit(code=1)

    typer.echo("Generated Spec:")
    typer.echo(yaml_text.rstrip())

    exists = output.exists()
    if not yes:
        if exists:
            prompt = f"\n{output} already exists. Overwrite?"
            confirmed = typer.confirm(prompt, default=False)
        else:
            confirmed = typer.confirm(f"\nWrite to {output}?", default=True)
        if not confirmed:
            typer.echo("Aborted; no file written.")
            raise typer.Exit(code=0)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml_text)
    typer.echo(f"Wrote {output}")


@spec_app.command("from-plan")
def spec_from_plan(
    path: Path = _PLAN_PATH_ARGUMENT,
    yes: bool = _YES_OPTION,
    output: Path = _OUTPUT_OPTION,
) -> None:
    """Draft a Spec from an existing plan document."""
    if not path.exists():
        typer.echo(f"Plan file not found: {path}", err=True)
        raise typer.Exit(code=2)
    plan_text = path.read_text()
    if not plan_text.strip():
        typer.echo(f"Plan file is empty: {path}", err=True)
        raise typer.Exit(code=2)

    client = _build_client("spec-from-plan")
    try:
        yaml_text = client.generate_spec(plan_text)
    except ClaudeNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except SkillInvocationError as exc:
        typer.echo(f"spec-from-plan skill failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    result = validate(yaml_text)
    if not result.ok:
        typer.echo("Generated Spec failed validation:", err=True)
        for err in result.errors:
            line = f"  {err.path}: {err.message}"
            if err.suggestion:
                line += f"  ({err.suggestion})"
            typer.echo(line, err=True)
        typer.echo("\n--- raw skill output ---", err=True)
        typer.echo(yaml_text, err=True)
        raise typer.Exit(code=1)

    typer.echo("Generated Spec:")
    typer.echo(yaml_text.rstrip())

    exists = output.exists()
    if not yes:
        if exists:
            prompt = f"\n{output} already exists. Overwrite?"
            confirmed = typer.confirm(prompt, default=False)
        else:
            confirmed = typer.confirm(f"\nWrite to {output}?", default=True)
        if not confirmed:
            typer.echo("Aborted; no file written.")
            raise typer.Exit(code=0)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml_text)
    typer.echo(f"Wrote {output}")


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
