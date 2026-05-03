"""Critique diff — buckets Observations against a compiled Spec into Findings.

Per ADR-0001 (effect taxonomy v1), Findings live in five buckets:

- `missing-required` (high) — a `required` Spec entry with no matching Observation.
- `added-forbidden`  (high) — an Observation matched by a `forbidden` Spec entry.
- `added-unspecified`(drift) — an Observation not mentioned in the Spec.
- `within-spec`     (info)  — an Observation matched by `required` or `allowed`.
- `unresolved`      (info)  — an Observation whose parameter is the unresolved
  sentinel (`Observation.is_unresolved`); never compared against the Spec.

Classification delegates to `SpecMatchers.classify` (T16), which encodes the
strongest-slot precedence `forbidden > required > allowed > unspecified`. An
Observation that classifies as `forbidden` may *also* satisfy a required entry
(see `SpecMatchers.matched_required`); both facts are recorded — the
added-forbidden Finding fires *and* the required entry is marked seen so it
does not show up as missing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from spectate.critique.expected import RequiredKey, SpecMatchers
from spectate.observations.observation import Observation

INLINE_IGNORE_MARKER = "# spectate: ignore"

FindingKind = Literal[
    "missing-required",
    "added-forbidden",
    "added-unspecified",
    "within-spec",
    "unresolved",
]

Severity = Literal["high", "drift", "info"]

_SEVERITY_BY_KIND: dict[FindingKind, Severity] = {
    "missing-required": "high",
    "added-forbidden": "high",
    "added-unspecified": "drift",
    "within-spec": "info",
    "unresolved": "info",
}


@dataclass(frozen=True, slots=True)
class Finding:
    kind: FindingKind
    observation: Observation | None
    required_key: RequiredKey | None
    severity: Severity

    @property
    def id(self) -> str:
        """Stable short hash derived from (kind, category, parameter, file, line).

        For Observation-bearing Findings, those fields come from the
        Observation. For ``missing-required`` Findings (no Observation), the
        category/parameter come from the ``RequiredKey`` and file/line are the
        empty string and 0 respectively. The result is the first 12 hex chars
        of a SHA-256, prefixed with ``F-`` for human readability.
        """
        if self.observation is not None:
            obs = self.observation
            parts = (self.kind, obs.category, obs.parameter, obs.file.as_posix(), str(obs.line))
        else:
            key = self.required_key
            assert key is not None
            parts = (self.kind, key.category, key.parameter, key.scope or "", "0")
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return f"F-{digest[:12]}"


@dataclass(frozen=True, slots=True)
class Findings:
    missing_required: tuple[Finding, ...]
    added_forbidden: tuple[Finding, ...]
    added_unspecified: tuple[Finding, ...]
    within_spec: tuple[Finding, ...]
    unresolved: tuple[Finding, ...]

    @property
    def has_violations(self) -> bool:
        return bool(self.missing_required or self.added_forbidden or self.added_unspecified)

    def all(self) -> tuple[Finding, ...]:
        """Concatenate buckets in fixed order: missing → forbidden → unspecified
        → within-spec → unresolved. Each bucket is already deterministically
        sorted; bucket-order yields a stable, reporter-friendly stream."""
        return (
            self.missing_required
            + self.added_forbidden
            + self.added_unspecified
            + self.within_spec
            + self.unresolved
        )


def _make(kind: FindingKind, *, obs: Observation | None, key: RequiredKey | None) -> Finding:
    return Finding(kind=kind, observation=obs, required_key=key, severity=_SEVERITY_BY_KIND[kind])


def critique(observations: Iterable[Observation], matchers: SpecMatchers) -> Findings:
    """Bucket Observations against the compiled Spec.

    Determinism: each bucket is sorted — Observation-bearing buckets by
    Observation natural order (the dataclass is frozen and `order=True`),
    `missing-required` by `RequiredKey` natural order.
    """
    missing: list[Finding] = []
    forbidden: list[Finding] = []
    unspecified: list[Finding] = []
    within: list[Finding] = []
    unresolved_bucket: list[Finding] = []

    seen_required: set[RequiredKey] = set()

    file_line_cache: dict[Path, list[str]] = {}

    for obs in observations:
        if _is_inline_ignored(obs, file_line_cache):
            continue
        if obs.is_unresolved:
            unresolved_bucket.append(_make("unresolved", obs=obs, key=None))
            continue

        for key in matchers.matched_required(obs):
            seen_required.add(key)

        slot = matchers.classify(obs)
        if slot == "forbidden":
            forbidden.append(_make("added-forbidden", obs=obs, key=None))
        elif slot == "required" or slot == "allowed":
            within.append(_make("within-spec", obs=obs, key=None))
        else:
            unspecified.append(_make("added-unspecified", obs=obs, key=None))

    for key in matchers.all_required_keys():
        if key not in seen_required:
            missing.append(_make("missing-required", obs=None, key=key))

    missing.sort(key=lambda f: _required_sort_key(f.required_key))
    forbidden.sort(key=_obs_sort_key)
    unspecified.sort(key=_obs_sort_key)
    within.sort(key=_obs_sort_key)
    unresolved_bucket.sort(key=_obs_sort_key)

    return Findings(
        missing_required=tuple(missing),
        added_forbidden=tuple(forbidden),
        added_unspecified=tuple(unspecified),
        within_spec=tuple(within),
        unresolved=tuple(unresolved_bucket),
    )


def _obs_sort_key(f: Finding) -> tuple[str, str, str, int]:
    obs = f.observation
    assert obs is not None
    return (obs.category, obs.parameter, str(obs.file), obs.line)


def _is_inline_ignored(obs: Observation, cache: dict[Path, list[str]]) -> bool:
    """Return True if the source line ends with ``# spectate: ignore``.

    Reads the source file lazily and caches per file. Returns False on any
    IO error (missing file, decode error, line out of range) — silently, to
    avoid making the Critique fragile to file-system races.
    """
    if obs.line <= 0:
        return False
    lines = cache.get(obs.file)
    if lines is None:
        try:
            lines = obs.file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        cache[obs.file] = lines
    if obs.line > len(lines):
        return False
    return lines[obs.line - 1].rstrip().endswith(INLINE_IGNORE_MARKER)


def _required_sort_key(key: RequiredKey | None) -> tuple[str, str, str]:
    assert key is not None
    return (key.category, key.parameter, key.scope or "")
