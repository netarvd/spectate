"""Compile a parsed `Spec` into matchers consumed by the Critique diff (T17).

`compile_spec(spec)` returns a `SpecMatchers` whose three methods form the
locked contract T17 builds Findings from:

- `classify(obs)` returns the strongest slot the Observation matches:
  `forbidden > required > allowed > unspecified`.
- `matched_required(obs)` returns every required entry the Observation
  satisfies (independent of `classify`'s precedence). T17 subtracts the
  union of these across all Observations from `all_required_keys()` to
  produce `missing-required` Findings.
- `all_required_keys()` enumerates every required entry in the Spec.

Match semantics follow ADR-0001:

- `network.outbound` — hostname glob via `fnmatch`.
- `fs.read` / `fs.write` — gitignore-style path glob via `pathspec`.
- `subprocess` — exact basename, with the slot-level sentinel `*`
  meaning "all binaries".
- `imports` / `env.read` / `db.read` / `db.write` — exact match only.

Per-handler scope at v1 is matched on **file path only** (ADR-0002 syntax
allows `path/file.py::function_name`, but resolving the enclosing function
of an Observation requires per-file AST analysis we defer to a later
iteration). Comparison is suffix-match on POSIX-normalised parts so
absolute Observation paths line up with repo-relative Spec paths. The
bare `function_name` shortcut (no `::`) degenerates to an unscoped match
under v1; it is documented and surfaced as a known gap.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from spectate.observations.observation import Observation
from spectate.spec.models import EffectSlots, ScopedRequired, Spec

Slot = Literal["required", "allowed", "forbidden", "unspecified"]

_SUBPROCESS_WILDCARD = "*"


@dataclass(frozen=True)
class RequiredKey:
    """Identity of a single `required` entry in the Spec.

    `(category, parameter, scope)` — `scope` is `None` for unconditional
    repo-wide entries and the verbatim handler string (e.g.
    `"jobs/exporter.py::run"`) for scoped entries. Hashable and ordered
    deterministically so T17 can dedupe and sort.
    """

    category: str
    parameter: str
    scope: str | None = None


@dataclass(frozen=True)
class _ScopeMatcher:
    """File-path scope filter for a `required` entry."""

    handler: str | None

    @property
    def file_part(self) -> str | None:
        if self.handler is None:
            return None
        head, sep, _ = self.handler.partition("::")
        if not sep:
            return None
        return head or None

    def matches(self, obs: Observation) -> bool:
        file_part = self.file_part
        if file_part is None:
            return True
        obs_parts = PurePosixPath(obs.file.as_posix()).parts
        spec_parts = PurePosixPath(file_part).parts
        if len(spec_parts) > len(obs_parts):
            return False
        return obs_parts[-len(spec_parts) :] == spec_parts


@dataclass
class _CategoryMatchers:
    """Compiled matchers for a single category's three slots."""

    category: str
    required: list[tuple[RequiredKey, str, _ScopeMatcher]] = field(default_factory=list)
    allowed_patterns: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    allowed_pathspec: PathSpec[GitWildMatchPattern] | None = None
    forbidden_pathspec: PathSpec[GitWildMatchPattern] | None = None
    required_pathspec: PathSpec[GitWildMatchPattern] | None = None
    required_index: list[tuple[RequiredKey, _ScopeMatcher]] = field(default_factory=list)


_HOST_GLOB_CATEGORIES = frozenset({"network.outbound"})
_PATH_GLOB_CATEGORIES = frozenset({"fs.read", "fs.write"})
_SUBPROCESS_CATEGORY = "subprocess"


def _is_glob_category(category: str) -> bool:
    return category in _HOST_GLOB_CATEGORIES or category in _PATH_GLOB_CATEGORIES


def _host_matches(pattern: str, host: str) -> bool:
    return fnmatch.fnmatchcase(host.lower(), pattern.lower())


def _build_pathspec(patterns: Iterable[str]) -> PathSpec[GitWildMatchPattern] | None:
    items = [p for p in patterns if p]
    if not items:
        return None
    return PathSpec.from_lines(GitWildMatchPattern, items)


def _path_matches(spec_pattern: str, value: str) -> bool:
    ps = PathSpec.from_lines(GitWildMatchPattern, [spec_pattern])
    return ps.match_file(value)


