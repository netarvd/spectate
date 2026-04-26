from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from spectate.spec import SkillClient, validate
from spectate.spec.llm import (
    ClaudeNotFoundError,
    SkillInvocationError,
    _strip_code_fences,
)


def test_strip_code_fences_removes_yaml_fence() -> None:
    text = "```yaml\nversion: 1\nnetwork:\n  outbound:\n    allowed:\n      - a.com\n```\n"
    out = _strip_code_fences(text)
    assert out.startswith("version: 1")
    assert "```" not in out


def test_strip_code_fences_passthrough_when_no_fence() -> None:
    text = "version: 1\nfoo: bar\n"
    assert _strip_code_fences(text) == text


def test_strip_code_fences_passthrough_when_unbalanced() -> None:
    text = "```yaml\nversion: 1\n"
    assert _strip_code_fences(text) == text


def test_generate_spec_invokes_claude_with_expected_args(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill-root"
    skill_dir.mkdir()
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout="version: 1\n", stderr="")

    client = SkillClient(claude_bin="claude-fake", skill_dir=skill_dir)

    with (
        patch("spectate.spec.llm.shutil.which", return_value="/usr/local/bin/claude-fake"),
        patch("spectate.spec.llm.subprocess.run", side_effect=fake_run),
    ):
        out = client.generate_spec("only call api.stripe.com")

    assert out == "version: 1\n"
    argv = captured["argv"]
    assert argv[0] == "/usr/local/bin/claude-fake"
    assert "-p" in argv
    assert "--bare" not in argv
    assert "--add-dir" in argv
    add_dir_idx = argv.index("--add-dir")
    assert argv[add_dir_idx + 1] == str(skill_dir)
    assert "--output-format" in argv
    out_idx = argv.index("--output-format")
    assert argv[out_idx + 1] == "text"
    prompt = argv[argv.index("-p") + 1]
    assert "only call api.stripe.com" in prompt
    assert "spec-init" in prompt


def test_bare_env_opt_in_appends_bare_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPECTATE_CLAUDE_BARE", "1")
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="version: 1\n", stderr="")

    client = SkillClient(claude_bin="claude", skill_dir=tmp_path)
    with (
        patch("spectate.spec.llm.shutil.which", return_value="/usr/bin/claude"),
        patch("spectate.spec.llm.subprocess.run", side_effect=fake_run),
    ):
        client.generate_spec("x")
    assert "--bare" in captured["argv"]


def test_claude_not_on_path_raises_typed_error(tmp_path: Path) -> None:
    client = SkillClient(claude_bin="definitely-not-installed-xyz", skill_dir=tmp_path)
    with (
        patch("spectate.spec.llm.shutil.which", return_value=None),
        pytest.raises(ClaudeNotFoundError) as excinfo,
    ):
        client.generate_spec("anything")
    assert "claude" in str(excinfo.value).lower()


def test_nonzero_exit_raises_skill_invocation_error(tmp_path: Path) -> None:
    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 7, stdout="", stderr="boom")

    client = SkillClient(claude_bin="claude", skill_dir=tmp_path)
    with (
        patch("spectate.spec.llm.shutil.which", return_value="/usr/bin/claude"),
        patch("spectate.spec.llm.subprocess.run", side_effect=fake_run),
        pytest.raises(SkillInvocationError) as excinfo,
    ):
        client.generate_spec("x")
    assert "7" in str(excinfo.value)
    assert "boom" in str(excinfo.value)


def test_default_skill_dir_materializes_dotclaude_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="version: 1\n", stderr="")

    client = SkillClient()
    with (
        patch("spectate.spec.llm.shutil.which", return_value="/usr/bin/claude"),
        patch("spectate.spec.llm.subprocess.run", side_effect=fake_run),
    ):
        client.generate_spec("x")

    add_dir = Path(captured["argv"][captured["argv"].index("--add-dir") + 1])
    skill_md = add_dir / ".claude" / "skills" / "spec-init" / "SKILL.md"
    assert skill_md.exists(), f"expected {skill_md} to be materialized"
    body = skill_md.read_text()
    assert "Spectate Spec" in body


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not on PATH")
def test_integration_generates_valid_spec() -> None:
    client = SkillClient()
    yaml_text = client.generate_spec("This service may only call api.stripe.com over the network.")
    result = validate(yaml_text)
    assert result.ok, f"errors={result.errors}\nraw=\n{yaml_text}"
