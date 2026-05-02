"""Effect aggregator — collects Observations from registered Watchers.

Importing `spectate.watchers` is what triggers Watcher registration via
side-effecting module imports. Callers that rely on `all_watchers()` must
import that package (directly or transitively) before invoking `aggregate`.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from pathlib import Path

from spectate.observations.observation import Observation
from spectate.observations.watcher import Watcher, all_watchers

_DEFAULT_IGNORED_DIRS = frozenset({".venv", "venv", "node_modules", ".git", "__pycache__"})


class WatcherError(RuntimeWarning):
    """Emitted when a Watcher raises while observing a file."""


def aggregate(path: Path, *, watchers: Iterable[Watcher] | None = None) -> tuple[Observation, ...]:
    """Run Watchers across `path` and return a sorted, deduped tuple.

    If `path` is a file, each Watcher observes it once. If `path` is a
    directory, it is walked recursively for `.py` files, skipping any
    directory whose name starts with `.` or appears in the built-in ignore
    list (`.venv`, `venv`, `node_modules`, `.git`, `__pycache__`). Symlinked
    directories are skipped to avoid cycles.

    `watchers` defaults to `all_watchers()`. The default registry is only
    populated by importing `spectate.watchers`; callers wanting the full
    set must ensure that import has happened.

    Observations are deduped on identity `(category, parameter, file, line,
    tags)` per ADR-0008. Metadata of duplicates is merged by union; on key
    conflict the first-seen value wins.

    A Watcher that raises while observing a file does not abort the scan —
    a `WatcherError` warning is emitted and the scan continues.
    """
    files = _collect_files(path)
    selected = tuple(watchers) if watchers is not None else all_watchers()
    merged: dict[tuple[object, ...], Observation] = {}
    for file in files:
        for watcher in selected:
            try:
                produced = watcher.observe(file)
            except Exception as exc:
                warnings.warn(
                    f"Watcher {watcher.name!r} failed on {file}: {exc!r}",
                    WatcherError,
                    stacklevel=2,
                )
                continue
            for obs in produced:
                key = (obs.category, obs.parameter, obs.file, obs.line, obs.tags)
                existing = merged.get(key)
                if existing is None:
                    merged[key] = obs
                    continue
                for k, v in obs.metadata.items():
                    if k not in existing.metadata:
                        existing.metadata[k] = v
    return tuple(sorted(merged.values()))


def _collect_files(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,) if path.suffix == ".py" else ()
    if not path.is_dir():
        return ()
    found: list[Path] = []
    _walk(path, found)
    found.sort()
    return tuple(found)


def _walk(directory: Path, sink: list[Path]) -> None:
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name.startswith(".") or entry.name in _DEFAULT_IGNORED_DIRS:
                continue
            _walk(entry, sink)
        elif entry.is_file() and entry.suffix == ".py":
            sink.append(entry)
