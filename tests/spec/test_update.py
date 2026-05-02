from __future__ import annotations

import pytest

from spectate.spec.update import (
    DeltaError,
    apply_diff,
    compute_diff,
    parse_yaml,
    to_yaml,
)


def _spec(**kw):
    base = {"version": 1}
    base.update(kw)
    return base


def test_addition_to_empty_category():
    existing = _spec()
    delta = {"version": 1, "fs": {"read": {"allowed": ["/etc/config.yaml"]}}}
    diff = compute_diff(existing, delta)
    assert len(diff.additions) == 1
    add = diff.additions[0]
    assert add.where.path == ("fs", "read")
    assert add.slot == "allowed"
    assert add.value == "/etc/config.yaml"
    assert not diff.conflicts
    assert not diff.removals


def test_addition_already_present_is_noop():
    existing = _spec(network={"outbound": {"allowed": ["api.stripe.com"]}})
    delta = {"version": 1, "network": {"outbound": {"allowed": ["api.stripe.com"]}}}
    diff = compute_diff(existing, delta)
    assert not diff.additions
    assert len(diff.noops) == 1


def test_addition_to_different_slot_is_conflict():
    existing = _spec(network={"outbound": {"allowed": ["api.stripe.com"]}})
    delta = {"version": 1, "network": {"outbound": {"forbidden": ["api.stripe.com"]}}}
    diff = compute_diff(existing, delta)
    assert not diff.additions
    assert len(diff.conflicts) == 1
    c = diff.conflicts[0]
    assert c.new_slot == "forbidden"
    assert c.existing_slot == "allowed"


def test_promote_allowed_to_required_via_add_plus_remove():
    existing = _spec(network={"outbound": {"allowed": ["api.stripe.com"]}})
    delta = {
        "version": 1,
        "network": {
            "outbound": {
                "required": ["api.stripe.com"],
                "removed": {"allowed": ["api.stripe.com"]},
            }
        },
    }
    diff = compute_diff(existing, delta)
    # The new required entry doesn't exist as required → addition (and
    # conflicts with the existing allowed entry — but the user explicitly
    # paired it with a removal so it would have been a conflict in v1).
    # We treat it as a conflict here; the dev resolves by approving both
    # entries. Document this behavior.
    assert len(diff.conflicts) == 1
    assert len(diff.removals) == 1


def test_remove_existing_entry():
    existing = _spec(network={"outbound": {"forbidden": ["tracking.example.com"]}})
    delta = {
        "version": 1,
        "network": {"outbound": {"removed": {"forbidden": ["tracking.example.com"]}}},
    }
    diff = compute_diff(existing, delta)
    assert len(diff.removals) == 1
    merged = apply_diff(existing, diff)
    assert "network" not in merged  # pruned empty


def test_remove_missing_entry_is_idempotent():
    existing = _spec()
    delta = {
        "version": 1,
        "network": {"outbound": {"removed": {"allowed": ["nope.com"]}}},
    }
    diff = compute_diff(existing, delta)
    merged = apply_diff(existing, diff)
    assert merged == existing


def test_apply_addition_creates_path():
    existing = _spec(network={"outbound": {"allowed": ["a.com"]}})
    delta = {"version": 1, "fs": {"read": {"allowed": ["/etc/x"]}}}
    diff = compute_diff(existing, delta)
    merged = apply_diff(existing, diff)
    assert merged["fs"]["read"]["allowed"] == ["/etc/x"]
    assert merged["network"]["outbound"]["allowed"] == ["a.com"]


def test_apply_does_not_mutate_existing():
    existing = _spec(network={"outbound": {"allowed": ["a.com"]}})
    delta = {"version": 1, "network": {"outbound": {"allowed": ["b.com"]}}}
    diff = compute_diff(existing, delta)
    merged = apply_diff(existing, diff)
    assert existing["network"]["outbound"]["allowed"] == ["a.com"]
    assert merged["network"]["outbound"]["allowed"] == ["a.com", "b.com"]


def test_flat_category_subprocess():
    existing = _spec(subprocess={"allowed": ["git"]})
    delta = {"version": 1, "subprocess": {"allowed": ["rg"]}}
    diff = compute_diff(existing, delta)
    assert len(diff.additions) == 1
    assert diff.additions[0].where.path == ("subprocess",)
    merged = apply_diff(existing, diff)
    assert merged["subprocess"]["allowed"] == ["git", "rg"]


def test_scoped_required_different_handler_same_value_is_conflict():
    """Same value, different handler scope → conflict (per the policy:
    different surrounding metadata requires explicit resolution)."""
    existing = _spec(
        network={
            "outbound": {
                "required": [{"handler": "a.py::f", "value": "api.x.com"}],
            }
        }
    )
    delta = {
        "version": 1,
        "network": {"outbound": {"required": [{"handler": "b.py::g", "value": "api.x.com"}]}},
    }
    diff = compute_diff(existing, delta)
    assert not diff.additions
    assert len(diff.conflicts) == 1


def test_scoped_required_distinct_value_is_addition():
    existing = _spec(
        network={
            "outbound": {
                "required": [{"handler": "a.py::f", "value": "api.x.com"}],
            }
        }
    )
    delta = {
        "version": 1,
        "network": {"outbound": {"required": [{"handler": "b.py::g", "value": "api.y.com"}]}},
    }
    diff = compute_diff(existing, delta)
    assert len(diff.additions) == 1
    assert not diff.conflicts


def test_bare_string_vs_scoped_required_is_conflict():
    existing = _spec(network={"outbound": {"required": ["api.x.com"]}})
    delta = {
        "version": 1,
        "network": {"outbound": {"required": [{"handler": "a.py::f", "value": "api.x.com"}]}},
    }
    diff = compute_diff(existing, delta)
    assert not diff.additions
    assert len(diff.conflicts) == 1


def test_malformed_delta_slot_not_a_list_raises():
    with pytest.raises(DeltaError):
        compute_diff(_spec(), {"version": 1, "network": {"outbound": {"allowed": "x"}}})


def test_malformed_removed_unknown_slot_raises():
    with pytest.raises(DeltaError):
        compute_diff(
            _spec(),
            {"version": 1, "network": {"outbound": {"removed": {"frobnicated": []}}}},
        )


def test_empty_delta_yields_empty_diff():
    diff = compute_diff(_spec(), {"version": 1})
    assert diff.empty
    assert not diff.noops


def test_parse_yaml_round_trip():
    text = "version: 1\nnetwork:\n  outbound:\n    allowed:\n      - a.com\n"
    doc = parse_yaml(text)
    assert doc["version"] == 1
    out = to_yaml(doc)
    assert "version: 1" in out
    assert "a.com" in out


def test_parse_yaml_rejects_non_mapping():
    with pytest.raises(DeltaError):
        parse_yaml("- a\n- b\n")
