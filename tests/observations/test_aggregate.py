from __future__ import annotations

import warnings
from collections.abc import Iterable
from pathlib import Path

import pytest

import spectate.watchers  # noqa: F401  — populates the default registry
from spectate.observations import (
    EmptyWatcherRegistryError,
    Observation,
    WatcherError,
    aggregate,
    clear_registry,
    register_watcher,
)

_KITCHEN_SINK = """\
import os
import requests
import subprocess
import sqlite3


def go() -> None:
    os.environ["API_KEY"]
    requests.get("https://api.example.com/v1")
    subprocess.run(["git", "status"])
    with open("/tmp/out.txt", "w") as fh:
        fh.write("hi")
    conn = sqlite3.connect(":memory:")
    conn.execute("SELECT id FROM users")
"""


def _ensure_default_registry() -> None:
    import importlib
    import sys

    from spectate.observations import all_watchers

    if all_watchers():
        return
    for mod in [
        "spectate.watchers.env",
        "spectate.watchers.fs",
        "spectate.watchers.imports_",
        "spectate.watchers.network",
        "spectate.watchers.sql",
        "spectate.watchers.subprocess_",
    ]:
        sys.modules.pop(mod, None)
        importlib.import_module(mod)


@pytest.fixture
def default_registry() -> Iterable[None]:
    _ensure_default_registry()
    yield


def test_aggregate_single_file_runs_all_watchers(tmp_path: Path, default_registry: None) -> None:
    target = tmp_path / "kitchen.py"
    target.write_text(_KITCHEN_SINK)
    obs = aggregate(target)
    categories = {o.category for o in obs}
    assert {
        "env.read",
        "network.outbound",
        "subprocess",
        "fs.write",
        "imports",
        "db.read",
    }.issubset(categories)


def test_aggregate_directory_walks_recursively(tmp_path: Path, default_registry: None) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("import os\n")
    (tmp_path / "pkg" / "sub").mkdir()
    (tmp_path / "pkg" / "sub" / "b.py").write_text("import sys\n")
    obs = aggregate(tmp_path)
    files = {o.file for o in obs}
    assert tmp_path / "pkg" / "a.py" in files
    assert tmp_path / "pkg" / "sub" / "b.py" in files


def test_aggregate_skips_ignored_dirs(tmp_path: Path, default_registry: None) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("import secret_pkg\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.py").write_text("import other_pkg\n")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "junk.py").write_text("import hidden_pkg\n")
    (tmp_path / "real.py").write_text("import json\n")
    obs = aggregate(tmp_path)
    params = {o.parameter for o in obs}
    assert "json" in params
    assert "secret_pkg" not in params
    assert "other_pkg" not in params
    assert "hidden_pkg" not in params


class _ConstWatcher:
    def __init__(self, name: str, observations: tuple[Observation, ...]) -> None:
        self.name = name
        self._observations = observations

    def observe(self, path: Path) -> Iterable[Observation]:
        return self._observations


def test_dedup_same_identity_collapses_to_one(tmp_path: Path) -> None:
    target = tmp_path / "x.py"
    target.write_text("")
    a = Observation("env.read", "FOO", target, 1)
    b = Observation("env.read", "FOO", target, 1)
    out = aggregate(target, watchers=[_ConstWatcher("a", (a,)), _ConstWatcher("b", (b,))])
    assert len(out) == 1


def test_metadata_merge_unions_keys_first_wins_on_conflict(
    tmp_path: Path,
) -> None:
    target = tmp_path / "x.py"
    target.write_text("")
    first = Observation(
        "db.read",
        "*",
        target,
        4,
        metadata={"unresolved_reason": "parse_failed", "shared": "first"},
    )
    second = Observation(
        "db.read",
        "*",
        target,
        4,
        metadata={"dialect": "sqlite", "shared": "second"},
    )
    out = aggregate(
        target,
        watchers=[_ConstWatcher("a", (first,)), _ConstWatcher("b", (second,))],
    )
    assert len(out) == 1
    merged = out[0].metadata
    assert merged["unresolved_reason"] == "parse_failed"
    assert merged["dialect"] == "sqlite"
    assert merged["shared"] == "first"


def test_sort_is_deterministic(tmp_path: Path, default_registry: None) -> None:
    target = tmp_path / "kitchen.py"
    target.write_text(_KITCHEN_SINK)
    first = aggregate(target)
    second = aggregate(target)
    assert first == second
    assert list(first) == sorted(first)


def test_custom_watchers_override_default_registry(tmp_path: Path) -> None:
    target = tmp_path / "x.py"
    target.write_text("import os\nos.environ['FOO']\n")

    class _Stub:
        name = "stub"

        def observe(self, path: Path) -> Iterable[Observation]:
            return (Observation("custom", "only", path, 1),)

    register_watcher(_Stub())  # default registry would also fire — but we pass watchers
    out = aggregate(target, watchers=[_Stub()])
    assert len(out) == 1
    assert out[0].category == "custom"


def test_watcher_exception_is_warned_not_raised(tmp_path: Path) -> None:
    target = tmp_path / "x.py"
    target.write_text("")

    class _Bad:
        name = "bad"

        def observe(self, path: Path) -> Iterable[Observation]:
            raise RuntimeError("boom")

    class _Good:
        name = "good"

        def observe(self, path: Path) -> Iterable[Observation]:
            return (Observation("env.read", "X", path, 1),)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = aggregate(target, watchers=[_Bad(), _Good()])
    assert len(out) == 1
    assert any(issubclass(w.category, WatcherError) for w in caught)


def test_non_python_file_yields_nothing(tmp_path: Path, default_registry: None) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("import os\n")
    assert aggregate(target) == ()


def test_directory_with_unparseable_file_skips_silently(
    tmp_path: Path, default_registry: None
) -> None:
    (tmp_path / "broken.py").write_text("def (:\n")
    (tmp_path / "ok.py").write_text("import json\n")
    out = aggregate(tmp_path)
    params = {o.parameter for o in out}
    assert "json" in params


def test_empty_registry_with_default_watchers_raises(tmp_path: Path) -> None:
    target = tmp_path / "x.py"
    target.write_text("import os\n")
    clear_registry()
    with pytest.raises(EmptyWatcherRegistryError) as exc_info:
        aggregate(target)
    assert "import spectate.watchers" in str(exc_info.value)
    assert "watchers=()" in str(exc_info.value)


def test_empty_registry_with_explicit_empty_watchers_is_a_no_op(tmp_path: Path) -> None:
    target = tmp_path / "x.py"
    target.write_text("import os\n")
    clear_registry()
    assert aggregate(target, watchers=()) == ()
