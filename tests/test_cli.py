from __future__ import annotations

from typer.testing import CliRunner

from spectate.cli import app

runner = CliRunner()

PLACEHOLDER = "not implemented yet"


def test_help_succeeds() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "spectate" in result.stdout.lower()


def test_spec_init() -> None:
    result = runner.invoke(app, ["spec", "init", "fetch weather data"])
    assert result.exit_code == 0
    assert PLACEHOLDER in result.stdout


def test_spec_transcribe() -> None:
    result = runner.invoke(app, ["spec", "transcribe", "./some/path"])
    assert result.exit_code == 0
    assert PLACEHOLDER in result.stdout


def test_review_with_path() -> None:
    result = runner.invoke(app, ["review", "./src"])
    assert result.exit_code == 0
    assert PLACEHOLDER in result.stdout


def test_review_default_path() -> None:
    result = runner.invoke(app, ["review"])
    assert result.exit_code == 0
    assert PLACEHOLDER in result.stdout


def test_accept() -> None:
    result = runner.invoke(app, ["accept", "F-001"])
    assert result.exit_code == 0
    assert PLACEHOLDER in result.stdout
