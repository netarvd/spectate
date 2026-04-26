"""Diff/merge logic for `spectate spec update`.

Given an existing Spec (as a dict parsed from YAML) and a delta produced by
the `spec-update` skill, compute additions / removals / conflicts and produce
a merged Spec dict for human review and re-validation.

A delta is a partial Spec with the same shape as a full Spec, plus an
optional `removed` section under each EffectSlots-bearing node:

    network:
      outbound:
        allowed: [api.openai.com]      # additions
        removed:
          forbidden: [tracking.example.com]

Top-level fields (`version`, `unresolved_handling`, `stdlib_auto_allow`)
are not modifiable via update — the delta's `version: 1` is asserted but
never copied over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

# Categories whose direct value is an EffectSlots dict (no subkey).
_FLAT_CATEGORIES = {"subprocess", "imports"}
# Categories whose direct value is an object of {subkey: EffectSlots}.
_NESTED_CATEGORIES = {
    "network": {"outbound"},
    "fs": {"read", "write"},
    "env": {"read"},
    "db": {"read", "write"},
}
_SLOTS = ("required", "allowed", "forbidden")


@dataclass(frozen=True)
class EffectKey:
    """Identifies an effect slot location: e.g. ('network', 'outbound')
    or ('subprocess',)."""

    path: tuple[str, ...]

    def display(self) -> str:
        return ".".join(self.path)


@dataclass(frozen=True)
class Change:
    """A single proposed change to a slot."""

    where: EffectKey
    slot: str
    value: Any  # str | dict for ScopedRequired
    kind: str  # "add" | "remove"

    def display_value(self) -> str:
        if isinstance(self.value, dict):
            return f"{self.value.get('value')}@{self.value.get('handler')}"
        return str(self.value)


@dataclass(frozen=True)
class Conflict:
    """A proposed addition that clashes with an existing entry in a different
    slot or different handler scope."""

    where: EffectKey
    new_slot: str
    new_value: Any
    existing_slot: str
    existing_value: Any

    def reason(self) -> str:
        nv = _value_display(self.new_value)
        ev = _value_display(self.existing_value)
        if self.new_slot != self.existing_slot:
            return (
                f"{self.where.display()}: {nv!r} would be added to "
                f"{self.new_slot!r} but already present in {self.existing_slot!r} "
                f"(as {ev!r})"
            )
        return (
            f"{self.where.display()}: {nv!r} would be added to "
            f"{self.new_slot!r} but a conflicting entry exists there: {ev!r}"
        )


@dataclass
class Diff:
    additions: list[Change] = field(default_factory=list)
    removals: list[Change] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    noops: list[Change] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.additions or self.removals or self.conflicts)


class DeltaError(ValueError):
    """Raised when the delta YAML is structurally malformed."""


def parse_yaml(text: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DeltaError(f"invalid YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise DeltaError("YAML root must be a mapping")
    return data


def _iter_slot_locations(doc: dict[str, Any]) -> list[EffectKey]:
    out: list[EffectKey] = []
    for cat in _FLAT_CATEGORIES:
        if cat in doc:
            out.append(EffectKey((cat,)))
    for cat, subs in _NESTED_CATEGORIES.items():
        node = doc.get(cat)
        if not isinstance(node, dict):
            continue
        for sub in subs:
            if sub in node:
                out.append(EffectKey((cat, sub)))
    return out


def _get_slots_node(doc: dict[str, Any], where: EffectKey) -> dict[str, Any] | None:
    cur: Any = doc
    for part in where.path:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if not isinstance(cur, dict):
        return None
    return cur


def _ensure_slots_node(doc: dict[str, Any], where: EffectKey) -> dict[str, Any]:
    cur: dict[str, Any] = doc
    for part in where.path[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    last = where.path[-1]
    nxt = cur.get(last)
    if not isinstance(nxt, dict):
        nxt = {}
        cur[last] = nxt
    return nxt


def _value_display(v: Any) -> str:
    if isinstance(v, dict):
        return f"{v.get('value')}@{v.get('handler')}"
    return str(v)


def _values_equivalent(a: Any, b: Any) -> bool:
    """Exact-match equivalence for v1.

    A bare string and a {handler, value} mapping are NOT equivalent even if
    their `value` matches — different scope.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return bool(a.get("handler") == b.get("handler") and a.get("value") == b.get("value"))
    return bool(a == b)


def _value_string(v: Any) -> str:
    if isinstance(v, dict):
        return str(v.get("value"))
    return str(v)


