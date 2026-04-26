from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

import spectate.cli as cli_module
from spectate.cli import app
from spectate.spec import ClaudeNotFoundError

runner = CliRunner()

PLACEHOLDER = "not implemented yet"

VALID_YAML = "version: 1\nnetwork:\n  outbound:\n    allowed:\n      - api.stripe.com\n"
INVALID_YAML = "version: 1\nbogus_key: 1\n"


class _StubClient:
    last_english: str | None = None

    def __init__(self, output: str = VALID_YAML) -> None:
        self._output = output

    def generate_spec(self, english: str) -> str:
        type(self).last_english = english
        return self._output


class _RaisingClient:
    def __init__(self) -> None:
        pass

    def generate_spec(self, english: str) -> str:
        raise ClaudeNotFoundError()


@pytest.fixture(autouse=True)
def _restore_factory() -> Iterator[None]:
    original = cli_module._llm_client_factory
    yield
    cli_module._set_llm_client_factory(original)


def test_help_succeeds() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "spectate" in result.stdout.lower()


def test_spec_init_writes_on_yes(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "init", "fetch weather data", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert out.read_text() == VALID_YAML
    assert _StubClient.last_english == "fetch weather data"


def test_spec_init_confirm_no_does_not_write(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "init", "anything", "--output", str(out)],
        input="n\n",
    )
    assert result.exit_code == 0, result.stdout
    assert not out.exists()
    assert "Aborted" in result.stdout


def test_spec_init_confirm_yes_writes(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "init", "anything", "--output", str(out)],
        input="y\n",
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()


def test_spec_init_existing_file_default_no_aborts(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "init", "anything", "--output", str(out)],
        input="\n",
    )
    assert result.exit_code == 0, result.stdout
    assert "already exists. Overwrite?" in result.stdout
    assert out.read_text() == "existing: spec\n"


def test_spec_init_existing_file_explicit_yes_overwrites(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "init", "anything", "--output", str(out)],
        input="y\n",
    )
    assert result.exit_code == 0, result.stdout
    assert out.read_text() == VALID_YAML


def test_spec_init_existing_file_yes_flag_overwrites(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "init", "anything", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.read_text() == VALID_YAML


def test_spec_init_validation_failure_exits_nonzero(tmp_path: Path) -> None:
    class BadClient(_StubClient):
        def __init__(self) -> None:
            super().__init__(output=INVALID_YAML)

    cli_module._set_llm_client_factory(BadClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "init", "x", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 1
    assert not out.exists()
    assert "failed validation" in (result.stdout + (result.stderr or ""))


def test_spec_init_claude_missing_exits_with_message() -> None:
    cli_module._set_llm_client_factory(_RaisingClient)
    result = runner.invoke(app, ["spec", "init", "x", "--yes"])
    assert result.exit_code == 2
    assert "Claude Code" in (result.stdout + (result.stderr or ""))


PLAN_TEXT = "# Plan\n\nThe service must call api.stripe.com.\n"


def test_spec_from_plan_writes_on_yes(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN_TEXT)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "from-plan", str(plan), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert out.read_text() == VALID_YAML
    assert _StubClient.last_english == PLAN_TEXT


def test_spec_from_plan_existing_file_default_no_aborts(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN_TEXT)
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "from-plan", str(plan), "--output", str(out)],
        input="\n",
    )
    assert result.exit_code == 0, result.stdout
    assert "already exists. Overwrite?" in result.stdout
    assert out.read_text() == "existing: spec\n"


def test_spec_from_plan_existing_file_yes_flag_overwrites(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN_TEXT)
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "from-plan", str(plan), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.read_text() == VALID_YAML


def test_spec_from_plan_validation_failure_exits_nonzero(tmp_path: Path) -> None:
    class BadClient(_StubClient):
        def __init__(self) -> None:
            super().__init__(output=INVALID_YAML)

    cli_module._set_llm_client_factory(BadClient)
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN_TEXT)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "from-plan", str(plan), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 1
    assert not out.exists()
    assert "failed validation" in (result.stdout + (result.stderr or ""))


def test_spec_from_plan_missing_file_exits_2(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    plan = tmp_path / "does-not-exist.md"
    out = tmp_path / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "from-plan", str(plan), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 2
    assert "not found" in (result.stdout + (result.stderr or ""))
    assert not out.exists()


def test_spec_from_plan_empty_file_exits_2(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    plan = tmp_path / "empty.md"
    plan.write_text("   \n\n")
    out = tmp_path / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "from-plan", str(plan), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 2
    assert "empty" in (result.stdout + (result.stderr or ""))
    assert not out.exists()


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
