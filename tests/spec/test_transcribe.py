from __future__ import annotations

from pathlib import Path

from spectate.observations.observation import UNRESOLVED, Observation
from spectate.spec.transcribe import observations_to_spec


def _obs(category: str, parameter: str, line: int = 1) -> Observation:
    return Observation(
        category=category,
        parameter=parameter,
        file=Path("a.py"),
        line=line,
    )


def test_empty_observations_yields_minimal_spec() -> None:
    spec = observations_to_spec([])
    assert spec.version == 1
    assert spec.network is None
    assert spec.fs is None
    assert spec.subprocess is None
    assert spec.imports is None
    assert spec.env is None
    assert spec.db is None


def test_each_category_lands_in_allowed() -> None:
    obs = [
        _obs("network.outbound", "api.example.com"),
        _obs("fs.read", "./config.yaml"),
        _obs("fs.write", "/tmp/out.txt"),
        _obs("subprocess", "git"),
        _obs("imports", "requests"),
        _obs("env.read", "OPENAI_API_KEY"),
        _obs("db.read", "users"),
        _obs("db.write", "sessions"),
    ]
    spec = observations_to_spec(obs)
    assert spec.network is not None and spec.network.outbound is not None
    assert spec.network.outbound.allowed == ["api.example.com"]
    assert spec.network.outbound.required == []
    assert spec.network.outbound.forbidden == []

    assert spec.fs is not None
    assert spec.fs.read is not None and spec.fs.read.allowed == ["./config.yaml"]
    assert spec.fs.write is not None and spec.fs.write.allowed == ["/tmp/out.txt"]

    assert spec.subprocess is not None and spec.subprocess.allowed == ["git"]
    assert spec.imports is not None and spec.imports.allowed == ["requests"]

    assert spec.env is not None and spec.env.read is not None
    assert spec.env.read.allowed == ["OPENAI_API_KEY"]

    assert spec.db is not None
    assert spec.db.read is not None and spec.db.read.allowed == ["users"]
    assert spec.db.write is not None and spec.db.write.allowed == ["sessions"]


def test_dedup_and_sort() -> None:
    obs = [
        _obs("imports", "requests", 1),
        _obs("imports", "httpx", 2),
        _obs("imports", "requests", 99),
    ]
    spec = observations_to_spec(obs)
    assert spec.imports is not None
    assert spec.imports.allowed == ["httpx", "requests"]


def test_unresolved_skipped() -> None:
    spec = observations_to_spec([_obs("network.outbound", UNRESOLVED)])
    assert spec.network is None


def test_only_one_fs_subcategory_present() -> None:
    spec = observations_to_spec([_obs("fs.read", "./a")])
    assert spec.fs is not None
    assert spec.fs.read is not None
    assert spec.fs.write is None


def test_required_and_forbidden_never_populated() -> None:
    spec = observations_to_spec([_obs("subprocess", "git")])
    assert spec.subprocess is not None
    assert spec.subprocess.required == []
    assert spec.subprocess.forbidden == []
