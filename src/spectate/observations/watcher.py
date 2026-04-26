from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from spectate.observations.observation import Observation


@runtime_checkable
class Watcher(Protocol):
    """A Watcher inspects a single source file and emits Observations.

    Implementations are duck-typed; no inheritance required. A Watcher is any
    object with a `name: str` attribute and an `observe(path)` method.
    """

    name: str

    def observe(self, path: Path) -> Iterable[Observation]: ...


_REGISTRY: list[Watcher] = []


def register_watcher(watcher: Watcher) -> Watcher:
    """Register a Watcher. Idempotent on duplicate `name`.

    Returns the watcher unchanged so this can be used as a decorator-like
    side effect at module import time.
    """
    for existing in _REGISTRY:
        if existing.name == watcher.name:
            return existing
    _REGISTRY.append(watcher)
    return watcher


def all_watchers() -> tuple[Watcher, ...]:
    """Return all currently-registered Watchers in registration order."""
    return tuple(_REGISTRY)


def clear_registry() -> None:
    """Test seam — wipe the registry between unit tests."""
    _REGISTRY.clear()
