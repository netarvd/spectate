from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from typing import Protocol, runtime_checkable

CLAUDE_INSTALL_URL = "https://docs.claude.com/claude-code"
DEFAULT_SKILL_NAME = "spec-init"
SKILL_PACKAGE = "spectate.skills"


class ClaudeNotFoundError(RuntimeError):
    """Raised when the `claude` CLI is not on PATH."""

    def __init__(self) -> None:
        super().__init__(
            "Spectate's `spec init` requires Claude Code (`claude` CLI) on PATH. "
            f"Install it from {CLAUDE_INSTALL_URL} and ensure `claude` is available."
        )


class SkillInvocationError(RuntimeError):
    """Raised when the bundled skill invocation fails."""


@runtime_checkable
class LLMClient(Protocol):
    def generate_spec(self, english: str) -> str: ...


def _materialize_skill_layout(dest_root: Path, skill_name: str) -> Path:
    """Lay out the bundled skill under `<dest_root>/.claude/skills/<skill_name>/`.

    Claude Code auto-loads skills nested under a `--add-dir` target's
    `.claude/skills/` directory. We ship skills as regular package
    subdirectories (`spectate/skills/<skill_name>/`) so hatchling packages
    them cleanly, then materialize the dotfile layout that `claude` expects
    on first use.
    """
    skills_root = dest_root / ".claude" / "skills"
    target = skills_root / skill_name
    if target.exists():
        return dest_root
    skills_root.mkdir(parents=True, exist_ok=True)
    src = resources.files(SKILL_PACKAGE).joinpath(skill_name)
    with resources.as_file(src) as src_path:
        shutil.copytree(src_path, target)
    return dest_root


class SkillClient:
    """Invokes a bundled Spectate Claude Code skill via `claude -p`."""

    def __init__(
        self,
        claude_bin: str = "claude",
        skill_dir: Path | None = None,
        timeout: float | None = 180.0,
        skill: str = DEFAULT_SKILL_NAME,
    ) -> None:
        self._claude_bin = claude_bin
        self._skill_dir_override = skill_dir
        self._timeout = timeout
        self._skill = skill
        self._materialized: Path | None = None

    def _resolve_claude(self) -> str:
        path = shutil.which(self._claude_bin)
        if path is None:
            raise ClaudeNotFoundError()
        return path

    def _resolve_skill_dir(self) -> Path:
        if self._skill_dir_override is not None:
            return self._skill_dir_override
        if self._materialized is None:
            cache_root = Path(tempfile.gettempdir()) / "spectate-skill-cache"
            cache_root.mkdir(parents=True, exist_ok=True)
            self._materialized = _materialize_skill_layout(cache_root, self._skill)
        return self._materialized

    def _build_argv(self, claude_path: str, skill_dir: Path, english: str) -> list[str]:
        prompt = (
            f"Use the {self._skill} skill to convert the following input "
            "into a Spectate Spec YAML. Emit YAML only, no prose, no code fences.\n\n"
            f"{english}"
        )
        argv = [
            claude_path,
            "-p",
            prompt,
            "--add-dir",
            str(skill_dir),
            "--output-format",
            "text",
        ]
        if os.environ.get("SPECTATE_CLAUDE_BARE") == "1":
            argv.append("--bare")
        return argv

    def generate_spec(self, english: str) -> str:
        claude_path = self._resolve_claude()
        skill_dir = self._resolve_skill_dir()
        argv = self._build_argv(claude_path, skill_dir, english)
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ClaudeNotFoundError() from exc
        if result.returncode != 0:
            raise SkillInvocationError(
                f"`claude -p` exited with status {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return _strip_code_fences(result.stdout)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) < 2 or not lines[-1].startswith("```"):
        return text
    return "\n".join(lines[1:-1]) + "\n"
