from __future__ import annotations

import json

from spectate.bulletin.json_format import SCHEMA_VERSION, render_json


def test_empty_findings_emits_full_schema(empty_findings):
    payload = json.loads(render_json(empty_findings))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert set(payload["findings"]) == {
        "missing-required",
        "added-forbidden",
        "added-unspecified",
        "unresolved",
        "within-spec",
    }
    for items in payload["findings"].values():
        assert items == []
    assert payload["summary"]["high_total"] == 0
    assert payload["summary"]["drift_total"] == 0


def test_schema_v1_shape(mixed_findings):
    payload = json.loads(render_json(mixed_findings))
    assert payload["schema_version"] == 1
    assert payload["summary"] == {
        "missing_required": 2,
        "added_forbidden": 1,
        "added_unspecified": 2,
        "unresolved": 1,
        "within_spec": 1,
        "high_total": 3,
        "drift_total": 2,
    }


def test_missing_required_serializes_required_key(mixed_findings):
    payload = json.loads(render_json(mixed_findings))
    first = payload["findings"]["missing-required"][0]
    assert first["kind"] == "missing-required"
    assert first["severity"] == "high"
    assert first["file"] is None
    assert first["line"] is None
    assert first["required_key"] == {
        "category": "network.outbound",
        "parameter": "api.example.com",
        "scope": None,
    }


def test_observation_finding_includes_metadata(mixed_findings):
    payload = json.loads(render_json(mixed_findings))
    unresolved = payload["findings"]["unresolved"][0]
    assert unresolved["metadata"] == {"unresolved_reason": "dynamic-fstring"}
    assert unresolved["file"] == "src/dyn.py"
    assert unresolved["line"] == 9


def test_deterministic_output(mixed_findings):
    a = render_json(mixed_findings)
    b = render_json(mixed_findings)
    assert a == b
    # sort_keys ensures byte-stable shape
    assert a == json.dumps(json.loads(a), indent=2, sort_keys=True)


def test_no_extraneous_optional_fields(empty_findings, mixed_findings):
    forbidden = json.loads(render_json(mixed_findings))["findings"]["added-forbidden"][0]
    assert "tags" not in forbidden  # empty tags omitted
    assert "metadata" not in forbidden
    assert "required_key" not in forbidden
