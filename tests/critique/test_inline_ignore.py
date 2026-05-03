from __future__ import annotations

from pathlib import Path

from spectate.critique.diff import critique
from spectate.critique.expected import compile_spec
from spectate.observations.observation import Observation
from spectate.spec.models import Spec


def _spec() -> Spec:
    return Spec.model_validate({"version": 1})


def test_inline_ignore_filters_observation(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("import requests  # spectate: ignore\nimport httpx\n")
    obs = (
        Observation(category="imports", parameter="requests", file=src, line=1),
        Observation(category="imports", parameter="httpx", file=src, line=2),
    )
    findings = critique(obs, compile_spec(_spec()))
    params = {f.observation.parameter for f in findings.added_unspecified if f.observation}
    assert params == {"httpx"}


def test_inline_ignore_missing_file_does_not_crash(tmp_path: Path) -> None:
    src = tmp_path / "ghost.py"
    obs = (Observation(category="imports", parameter="httpx", file=src, line=1),)
    findings = critique(obs, compile_spec(_spec()))
    assert len(findings.added_unspecified) == 1


def test_inline_ignore_only_trailing_comment_counts(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("# spectate: ignore at top of file\nimport httpx\n")
    obs = (Observation(category="imports", parameter="httpx", file=src, line=2),)
    findings = critique(obs, compile_spec(_spec()))
    assert len(findings.added_unspecified) == 1
