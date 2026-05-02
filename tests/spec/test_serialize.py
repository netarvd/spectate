from __future__ import annotations

from pathlib import Path

import yaml

from spectate.observations.observation import Observation
from spectate.spec.models import Spec
from spectate.spec.serialize import spec_to_yaml
from spectate.spec.transcribe import observations_to_spec
from spectate.spec.validate import validate


def test_empty_spec_strips_empty_subcategories() -> None:
    spec = Spec(version=1)
    text = spec_to_yaml(spec)
    parsed = yaml.safe_load(text)
    assert parsed == {
        "version": 1,
        "unresolved_handling": "surface",
        "stdlib_auto_allow": True,
    }
    assert "network" not in text
    assert "fs" not in text


def test_roundtrip_validates() -> None:
    obs = [
        Observation(
            category="network.outbound",
            parameter="api.example.com",
            file=Path("a.py"),
            line=1,
        ),
        Observation(
            category="imports",
            parameter="httpx",
            file=Path("a.py"),
            line=2,
        ),
    ]
    text = spec_to_yaml(observations_to_spec(obs))
    result = validate(text)
    assert result.ok, [(e.path, e.message) for e in result.errors]


def test_does_not_emit_empty_required_or_forbidden() -> None:
    obs = [
        Observation(
            category="imports",
            parameter="httpx",
            file=Path("a.py"),
            line=1,
        ),
    ]
    text = spec_to_yaml(observations_to_spec(obs))
    assert "required" not in text
    assert "forbidden" not in text
    assert "httpx" in text


def test_top_level_keys_preserved_even_when_default() -> None:
    spec = Spec(version=1)
    text = spec_to_yaml(spec)
    assert "version: 1" in text
    assert "unresolved_handling: surface" in text
    assert "stdlib_auto_allow: true" in text