class SpecMatchers:
    """Locked contract consumed by T17.

    Construct via `compile_spec(spec)`. Stateless after construction.
    """

    def __init__(self, categories: dict[str, _CategoryMatchers]):
        self._categories = categories
        self._all_required: tuple[RequiredKey, ...] = tuple(
            sorted(
                (key for cat in categories.values() for key, _, _ in cat.required),
                key=lambda k: (k.category, k.parameter, k.scope or ""),
            )
        )

    def classify(self, obs: Observation) -> Slot:
        """Return the strongest slot this Observation matches.

        Precedence: `forbidden > required > allowed > unspecified`.
        Unresolved Observations (`obs.is_unresolved`) always classify as
        `unspecified` — the Bulletin routes them to a dedicated
        `unresolved` severity per ADR-0001, not through the Spec slots.
        """
        if obs.is_unresolved:
            return "unspecified"
        cat = self._categories.get(obs.category)
        if cat is None:
            return "unspecified"
        if self._matches_forbidden(cat, obs):
            return "forbidden"
        if self._matches_required(cat, obs):
            return "required"
        if self._matches_allowed(cat, obs):
            return "allowed"
        return "unspecified"

    def matched_required(self, obs: Observation) -> tuple[RequiredKey, ...]:
        """Return every required entry this Observation satisfies.

        Independent of `classify` — an Observation that classifies as
        `forbidden` may still satisfy a required entry, and T17 records
        both facts (the missing-required slot is filled, the
        added-forbidden Finding still fires).
        """
        if obs.is_unresolved:
            return ()
        cat = self._categories.get(obs.category)
        if cat is None:
            return ()
        hits: list[RequiredKey] = []
        for key, pattern, scope in cat.required:
            if not scope.matches(obs):
                continue
            if _category_value_matches(obs.category, pattern, obs.parameter):
                hits.append(key)
        return tuple(hits)

    def all_required_keys(self) -> tuple[RequiredKey, ...]:
        """Every required entry across every category, deterministically ordered."""
        return self._all_required

    def _matches_forbidden(self, cat: _CategoryMatchers, obs: Observation) -> bool:
        if obs.category in _PATH_GLOB_CATEGORIES:
            return cat.forbidden_pathspec is not None and cat.forbidden_pathspec.match_file(
                obs.parameter
            )
        for pattern in cat.forbidden_patterns:
            if _category_value_matches(obs.category, pattern, obs.parameter):
                return True
        return False

    def _matches_allowed(self, cat: _CategoryMatchers, obs: Observation) -> bool:
        if obs.category in _PATH_GLOB_CATEGORIES:
            return cat.allowed_pathspec is not None and cat.allowed_pathspec.match_file(
                obs.parameter
            )
        for pattern in cat.allowed_patterns:
            if _category_value_matches(obs.category, pattern, obs.parameter):
                return True
        return False

    def _matches_required(self, cat: _CategoryMatchers, obs: Observation) -> bool:  # noqa: ARG002
        return bool(self.matched_required(obs))


def _category_value_matches(category: str, pattern: str, value: str) -> bool:
    if category in _HOST_GLOB_CATEGORIES:
        return _host_matches(pattern, value)
    if category in _PATH_GLOB_CATEGORIES:
        return _path_matches(pattern, value)
    if category == _SUBPROCESS_CATEGORY and pattern == _SUBPROCESS_WILDCARD:
        return True
    return pattern == value


def compile_spec(spec: Spec) -> SpecMatchers:
    """Compile a parsed `Spec` into a `SpecMatchers`.

    Patterns are compiled once here, not per-Observation. Empty/None
    sections produce no matchers — `classify` returns `"unspecified"` for
    every Observation against a fully-empty Spec.
    """
    categories: dict[str, _CategoryMatchers] = {}

    if spec.network and spec.network.outbound:
        categories["network.outbound"] = _compile_category(
            "network.outbound", spec.network.outbound
        )
    if spec.fs:
        if spec.fs.read:
            categories["fs.read"] = _compile_category("fs.read", spec.fs.read)
        if spec.fs.write:
            categories["fs.write"] = _compile_category("fs.write", spec.fs.write)
    if spec.subprocess:
        categories["subprocess"] = _compile_category("subprocess", spec.subprocess)
    if spec.imports:
        categories["imports"] = _compile_category("imports", spec.imports)
    if spec.env and spec.env.read:
        categories["env.read"] = _compile_category("env.read", spec.env.read)
    if spec.db:
        if spec.db.read:
            categories["db.read"] = _compile_category("db.read", spec.db.read)
        if spec.db.write:
            categories["db.write"] = _compile_category("db.write", spec.db.write)

    return SpecMatchers(categories)


def _compile_category(category: str, slots: EffectSlots) -> _CategoryMatchers:
    cat = _CategoryMatchers(category=category)
    for entry in slots.required:
        if isinstance(entry, ScopedRequired):
            scope = _ScopeMatcher(handler=entry.handler)
            key = RequiredKey(category=category, parameter=entry.value, scope=entry.handler)
            cat.required.append((key, entry.value, scope))
        else:
            scope = _ScopeMatcher(handler=None)
            key = RequiredKey(category=category, parameter=entry, scope=None)
            cat.required.append((key, entry, scope))

    cat.allowed_patterns = list(slots.allowed)
    cat.forbidden_patterns = list(slots.forbidden)

    if category in _PATH_GLOB_CATEGORIES:
        cat.allowed_pathspec = _build_pathspec(slots.allowed)
        cat.forbidden_pathspec = _build_pathspec(slots.forbidden)

    return cat
