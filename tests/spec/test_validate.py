from __future__ import annotations

from pathlib import Path

import pytest

from spectate.spec import Spec, SpecError, ValidationResult, validate

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples" / "specs"
EXAMPLE_FILES = sorted(p.name for p in EXAMPLES_DIR.glob("*.yaml"))


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_validates(filename: str) -> None:
    text = (EXAMPLES_DIR / filename).read_text()
    result = validate(text)
    assert result.ok, [(e.path, e.message) for e in result.errors]
    assert isinstance(result.spec, Spec)


def _assert_failure(
    text: str,
    *,
    path_contains: str | None = None,
    msg_contains: str | None = None,
) -> ValidationResult:
    result = validate(text)
    assert not result.ok
    assert result.spec is None
    assert result.errors, "expected at least one SpecError"
    for e in result.errors:
        assert isinstance(e, SpecError)
    if path_contains is not None:
        assert any(path_contains in e.path for e in result.errors), [
            (e.path, e.message) for e in result.errors
        ]
    if msg_contains is not None:
        assert any(msg_contains.lower() in e.message.lower() for e in result.errors), [
            (e.path, e.message) for e in result.errors
        ]
    return result


def test_unknown_top_level_field_with_suggestion() -> None:
    text = "version: 1\nnewtork:\n  outbound:\n    allowed: [api.example.com]\n"
    result = _assert_failure(text, path_contains="$", msg_contains="Additional properties")
    assert any(e.suggestion and "network" in e.suggestion for e in result.errors), [
        (e.path, e.message, e.suggestion) for e in result.errors
    ]


def test_malformed_effect_value_not_a_string() -> None:
    text = "version: 1\nimports:\n  allowed:\n    - 123\n"
    _assert_failure(text, path_contains="imports")


def test_missing_required_version() -> None:
    text = "network:\n  outbound:\n    allowed: [api.example.com]\n"
    _assert_failure(text, path_contains="$", msg_contains="version")


def test_wrong_version_literal() -> None:
    text = "version: 2\nnetwork:\n  outbound:\n    allowed: [api.example.com]\n"
    _assert_failure(text, path_contains="version")


def test_type_mismatch_on_slot() -> None:
    text = "version: 1\nimports:\n  allowed: pickle\n"
    _assert_failure(text, path_contains="allowed")
