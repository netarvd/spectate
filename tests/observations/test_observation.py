from pathlib import Path

import pytest

from spectate.observations import UNRESOLVED, Observation


def test_observation_is_frozen_and_hashable() -> None:
    obs = Observation(
        category="network.outbound", parameter="api.example.com", file=Path("a.py"), line=10
    )
    assert {obs} == {obs}
    with pytest.raises(AttributeError):
        obs.parameter = "evil.com"  # type: ignore[misc]


def test_observation_orders_by_field_sequence() -> None:
    a = Observation("fs.read", "/tmp/a", Path("x.py"), 1)
    b = Observation("fs.read", "/tmp/b", Path("x.py"), 1)
    c = Observation("fs.write", "/tmp/a", Path("x.py"), 1)
    assert sorted([c, b, a]) == [a, b, c]


def test_observation_tags_default_empty() -> None:
    obs = Observation("imports", "os", Path("x.py"), 1)
    assert obs.tags == ()


def test_observation_tags_carry_metadata() -> None:
    obs = Observation("imports", "os", Path("x.py"), 1, tags=("stdlib",))
    assert obs.tags == ("stdlib",)


def test_unresolved_sentinel_detected() -> None:
    resolved = Observation("subprocess", "git", Path("x.py"), 1)
    unresolved = Observation("subprocess", UNRESOLVED, Path("x.py"), 1)
    assert not resolved.is_unresolved
    assert unresolved.is_unresolved
