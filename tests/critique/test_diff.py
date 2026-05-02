from __future__ import annotations

from pathlib import Path

from spectate.critique import Findings, RequiredKey, compile_spec, critique
from spectate.observations import UNRESOLVED, Observation
from spectate.spec import validate


def _obs(category: str, parameter: str, file: str = "src/app.py", line: int = 1) -> Observation:
    return Observation(category=category, parameter=parameter, file=Path(file), line=line)


def _spec(text: str):
    result = validate(text)
    assert result.ok, [(e.path, e.message) for e in result.errors]
    assert result.spec is not None
    return result.spec


SPEC_BASIC = """
version: 1
network:
  outbound:
    required:
      - api.example.com
    allowed:
      - cdn.example.com
    forbidden:
      - evil.example.com
"""


def test_all_four_buckets_fire() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    obs = [
        _obs("network.outbound", "api.example.com"),
        _obs("network.outbound", "cdn.example.com"),
        _obs("network.outbound", "evil.example.com"),
        _obs("network.outbound", "random.example.com"),
    ]
    findings = critique(obs, matchers)

    assert len(findings.added_forbidden) == 1
    assert findings.added_forbidden[0].observation is not None
    assert findings.added_forbidden[0].observation.parameter == "evil.example.com"
    assert findings.added_forbidden[0].severity == "high"

    assert len(findings.added_unspecified) == 1
    assert findings.added_unspecified[0].observation is not None
    assert findings.added_unspecified[0].observation.parameter == "random.example.com"
    assert findings.added_unspecified[0].severity == "drift"

    assert len(findings.within_spec) == 2
    for f in findings.within_spec:
        assert f.severity == "info"

    assert findings.missing_required == ()
    assert findings.unresolved == ()


def test_unresolved_bucket_skips_spec() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    obs = _obs("network.outbound", UNRESOLVED)
    findings = critique([obs], matchers)
    assert len(findings.unresolved) == 1
    assert findings.unresolved[0].observation is obs
    assert findings.unresolved[0].severity == "info"
    assert findings.added_unspecified == ()
    assert findings.within_spec == ()


def test_missing_required_when_no_observation() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    findings = critique([], matchers)
    assert len(findings.missing_required) == 1
    f = findings.missing_required[0]
    assert f.observation is None
    assert f.required_key == RequiredKey(
        category="network.outbound", parameter="api.example.com", scope=None
    )
    assert f.severity == "high"


def test_multiple_observations_satisfy_one_required_key_once() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    obs = [
        _obs("network.outbound", "api.example.com", file="src/a.py", line=1),
        _obs("network.outbound", "api.example.com", file="src/b.py", line=2),
        _obs("network.outbound", "api.example.com", file="src/c.py", line=3),
    ]
    findings = critique(obs, matchers)
    assert len(findings.within_spec) == 3
    assert findings.missing_required == ()


def test_empty_spec_routes_everything_to_unspecified_or_unresolved() -> None:
    spec = _spec("version: 1\n")
    matchers = compile_spec(spec)
    obs = [
        _obs("network.outbound", "api.example.com"),
        _obs("imports", "requests"),
        _obs("subprocess", UNRESOLVED),
    ]
    findings = critique(obs, matchers)
    assert len(findings.added_unspecified) == 2
    assert len(findings.unresolved) == 1
    assert findings.missing_required == ()
    assert findings.within_spec == ()
    assert findings.added_forbidden == ()


def test_empty_observations_yields_all_missing() -> None:
    spec_text = """
version: 1
network:
  outbound:
    required:
      - api.one.com
      - api.two.com
imports:
  required:
    - requests
"""
    matchers = compile_spec(_spec(spec_text))
    findings = critique([], matchers)
    assert len(findings.missing_required) == 3
    for f in findings.missing_required:
        assert f.observation is None
        assert f.required_key is not None
        assert f.severity == "high"


def test_forbidden_trumps_allowed() -> None:
    spec_text = """
version: 1
fs:
  write:
    allowed:
      - "/var/log/**"
    forbidden:
      - "/var/log/secret.log"
"""
    matchers = compile_spec(_spec(spec_text))
    obs = _obs("fs.write", "/var/log/secret.log")
    findings = critique([obs], matchers)
    assert len(findings.added_forbidden) == 1
    assert findings.within_spec == ()


def test_forbidden_observation_still_marks_required_seen() -> None:
    spec_text = """
version: 1
network:
  outbound:
    required:
      - api.example.com
    forbidden:
      - "*.example.com"
"""
    matchers = compile_spec(_spec(spec_text))
    obs = _obs("network.outbound", "api.example.com")
    findings = critique([obs], matchers)
    assert len(findings.added_forbidden) == 1
    assert findings.missing_required == ()


def test_determinism_same_input_same_buckets() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    obs = [
        _obs("network.outbound", "z.example.com", file="src/z.py"),
        _obs("network.outbound", "a.example.com", file="src/a.py"),
        _obs("network.outbound", "m.example.com", file="src/m.py"),
    ]
    a = critique(obs, matchers)
    b = critique(list(reversed(obs)), matchers)
    assert a == b
    params = [f.observation.parameter for f in a.added_unspecified if f.observation]
    assert params == sorted(params)


def test_has_violations_property() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    clean = critique([_obs("network.outbound", "api.example.com")], matchers)
    assert not clean.has_violations

    dirty = critique([_obs("network.outbound", "evil.example.com")], matchers)
    assert dirty.has_violations


def test_all_concatenates_in_bucket_order() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    obs = [
        _obs("network.outbound", "evil.example.com"),
        _obs("network.outbound", "random.example.com"),
        _obs("network.outbound", "cdn.example.com"),
        _obs("network.outbound", UNRESOLVED),
    ]
    findings = critique(obs, matchers)
    kinds = [f.kind for f in findings.all()]
    assert kinds == [
        "missing-required",
        "added-forbidden",
        "added-unspecified",
        "within-spec",
        "unresolved",
    ]


def test_observation_in_uncategorized_category_routes_to_unspecified() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    findings = critique([_obs("imports", "requests")], matchers)
    assert len(findings.added_unspecified) == 1
    assert findings.added_unspecified[0].observation is not None
    assert findings.added_unspecified[0].observation.category == "imports"


def test_findings_is_immutable() -> None:
    matchers = compile_spec(_spec(SPEC_BASIC))
    findings = critique([], matchers)
    assert isinstance(findings, Findings)
    import dataclasses

    assert dataclasses.is_dataclass(findings)
