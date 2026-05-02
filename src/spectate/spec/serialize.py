"""Serialize a Spec to clean YAML.

Strips empty subcategories/slots so the draft output stays readable rather
than emitting a forest of empty ``required: []`` / ``allowed: []`` /
``forbidden: []`` lists.
"""

from __future__ import annotations

from typing import Any

import yaml

from spectate.spec.models import Spec


def _prune(value: Any) -> Any:
    if isinstance(value, dict):
        pruned: dict[str, Any] = {}
        for k, v in value.items():
            cleaned = _prune(v)
            if _is_empty(cleaned):
                continue
            pruned[k] = cleaned
        return pruned
    if isinstance(value, list):
        return [_prune(v) for v in value]
    return value


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, (dict, list)) and len(value) == 0


_PRESERVE_KEYS = frozenset({"version", "unresolved_handling", "stdlib_auto_allow"})


def spec_to_yaml(spec: Spec) -> str:
    raw = spec.model_dump(mode="json", exclude_none=False)
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _PRESERVE_KEYS:
            cleaned[key] = value
            continue
        pruned = _prune(value)
        if _is_empty(pruned):
            continue
        cleaned[key] = pruned
    return yaml.safe_dump(cleaned, sort_keys=False, default_flow_style=False)
