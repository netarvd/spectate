from collections.abc import Iterable
from pathlib import Path

from spectate.observations import (
    Observation,
    Watcher,
    all_watchers,
    clear_registry,
    register_watcher,
)


class _StubWatcher:
    def __init__(self, name: str) -> None:
        self.name = name

    def observe(self, path: Path) -> Iterable[Observation]:
        return ()


def test_stub_satisfies_protocol() -> None:
    assert isinstance(_StubWatcher("x"), Watcher)


def test_register_appends_to_registry() -> None:
    clear_registry()
    a = _StubWatcher("a")
    b = _StubWatcher("b")
    register_watcher(a)
    register_watcher(b)
    assert all_watchers() == (a, b)


def test_register_returns_the_watcher_unchanged() -> None:
    clear_registry()
    w = _StubWatcher("a")
    assert register_watcher(w) is w


def test_register_is_idempotent_on_duplicate_name() -> None:
    clear_registry()
    first = _StubWatcher("dup")
    second = _StubWatcher("dup")
    register_watcher(first)
    returned = register_watcher(second)
    assert returned is first
    assert all_watchers() == (first,)


def test_clear_registry_empties() -> None:
    register_watcher(_StubWatcher("x"))
    clear_registry()
    assert all_watchers() == ()
