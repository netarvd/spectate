from __future__ import annotations

import json as _json
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


EXISTING_SPEC = "version: 1\nnetwork:\n  outbound:\n    allowed:\n      - api.stripe.com\n"


def _write_existing(tmp_path: Path) -> Path:
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text(EXISTING_SPEC)
    return out


def test_spec_update_no_existing_spec_errors(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "update", "anything", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "spec init" in combined


def test_spec_update_requires_english_or_from_plan(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = _write_existing(tmp_path)
    result = runner.invoke(app, ["spec", "update", "--yes", "--output", str(out)])
    assert result.exit_code == 2


def test_spec_update_rejects_both_english_and_from_plan(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = _write_existing(tmp_path)
    plan = tmp_path / "plan.md"
    plan.write_text("change: x\n")
    result = runner.invoke(
        app,
        [
            "spec",
            "update",
            "english",
            "--from-plan",
            str(plan),
            "--yes",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 2


def test_spec_update_applies_addition_yes(tmp_path: Path) -> None:
    delta = "version: 1\nnetwork:\n  outbound:\n    allowed:\n      - api.openai.com\n"
    cli_module._set_llm_client_factory(lambda: _StubClient(output=delta))
    out = _write_existing(tmp_path)
    result = runner.invoke(
        app,
        ["spec", "update", "also call openai", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    new_text = out.read_text()
    assert "api.stripe.com" in new_text
    assert "api.openai.com" in new_text


def test_spec_update_conflict_aborts_and_does_not_write(tmp_path: Path) -> None:
    delta = "version: 1\nnetwork:\n  outbound:\n    forbidden:\n      - api.stripe.com\n"
    cli_module._set_llm_client_factory(lambda: _StubClient(output=delta))
    out = _write_existing(tmp_path)
    original = out.read_text()
    result = runner.invoke(
        app,
        ["spec", "update", "ban stripe", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 1
    assert out.read_text() == original
    combined = result.stdout + (result.stderr or "")
    assert "Conflict" in combined or "conflict" in combined


def test_spec_update_empty_delta_is_noop(tmp_path: Path) -> None:
    delta = "version: 1\n"
    cli_module._set_llm_client_factory(lambda: _StubClient(output=delta))
    out = _write_existing(tmp_path)
    original = out.read_text()
    result = runner.invoke(
        app,
        ["spec", "update", "no actual change", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0
    assert out.read_text() == original
    assert "Nothing to apply" in result.stdout


def test_spec_update_interactive_accepts_addition(tmp_path: Path) -> None:
    delta = "version: 1\nfs:\n  read:\n    allowed:\n      - /etc/config.yaml\n"
    cli_module._set_llm_client_factory(lambda: _StubClient(output=delta))
    out = _write_existing(tmp_path)
    result = runner.invoke(
        app,
        ["spec", "update", "reads config", "--output", str(out)],
        input="y\ny\n",
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "/etc/config.yaml" in out.read_text()


def test_spec_update_interactive_rejects_all(tmp_path: Path) -> None:
    delta = "version: 1\nfs:\n  read:\n    allowed:\n      - /etc/config.yaml\n"
    cli_module._set_llm_client_factory(lambda: _StubClient(output=delta))
    out = _write_existing(tmp_path)
    original = out.read_text()
    result = runner.invoke(
        app,
        ["spec", "update", "reads config", "--output", str(out)],
        input="n\n",
    )
    assert result.exit_code == 0
    assert out.read_text() == original
    assert "No changes accepted" in result.stdout


def test_spec_update_existing_invalid_spec_errors(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_StubClient)
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("version: 1\nbogus: 1\n")
    result = runner.invoke(
        app,
        ["spec", "update", "anything", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 2
    assert "invalid" in (result.stdout + (result.stderr or ""))


def test_spec_update_from_plan(tmp_path: Path) -> None:
    delta = "version: 1\nimports:\n  allowed:\n    - httpx\n"

    captured: dict[str, str] = {}

    class _Capture(_StubClient):
        def __init__(self) -> None:
            super().__init__(output=delta)

        def generate_spec(self, english: str) -> str:
            captured["english"] = english
            return super().generate_spec(english)

    cli_module._set_llm_client_factory(_Capture)
    out = _write_existing(tmp_path)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nUses httpx now.\n")
    result = runner.invoke(
        app,
        [
            "spec",
            "update",
            "--from-plan",
            str(plan),
            "--yes",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "httpx" in out.read_text()
    assert "EXISTING SPEC" in captured["english"]
    assert "CHANGE REQUEST" in captured["english"]
    assert "Uses httpx now" in captured["english"]


def test_spec_update_claude_missing_exits_with_message(tmp_path: Path) -> None:
    cli_module._set_llm_client_factory(_RaisingClient)
    out = _write_existing(tmp_path)
    result = runner.invoke(
        app,
        ["spec", "update", "x", "--yes", "--output", str(out)],
    )
    assert result.exit_code == 2
    assert "Claude Code" in (result.stdout + (result.stderr or ""))


def _stub_observations() -> tuple:
    from spectate.observations.observation import Observation

    return (
        Observation(
            category="network.outbound",
            parameter="api.example.com",
            file=Path("a.py"),
            line=1,
        ),
        Observation(
            category="imports",
            parameter="httpx",
            file=Path("a.py"),
            line=2,
        ),
    )


@pytest.fixture
def _stub_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    agg_module = importlib.import_module("spectate.observations.aggregate")
    monkeypatch.setattr(agg_module, "aggregate", lambda path, **_kw: _stub_observations())


def test_spec_transcribe_path_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    out = tmp_path / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "transcribe", str(missing), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 2
    assert "not found" in (result.stdout + (result.stderr or ""))
    assert not out.exists()


def test_spec_transcribe_writes_on_yes(tmp_path: Path, _stub_aggregate: None) -> None:
    target = tmp_path / "src"
    target.mkdir()
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "transcribe", str(target), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert out.exists()
    body = out.read_text()
    assert "api.example.com" in body
    assert "httpx" in body
    combined = result.stdout + (result.stderr or "")
    assert "DRAFT" in combined


def test_spec_transcribe_default_no_aborts_when_file_exists(
    tmp_path: Path, _stub_aggregate: None
) -> None:
    target = tmp_path / "src"
    target.mkdir()
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "transcribe", str(target), "--output", str(out)],
        input="\n",
    )
    assert result.exit_code == 0, result.stdout
    assert "already exists. Overwrite?" in result.stdout
    assert out.read_text() == "existing: spec\n"


def test_spec_transcribe_yes_overwrites(tmp_path: Path, _stub_aggregate: None) -> None:
    target = tmp_path / "src"
    target.mkdir()
    out = tmp_path / ".spectate" / "spec.yaml"
    out.parent.mkdir(parents=True)
    out.write_text("existing: spec\n")
    result = runner.invoke(
        app,
        ["spec", "transcribe", str(target), "--yes", "--output", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert "api.example.com" in out.read_text()


def test_spec_transcribe_confirm_yes_writes(tmp_path: Path, _stub_aggregate: None) -> None:
    target = tmp_path / "src"
    target.mkdir()
    out = tmp_path / ".spectate" / "spec.yaml"
    result = runner.invoke(
        app,
        ["spec", "transcribe", str(target), "--output", str(out)],
        input="y\n",
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()


REVIEW_SPEC_CLEAN = """version: 1
imports:
  allowed:
    - os
    - sys
"""

REVIEW_SPEC_DRIFT = """version: 1
imports:
  allowed:
    - os
"""

REVIEW_SPEC_REQUIRED = """version: 1
imports:
  required:
    - requests
"""


@pytest.fixture(autouse=True)
def _ensure_watchers_registered() -> None:
    """Other test modules call clear_registry(); ensure ours start populated."""
    import importlib

    from spectate.observations.watcher import all_watchers

    if not all_watchers():
        for name in (
            "spectate.watchers.env",
            "spectate.watchers.fs",
            "spectate.watchers.imports_",
            "spectate.watchers.network",
            "spectate.watchers.sql",
            "spectate.watchers.subprocess_",
        ):
            importlib.reload(importlib.import_module(name))


def _write_sample_project(tmp_path: Path) -> Path:
    src = tmp_path / "proj"
    src.mkdir()
    (src / "code.py").write_text("import os\nimport sys\n")
    return src


def test_review_clean_spec_exits_zero(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_CLEAN)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec)])
    assert result.exit_code == 0, result.stdout + result.stderr
    out = result.stdout.lower()
    assert "within-spec" in out or "no drift" in out


def test_review_drift_exits_one(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_DRIFT)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec)])
    assert result.exit_code == 1
    assert "added-unspecified" in result.stdout or "sys" in result.stdout


def test_review_json_emits_valid_json(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_DRIFT)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--json"])
    assert result.exit_code == 1
    payload = _json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert "findings" in payload


def test_review_markdown_emits_markdown(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_DRIFT)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--markdown"])
    assert result.exit_code == 1
    assert "Spectate" in result.stdout or "<details>" in result.stdout


def test_review_fail_on_added_ignores_missing_required(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    # required + allowed: requests required (missing), os/sys allowed (clean).
    spec.write_text(
        "version: 1\nimports:\n  required:\n    - requests\n  allowed:\n    - os\n    - sys\n"
    )
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--fail-on", "added"])
    assert result.exit_code == 0, result.stdout + result.stderr


def test_review_fail_on_missing_only_with_missing_required_exits_one(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\nimports:\n  required:\n    - requests\n  allowed:\n    - os\n    - sys\n"
    )
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--fail-on", "missing"])
    assert result.exit_code == 1


def test_review_missing_spec_exits_two(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec)])
    assert result.exit_code == 2
    assert "No Spec" in result.stderr or "No Spec" in result.stdout


def test_review_invalid_spec_exits_one(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(INVALID_YAML)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec)])
    assert result.exit_code == 1
    assert "invalid" in (result.stderr + result.stdout).lower()


def test_review_mutually_exclusive_flags_exit_two(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_CLEAN)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--json", "--markdown"])
    assert result.exit_code == 2
    assert "mutually exclusive" in (result.stderr + result.stdout)


def test_review_missing_path_exits_two(tmp_path: Path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_CLEAN)
    result = runner.invoke(app, ["review", str(tmp_path / "nonexistent"), "--spec", str(spec)])
    assert result.exit_code == 2


def test_review_invalid_fail_on_exits_two(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_CLEAN)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--fail-on", "bogus"])
    assert result.exit_code == 2


def test_review_quiet_suppresses_within_spec(tmp_path: Path) -> None:
    proj = _write_sample_project(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(REVIEW_SPEC_CLEAN)
    result = runner.invoke(app, ["review", str(proj), "--spec", str(spec), "--quiet"])
    assert result.exit_code == 0
    assert "within-spec" not in result.stdout


def _write_accept_project(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "code.py").write_text("import os\nimport requests\n")
    spec = tmp_path / "spec.yaml"
    spec.write_text("version: 1\nimports:\n  allowed:\n    - os\n")
    return proj, spec


def _accept_finding_id(proj: Path, spec: Path, parameter: str) -> str:
    from spectate.critique.diff import critique
    from spectate.critique.expected import compile_spec
    from spectate.observations.aggregate import aggregate
    from spectate.spec import validate as _validate

    res = _validate(spec.read_text())
    assert res.spec is not None
    findings = critique(aggregate(proj), compile_spec(res.spec))
    for f in findings.all():
        if f.observation is not None and f.observation.parameter == parameter:
            return f.id
    raise AssertionError(f"no finding for {parameter}")


def test_accept_success_writes_spec(tmp_path: Path) -> None:
    proj, spec = _write_accept_project(tmp_path)
    fid = _accept_finding_id(proj, spec, "requests")
    result = runner.invoke(
        app,
        ["accept", fid, "--spec", str(spec), "--path", str(proj)],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    body = spec.read_text()
    assert "requests" in body
    assert "Accepted" in result.stdout


def test_accept_unknown_finding_exits_one(tmp_path: Path) -> None:
    proj, spec = _write_accept_project(tmp_path)
    result = runner.invoke(
        app,
        ["accept", "F-deadbeef0000", "--spec", str(spec), "--path", str(proj)],
    )
    assert result.exit_code == 1
    assert "not found" in (result.stdout + (result.stderr or ""))


def test_accept_missing_spec_exits_two(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    spec = tmp_path / "nope.yaml"
    result = runner.invoke(
        app,
        ["accept", "F-x", "--spec", str(spec), "--path", str(proj)],
    )
    assert result.exit_code == 2


def test_accept_reason_is_echoed(tmp_path: Path) -> None:
    proj, spec = _write_accept_project(tmp_path)
    fid = _accept_finding_id(proj, spec, "requests")
    result = runner.invoke(
        app,
        [
            "accept",
            fid,
            "--spec",
            str(spec),
            "--path",
            str(proj),
            "--reason",
            "needed for outbound API",
        ],
    )
    assert result.exit_code == 0
    assert "needed for outbound API" in result.stdout


def test_accept_writes_roundtrippable_yaml(tmp_path: Path) -> None:
    from spectate.spec import validate as _validate

    proj, spec = _write_accept_project(tmp_path)
    fid = _accept_finding_id(proj, spec, "requests")
    result = runner.invoke(
        app,
        ["accept", fid, "--spec", str(spec), "--path", str(proj)],
    )
    assert result.exit_code == 0
    res = _validate(spec.read_text())
    assert res.ok
