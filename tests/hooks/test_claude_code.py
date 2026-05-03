from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from spectate.hooks import claude_code as hook

CLEAN_BULLETIN = {
    "schema_version": 1,
    "summary": {
        "missing_required": 0,
        "added_forbidden": 0,
        "added_unspecified": 0,
        "unresolved": 0,
        "within_spec": 0,
        "high_total": 0,
        "drift_total": 0,
    },
    "findings": {
        "missing-required": [],
        "added-forbidden": [],
        "added-unspecified": [],
        "unresolved": [],
        "within-spec": [],
    },
}

DRIFT_BULLETIN = {
    "schema_version": 1,
    "summary": {
        "missing_required": 1,
        "added_forbidden": 0,
        "added_unspecified": 2,
        "unresolved": 0,
        "within_spec": 0,
        "high_total": 1,
        "drift_total": 2,
    },
    "findings": {
        "missing-required": [
            {
                "kind": "missing-required",
                "severity": "high",
                "category": "network.outbound",
                "parameter": "api.stripe.com",
                "file": None,
                "line": None,
            }
        ],
        "added-forbidden": [],
        "added-unspecified": [
            {
                "kind": "added-unspecified",
                "severity": "drift",
                "category": "fs.write",
                "parameter": "/tmp/foo",
                "file": "src/a.py",
                "line": 12,
            },
            {
                "kind": "added-unspecified",
                "severity": "drift",
                "category": "subprocess",
                "parameter": "rm",
                "file": "src/b.py",
                "line": 3,
            },
        ],
        "unresolved": [],
        "within-spec": [],
    },
}


def _payload(tool: str, cwd: str, event: str = "PreToolUse") -> dict[str, Any]:
    return {
        "hook_event_name": event,
        "tool_name": tool,
        "cwd": cwd,
        "tool_input": {"file_path": f"{cwd}/x.py"},
    }


def _seed_spec(root: Path) -> None:
    (root / ".spectate").mkdir(parents=True, exist_ok=True)
    (root / ".spectate" / "spec.yaml").write_text("version: 1\n")


def test_pretooluse_write_with_drift_emits_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_spec(tmp_path)
    monkeypatch.setattr(hook, "_run_review", lambda *_: DRIFT_BULLETIN)
    out = hook.process(_payload("Write", str(tmp_path)))
    assert out is not None
    block = out["hookSpecificOutput"]
    assert block["hookEventName"] == "PreToolUse"
    ctx = block["additionalContext"]
    assert "Spectate detected drift" in ctx
    assert "high=1" in ctx
    assert "drift=2" in ctx
    assert "api.stripe.com" in ctx
    assert "/tmp/foo" in ctx


def test_pretooluse_write_clean_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_spec(tmp_path)
    monkeypatch.setattr(hook, "_run_review", lambda *_: CLEAN_BULLETIN)
    assert hook.process(_payload("Write", str(tmp_path))) is None


def test_missing_spec_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"n": 0}

    def _boom(*_: Any) -> None:
        called["n"] += 1
        raise AssertionError("should not be called")

    monkeypatch.setattr(hook, "_run_review", _boom)
    assert hook.process(_payload("Write", str(tmp_path))) is None
    assert called["n"] == 0


def test_non_watched_tool_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_spec(tmp_path)
    monkeypatch.setattr(hook, "_run_review", lambda *_: (_ for _ in ()).throw(AssertionError("no")))
    assert hook.process(_payload("Bash", str(tmp_path))) is None
    assert hook.process(_payload("Read", str(tmp_path))) is None


def test_non_pretooluse_event_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_spec(tmp_path)
    monkeypatch.setattr(hook, "_run_review", lambda *_: DRIFT_BULLETIN)
    assert hook.process(_payload("Write", str(tmp_path), event="PostToolUse")) is None


def test_main_reads_stdin_and_writes_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_spec(tmp_path)
    monkeypatch.setattr(hook, "_run_review", lambda *_: DRIFT_BULLETIN)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload("Edit", str(tmp_path)))))
    rc = hook.main()
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_main_silent_on_malformed_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_run_review_returns_none_on_invalid_spec(tmp_path: Path) -> None:
    (tmp_path / ".spectate").mkdir()
    spec = tmp_path / ".spectate" / "spec.yaml"
    spec.write_text("not: a: valid: spec\n::: bad\n")
    assert hook._run_review(tmp_path, spec) is None
