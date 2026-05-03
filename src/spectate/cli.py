from __future__ import annotations

from pathlib import Path

import typer

from spectate import __version__
from spectate.spec import (
    ClaudeNotFoundError,
    DeltaError,
    LLMClient,
    SkillClient,
    SkillInvocationError,
    apply_diff,
    compute_diff,
    format_diff,
    observations_to_spec,
    parse_yaml,
    spec_to_yaml,
    to_yaml,
    validate,
)
from spectate.spec.update import Change, Diff

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


_UPDATE_ENGLISH_ARG = typer.Argument(None, help="English description of the change to apply.")
_UPDATE_FROM_PLAN_OPTION = typer.Option(
    None,
    "--from-plan",
    help="Path to a plan markdown file describing the change.",
)


def _filter_diff_interactive(diff: Diff) -> Diff:
    """Walk additions and removals, prompting per-change. Returns a new Diff
    containing only the entries the user accepted. Conflicts are not offered
    here — they must be resolved upstream."""
    kept_adds: list[Change] = []
    kept_rems: list[Change] = []
    for change in diff.additions:
        prompt = f"Apply addition {change.where.display()}.{change.slot}: {change.display_value()}?"
        if typer.confirm(prompt, default=True):
            kept_adds.append(change)
    for change in diff.removals:
        prompt = f"Apply removal {change.where.display()}.{change.slot}: {change.display_value()}?"
        if typer.confirm(prompt, default=True):
            kept_rems.append(change)
    return Diff(additions=kept_adds, removals=kept_rems, conflicts=[], noops=diff.noops)


