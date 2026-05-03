"""Accept a Finding into the Spec.

Pure function: takes the current parsed Spec plus the Finding to accept and
returns a new Spec with the Finding's effect added to (or removed from) the
appropriate slot. The CLI is responsible for IO.

Per the Critique taxonomy (ADR-0001):

- ``added-unspecified`` — the Observation is real and not yet in the Spec.
  Accept by appending the parameter to the matching ``allowed`` slot.
- ``added-forbidden``  — the Observation is real but the Spec forbids it.
  Accept by removing the matching pattern(s) from ``forbidden``. We do *not*
  silently re-add to ``allowed``: the developer should make the affirmative
  declaration via ``spec update`` or by editing the Spec. (Decision raised
  in PR; default is remove-only.)
- ``missing-required`` — there is no Observation to accept. ``accept`` is
  the wrong tool; the developer must either implement the requirement or
  drop it from the Spec. Raises ``AcceptError``.
- ``unresolved`` — the parameter is the unresolved sentinel; there is
  nothing concrete to add. Raises ``AcceptError``; route through inline
  ``# spectate: ignore`` instead.
- ``within-spec`` — already covered by the Spec; accepting it is a no-op.
  Raises ``AcceptError`` for clarity rather than silently doing nothing.
"""

from __future__ import annotations

from typing import Any

from spectate.critique.diff import Finding
from spectate.spec.models import (
    DbSection,
    EffectSlots,
    EnvSection,
    FsSection,
    NetworkSection,
    Spec,
)


class AcceptError(Exception):
    """Raised when a Finding cannot be accepted into the Spec."""


_CATEGORY_PATH: dict[str, tuple[str, ...]] = {
    "network.outbound": ("network", "outbound"),
    "fs.read": ("fs", "read"),
    "fs.write": ("fs", "write"),
    "subprocess": ("subprocess",),
    "imports": ("imports",),
    "env.read": ("env", "read"),
    "db.read": ("db", "read"),
    "db.write": ("db", "write"),
}


def accept_finding(spec: Spec, finding: Finding) -> Spec:
    """Return a new Spec with ``finding``'s effect accepted.

    See module docstring for the per-kind semantics.
    """
    if finding.kind == "missing-required":
        raise AcceptError(
            "Cannot 'accept' a missing-required Finding — implement the requirement "
            "or remove it from the Spec.",
        )
    if finding.kind == "unresolved":
        raise AcceptError(
            "Cannot 'accept' an unresolved Finding — add `# spectate: ignore` to the "
            "source line or resolve the parameter.",
        )
    if finding.kind == "within-spec":
        raise AcceptError("Finding is already within-spec; nothing to accept.")

    obs = finding.observation
    assert obs is not None  # added-unspecified and added-forbidden always carry one
    path = _CATEGORY_PATH.get(obs.category)
    if path is None:
        raise AcceptError(f"Unknown effect category: {obs.category!r}")

    raw = spec.model_dump()
    slots = _ensure_slots(raw, path)

    if finding.kind == "added-unspecified":
        if obs.parameter not in slots["allowed"]:
            slots["allowed"].append(obs.parameter)
    elif finding.kind == "added-forbidden":
        slots["forbidden"] = [p for p in slots["forbidden"] if p != obs.parameter]

    return Spec.model_validate(raw)


def _ensure_slots(raw: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    """Walk ``raw`` along ``path``, materialising EffectSlots-shaped dicts.

    Pydantic dumps ``None`` for missing sections; we replace those with empty
    dicts as we descend, then ensure the leaf has the three slot lists.
    """
    cursor = raw
    for key in path:
        if cursor.get(key) is None:
            cursor[key] = {}
        cursor = cursor[key]
    for slot in ("required", "allowed", "forbidden"):
        cursor.setdefault(slot, [])
    return cursor


# Re-exports used by validators / type checkers; ensure imports are not pruned.
_ = (DbSection, EffectSlots, EnvSection, FsSection, NetworkSection)