def _find_existing(slots: dict[str, Any], value: Any) -> tuple[str, Any] | None:
    """Find any existing entry in this slots node that either equals the
    candidate exactly OR shares the same surface value (different scope /
    different shape) — both are reasons to surface the candidate as an
    existing-match (no-op or conflict), never as a silent second add.
    Exact match is preferred over string match.
    """
    exact: tuple[str, Any] | None = None
    by_string: tuple[str, Any] | None = None
    target_string = _value_string(value)
    for slot in _SLOTS:
        entries = slots.get(slot)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if _values_equivalent(entry, value):
                if exact is None:
                    exact = (slot, entry)
            elif _value_string(entry) == target_string and by_string is None:
                by_string = (slot, entry)
    return exact or by_string


def compute_diff(existing: dict[str, Any], delta: dict[str, Any]) -> Diff:
    """Compute the Diff produced by applying ``delta`` to ``existing``.

    ``existing`` is a parsed Spec dict (top-level Spec). ``delta`` is the
    skill output, also a dict, with the additions/removals shape documented
    in the module docstring. Neither is mutated.
    """
    diff = Diff()

    for where in _iter_slot_locations(delta):
        delta_slots = _get_slots_node(delta, where) or {}
        existing_slots = _get_slots_node(existing, where) or {}

        for slot in _SLOTS:
            entries = delta_slots.get(slot)
            if entries is None:
                continue
            if not isinstance(entries, list):
                raise DeltaError(
                    f"delta {where.display()}.{slot} must be a list, got {type(entries).__name__}"
                )
            for value in entries:
                existing_match = _find_existing(existing_slots, value)
                if existing_match is None:
                    diff.additions.append(Change(where, slot, value, "add"))
                    continue
                ex_slot, ex_value = existing_match
                if ex_slot == slot and _values_equivalent(ex_value, value):
                    diff.noops.append(Change(where, slot, value, "add"))
                    continue
                diff.conflicts.append(
                    Conflict(
                        where=where,
                        new_slot=slot,
                        new_value=value,
                        existing_slot=ex_slot,
                        existing_value=ex_value,
                    )
                )

        removed = delta_slots.get("removed")
        if removed is not None:
            if not isinstance(removed, dict):
                raise DeltaError(
                    f"delta {where.display()}.removed must be a mapping, "
                    f"got {type(removed).__name__}"
                )
            for slot, entries in removed.items():
                if slot not in _SLOTS:
                    raise DeltaError(f"delta {where.display()}.removed.{slot}: unknown slot")
                if not isinstance(entries, list):
                    raise DeltaError(f"delta {where.display()}.removed.{slot} must be a list")
                for value in entries:
                    diff.removals.append(Change(where, slot, value, "remove"))

    return diff


def _deep_copy(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: _deep_copy(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_deep_copy(x) for x in d]
    return d


def apply_diff(existing: dict[str, Any], diff: Diff) -> dict[str, Any]:
    """Return a new dict: ``existing`` with ``diff.additions`` and
    ``diff.removals`` applied. Conflicts are NOT applied (caller resolves
    them by editing the diff before calling).
    """
    merged: dict[str, Any] = _deep_copy(existing)

    for change in diff.removals:
        slots = _get_slots_node(merged, change.where)
        if slots is None:
            continue
        entries = slots.get(change.slot)
        if not isinstance(entries, list):
            continue
        slots[change.slot] = [e for e in entries if not _values_equivalent(e, change.value)]
        if not slots[change.slot]:
            del slots[change.slot]
        _prune_empty(merged, change.where)

    for change in diff.additions:
        slots = _ensure_slots_node(merged, change.where)
        entries = slots.setdefault(change.slot, [])
        if not any(_values_equivalent(e, change.value) for e in entries):
            entries.append(change.value)

    return merged


def _prune_empty(doc: dict[str, Any], where: EffectKey) -> None:
    """After removals, drop empty slot containers and category nodes."""
    cur: dict[str, Any] = doc
    trail: list[tuple[dict[str, Any], str]] = []
    for part in where.path:
        if not isinstance(cur, dict) or part not in cur:
            return
        trail.append((cur, part))
        cur = cur[part]
    if isinstance(cur, dict) and not cur:
        for parent, key in reversed(trail):
            if isinstance(parent.get(key), dict) and not parent[key]:
                del parent[key]
            else:
                return


def to_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def format_diff(diff: Diff) -> str:
    """Human-readable rendering for terminal review."""
    lines: list[str] = []
    if diff.additions:
        lines.append("Additions:")
        for c in diff.additions:
            lines.append(f"  + {c.where.display()}.{c.slot}: {c.display_value()}")
    if diff.removals:
        lines.append("Removals:")
        for c in diff.removals:
            lines.append(f"  - {c.where.display()}.{c.slot}: {c.display_value()}")
    if diff.conflicts:
        lines.append("Conflicts (require resolution):")
        for k in diff.conflicts:
            lines.append(f"  ! {k.reason()}")
    if diff.noops:
        lines.append(f"No-ops (already present): {len(diff.noops)}")
    if not lines:
        lines.append("(no changes)")
    return "\n".join(lines)
