"""Transcribe Observations into a draft Spec.

Buckets each Observation into the matching category's ``allowed`` slot. We
never auto-populate ``required`` or ``forbidden`` from observation alone —
the human decides intent. Unresolved Observations (parameter == "*") are
skipped silently; surfacing them as wildcard ``allowed`` would be louder
than helpful here.
"""

from __future__ import annotations

from collections.abc import Iterable

from spectate.observations.observation import UNRESOLVED, Observation
from spectate.spec.models import (
    DbSection,
    EffectSlots,
    EnvSection,
    FsSection,
    NetworkSection,
    Spec,
)


def _dedup_sorted(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def observations_to_spec(observations: Iterable[Observation]) -> Spec:
    """Bucket Observations into a draft Spec, populating only ``allowed``."""
    buckets: dict[str, list[str]] = {}
    for obs in observations:
        if obs.parameter == UNRESOLVED:
            continue
        buckets.setdefault(obs.category, []).append(obs.parameter)

    def slots(category: str) -> EffectSlots | None:
        params = buckets.get(category)
        if not params:
            return None
        return EffectSlots(allowed=_dedup_sorted(params))

    network_outbound = slots("network.outbound")
    fs_read = slots("fs.read")
    fs_write = slots("fs.write")
    env_read = slots("env.read")
    db_read = slots("db.read")
    db_write = slots("db.write")
    subprocess_slots = slots("subprocess")
    imports_slots = slots("imports")

    return Spec(
        version=1,
        network=NetworkSection(outbound=network_outbound) if network_outbound else None,
        fs=FsSection(read=fs_read, write=fs_write) if (fs_read or fs_write) else None,
        subprocess=subprocess_slots,
        imports=imports_slots,
        env=EnvSection(read=env_read) if env_read else None,
        db=DbSection(read=db_read, write=db_write) if (db_read or db_write) else None,
    )
