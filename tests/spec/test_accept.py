from __future__ import annotations

from pathlib import Path

import pytest

from spectate.critique.diff import Finding
from spectate.critique.expected import RequiredKey
from spectate.observations.observation import Observation
from spectate.spec.accept import AcceptError, accept_finding
from spectate.spec.models import Spec


def _spec(**kw: object) -> Spec:
    base: dict[str, object] = {"version": 1}
    base.update(kw)
    return Spec.model_validate(base)


def _obs(category: str, parameter: str) -> Observation:
    return Observation(category=category, parameter=parameter, file=Path("a.py"), line=1)


def _finding(kind: str, obs: Observation | None = None, key: RequiredKey | None = None) -> Finding:
    sev = {"missing-required": "high", "added-forbidden": "high", "added-unspecified": "drift"}.get(
        kind, "info"
    )
    return Finding(kind=kind, observation=obs, required_key=key, severity=sev)  # type: ignore[arg-type]


def test_accept_added_unspecified_appends_to_allowed() -> None:
    spec = _spec()
    f = _finding("added-unspecified", obs=_obs("network.outbound", "api.example.com"))
    new = accept_finding(spec, f)
    assert new.network is not None and new.network.outbound is not None
    assert "api.example.com" in new.network.outbound.allowed


def test_accept_added_unspecified_idempotent() -> None:
    spec = _spec(imports={"allowed": ["httpx"]})
    f = _finding("added-unspecified", obs=_obs("imports", "httpx"))
    new = accept_finding(spec, f)
    assert new.imports is not None
    assert new.imports.allowed.count("httpx") == 1


def test_accept_added_forbidden_removes_from_forbidden() -> None:
    spec = _spec(imports={"forbidden": ["requests"]})
    f = _finding("added-forbidden", obs=_obs("imports", "requests"))
    new = accept_finding(spec, f)
    assert new.imports is not None
    assert "requests" not in new.imports.forbidden
    assert "requests" not in new.imports.allowed


def test_accept_missing_required_raises() -> None:
    spec = _spec()
    f = _finding("missing-required", key=RequiredKey(category="imports", parameter="requests"))
    with pytest.raises(AcceptError):
        accept_finding(spec, f)


def test_accept_unresolved_raises() -> None:
    spec = _spec()
    f = _finding("unresolved", obs=_obs("imports", "*"))
    with pytest.raises(AcceptError):
        accept_finding(spec, f)


def test_accept_within_spec_raises() -> None:
    spec = _spec(imports={"allowed": ["os"]})
    f = _finding("within-spec", obs=_obs("imports", "os"))
    with pytest.raises(AcceptError):
        accept_finding(spec, f)


def test_accept_subprocess_category() -> None:
    spec = _spec()
    f = _finding("added-unspecified", obs=_obs("subprocess", "git"))
    new = accept_finding(spec, f)
    assert new.subprocess is not None
    assert "git" in new.subprocess.allowed


def test_accept_fs_read_category() -> None:
    spec = _spec()
    f = _finding("added-unspecified", obs=_obs("fs.read", "/etc/hosts"))
    new = accept_finding(spec, f)
    assert new.fs is not None and new.fs.read is not None
    assert "/etc/hosts" in new.fs.read.allowed