@spec_app.command("update")
def spec_update(
    english: str | None = _UPDATE_ENGLISH_ARG,
    from_plan: Path | None = _UPDATE_FROM_PLAN_OPTION,
    yes: bool = _YES_OPTION,
    output: Path = _OUTPUT_OPTION,
) -> None:
    """Smart upsert against an existing Spec.

    Either pass an English change description as the argument, or use
    ``--from-plan`` to point at a markdown plan describing the change.
    """
    if (english is None) == (from_plan is None):
        typer.echo(
            "Provide either an english description argument OR --from-plan <path>, not both.",
            err=True,
        )
        raise typer.Exit(code=2)

    if not output.exists():
        typer.echo(
            f"No existing Spec at {output}. Run `spectate spec init` first.",
            err=True,
        )
        raise typer.Exit(code=2)

    existing_text = output.read_text()
    existing_result = validate(existing_text)
    if not existing_result.ok:
        typer.echo(f"Existing Spec at {output} is invalid; refusing to update.", err=True)
        for err in existing_result.errors:
            typer.echo(f"  {err.path}: {err.message}", err=True)
        raise typer.Exit(code=2)
    existing_doc = parse_yaml(existing_text)

    if from_plan is not None:
        if not from_plan.exists():
            typer.echo(f"Plan file not found: {from_plan}", err=True)
            raise typer.Exit(code=2)
        change_text = from_plan.read_text()
        if not change_text.strip():
            typer.echo(f"Plan file is empty: {from_plan}", err=True)
            raise typer.Exit(code=2)
    else:
        assert english is not None
        change_text = english

    prompt_body = (
        f"EXISTING SPEC:\n{existing_text.rstrip()}\n\nCHANGE REQUEST:\n{change_text.rstrip()}\n"
    )

    client = _build_client("spec-update")
    try:
        delta_yaml = client.generate_spec(prompt_body)
    except ClaudeNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except SkillInvocationError as exc:
        typer.echo(f"spec-update skill failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        delta_doc = parse_yaml(delta_yaml)
    except DeltaError as exc:
        typer.echo(f"Skill emitted malformed delta YAML: {exc}", err=True)
        typer.echo("\n--- raw skill output ---", err=True)
        typer.echo(delta_yaml, err=True)
        raise typer.Exit(code=1) from exc

    try:
        diff = compute_diff(existing_doc, delta_doc)
    except DeltaError as exc:
        typer.echo(f"Delta is structurally invalid: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Proposed changes:")
    typer.echo(format_diff(diff))

    if diff.conflicts:
        typer.echo(
            "\nConflicts detected — resolve manually by editing the Spec, "
            "then re-run. Refusing to silently overwrite.",
            err=True,
        )
        raise typer.Exit(code=1)

    if diff.empty:
        typer.echo("Nothing to apply.")
        raise typer.Exit(code=0)

    applied = diff if yes else _filter_diff_interactive(diff)

    if applied.empty:
        typer.echo("No changes accepted; Spec untouched.")
        raise typer.Exit(code=0)

    merged = apply_diff(existing_doc, applied)
    merged_yaml = to_yaml(merged)

    result = validate(merged_yaml)
    if not result.ok:
        typer.echo("Merged Spec failed validation:", err=True)
        for err in result.errors:
            line = f"  {err.path}: {err.message}"
            if err.suggestion:
                line += f"  ({err.suggestion})"
            typer.echo(line, err=True)
        typer.echo("\n--- merged YAML ---", err=True)
        typer.echo(merged_yaml, err=True)
        raise typer.Exit(code=1)

    typer.echo("\nMerged Spec:")
    typer.echo(merged_yaml.rstrip())

    if not yes and not typer.confirm(f"\nWrite to {output}?", default=True):
        typer.echo("Aborted; no file written.")
        raise typer.Exit(code=0)

    output.write_text(merged_yaml)
    typer.echo(f"Wrote {output}")


_TRANSCRIBE_PATH_ARGUMENT = typer.Argument(
    ...,
    help="File or directory to scan.",
)


@spec_app.command("transcribe")
def spec_transcribe(
    path: Path = _TRANSCRIBE_PATH_ARGUMENT,
    yes: bool = _YES_OPTION,
    output: Path = _OUTPUT_OPTION,
) -> None:
    """Bootstrap a draft Spec from existing code."""
    if not path.exists():
        typer.echo(f"Path not found: {path}", err=True)
        raise typer.Exit(code=2)

    import spectate.watchers  # noqa: F401  populates the Watcher registry
    from spectate.observations.aggregate import aggregate

    observations = aggregate(path)
    spec = observations_to_spec(observations)
    yaml_text = spec_to_yaml(spec)

    result = validate(yaml_text)
    if not result.ok:
        typer.echo("Generated Spec failed validation:", err=True)
        for err in result.errors:
            line = f"  {err.path}: {err.message}"
            if err.suggestion:
                line += f"  ({err.suggestion})"
            typer.echo(line, err=True)
        typer.echo("\n--- raw transcribed YAML ---", err=True)
        typer.echo(yaml_text, err=True)
        raise typer.Exit(code=1)

    typer.echo("=== DRAFT - review before committing ===", err=True)
    typer.echo("Transcribed Spec:")
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


_DEFAULT_REVIEW_PATH = Path()  # current directory
_REVIEW_PATH_ARGUMENT = typer.Argument(_DEFAULT_REVIEW_PATH, help="Path to review.")
_REVIEW_SPEC_OPTION = typer.Option(
    DEFAULT_SPEC_PATH,
    "--spec",
    "-s",
    help="Path to the Spec YAML.",
)
_REVIEW_JSON_OPTION = typer.Option(False, "--json", help="Emit JSON Bulletin.")
_REVIEW_MARKDOWN_OPTION = typer.Option(
    False, "--markdown", help="Emit markdown Bulletin (PR-comment ready)."
)
_REVIEW_QUIET_OPTION = typer.Option(
    False, "--quiet", "-q", help="Suppress within-spec section (terminal mode)."
)
_REVIEW_FAIL_ON_OPTION = typer.Option(
    "both",
    "--fail-on",
    help="Which buckets cause non-zero exit: added | missing | both.",
)
_REVIEW_NO_COLOR_OPTION = typer.Option(
    False, "--no-color", help="Disable color in terminal output."
)


@app.command("review")
def review(
    path: Path = _REVIEW_PATH_ARGUMENT,
    spec: Path = _REVIEW_SPEC_OPTION,
    json: bool = _REVIEW_JSON_OPTION,
    markdown: bool = _REVIEW_MARKDOWN_OPTION,
    quiet: bool = _REVIEW_QUIET_OPTION,
    fail_on: str = _REVIEW_FAIL_ON_OPTION,
    no_color: bool = _REVIEW_NO_COLOR_OPTION,
) -> None:
    """Watch + Critique + Bulletin in one command."""
    import sys
    from dataclasses import replace

    import spectate.watchers  # noqa: F401  populates the Watcher registry
    from spectate.bulletin import render_json, render_markdown, render_terminal
    from spectate.critique.diff import critique
    from spectate.critique.expected import compile_spec
    from spectate.observations.aggregate import aggregate

    if json and markdown:
        typer.echo("--json and --markdown are mutually exclusive.", err=True)
        raise typer.Exit(code=2)

    if fail_on not in {"added", "missing", "both"}:
        typer.echo(
            f"--fail-on must be one of: added, missing, both (got {fail_on!r}).",
            err=True,
        )
        raise typer.Exit(code=2)

    if not spec.exists():
        typer.echo(
            f"No Spec at {spec}. Run `spectate spec init` first, or pass --spec.",
            err=True,
        )
        raise typer.Exit(code=2)

    spec_text = spec.read_text()
    result = validate(spec_text)
    if not result.ok:
        typer.echo(f"Spec at {spec} is invalid:", err=True)
        for err in result.errors:
            line = f"  {err.path}: {err.message}"
            if err.suggestion:
                line += f"  ({err.suggestion})"
            typer.echo(line, err=True)
        raise typer.Exit(code=1)
    assert result.spec is not None
    spec_obj = result.spec

    if not path.exists():
        typer.echo(f"Path not found: {path}", err=True)
        raise typer.Exit(code=2)

    observations = aggregate(path)
    matchers = compile_spec(spec_obj)
    findings = critique(observations, matchers)

    if json:
        output = render_json(findings)
    elif markdown:
        output = render_markdown(findings)
    else:
        findings_for_render = replace(findings, within_spec=()) if quiet else findings
        color = False if no_color else sys.stdout.isatty()
        output = render_terminal(findings_for_render, color=color)

    typer.echo(output)

    fail_added = fail_on in {"added", "both"}
    fail_missing = fail_on in {"missing", "both"}
    offending = False
    if fail_missing and findings.missing_required:
        offending = True
    if fail_added and (findings.added_forbidden or findings.added_unspecified):
        offending = True
    if offending:
        raise typer.Exit(code=1)


@app.command("accept")
def accept(finding_id: str = typer.Argument(..., help="Finding ID to accept.")) -> None:
    """Accept a Finding into the Spec."""
    typer.echo("not implemented yet")


if __name__ == "__main__":
    app()
