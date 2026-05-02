from __future__ import annotations

from pathlib import Path

import pytest

from spectate.critique import RequiredKey, SpecMatchers, compile_spec
from spectate.observations import UNRESOLVED, Observation
from spectate.spec import Spec, validate

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples" / "specs"
EXAMPLE_FILES = sorted(p.name for p in EXAMPLES_DIR.glob("*.yaml"))


def _load_spec(filename: str) -> Spec:
    text = (EXAMPLES_DIR / filename).read_text()
    result = validate(text)
    assert result.ok, [(e.path, e.message) for e in result.errors]
    assert result.spec is not None
    return result.spec


def _obs(category: str, parameter: str, file: str = "src/app.py", line: int = 1) -> Observation:
    return Observation(category=category, parameter=parameter, file=Path(file), line=line)


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_compile_each_example_spec(filename: str) -> None:
    spec = _load_spec(filename)
    matchers = compile_spec(spec)
    assert isinstance(matchers, SpecMatchers)


def test_empty_spec_classifies_everything_unspecified() -> None:
    spec = Spec(version=1)
    matchers = compile_spec(spec)
    assert matchers.all_required_keys() == ()
    obs = _obs("network.outbound", "api.example.com")
    assert matchers.classify(obs) == "unspecified"
    assert matchers.matched_required(obs) == ()


def test_host_glob_matches_subdomain_and_rejects_other_apex() -> None:
    spec = _load_spec("comprehensive.yaml")
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("network.outbound", "api.example.com")) in {
        "required",
        "allowed",
    }
    assert matchers.classify(_obs("network.outbound", "edge.example.com")) == "allowed"
    assert matchers.classify(_obs("network.outbound", "example.org")) == "unspecified"


def test_host_glob_is_case_insensitive() -> None:
    spec = _load_spec("comprehensive.yaml")
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("network.outbound", "EDGE.Example.COM")) == "allowed"


def test_path_glob_matches_under_prefix_and_rejects_outside() -> None:
    spec_text = """
version: 1
fs:
  read:
    allowed:
      - "/var/log/**"
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("fs.read", "/var/log/cache/x.bin")) == "allowed"
    assert matchers.classify(_obs("fs.read", "/etc/passwd")) == "unspecified"


def test_path_glob_forbidden_takes_precedence_over_allowed() -> None:
    spec_text = """
version: 1
fs:
  write:
    allowed:
      - "/tmp/**"
    forbidden:
      - "/tmp/secret/**"
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("fs.write", "/tmp/ok.txt")) == "allowed"
    assert matchers.classify(_obs("fs.write", "/tmp/secret/key")) == "forbidden"


def test_imports_env_db_match_exact_only() -> None:
    spec_text = """
version: 1
imports:
  allowed:
    - requests
env:
  read:
    allowed:
      - HOME
db:
  read:
    allowed:
      - users
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("imports", "requests")) == "allowed"
    assert matchers.classify(_obs("imports", "requests-toolbelt")) == "unspecified"
    assert matchers.classify(_obs("env.read", "HOME")) == "allowed"
    assert matchers.classify(_obs("env.read", "HOMEDIR")) == "unspecified"
    assert matchers.classify(_obs("db.read", "users")) == "allowed"
    assert matchers.classify(_obs("db.read", "user")) == "unspecified"


def test_subprocess_wildcard_matches_all_binaries() -> None:
    spec_text = """
version: 1
subprocess:
  allowed:
    - "*"
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("subprocess", "git")) == "allowed"
    assert matchers.classify(_obs("subprocess", "anything")) == "allowed"


def test_subprocess_exact_does_not_glob() -> None:
    spec_text = """
version: 1
subprocess:
  allowed:
    - git
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("subprocess", "git")) == "allowed"
    assert matchers.classify(_obs("subprocess", "git-lfs")) == "unspecified"


def test_strongest_slot_forbidden_wins_over_allowed() -> None:
    spec_text = """
version: 1
network:
  outbound:
    allowed:
      - "*.example.com"
    forbidden:
      - api.example.com
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("network.outbound", "api.example.com")) == "forbidden"
    assert matchers.classify(_obs("network.outbound", "edge.example.com")) == "allowed"


def test_strongest_slot_required_wins_over_allowed() -> None:
    spec_text = """
version: 1
imports:
  required:
    - requests
  allowed:
    - requests
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    assert matchers.classify(_obs("imports", "requests")) == "required"


def test_required_key_tracking_unconditional() -> None:
    spec = _load_spec("comprehensive.yaml")
    matchers = compile_spec(spec)
    keys = matchers.all_required_keys()
    assert RequiredKey("imports", "requests", None) in keys
    assert RequiredKey("network.outbound", "api.example.com", None) in keys
    assert RequiredKey("env.read", "OPENAI_API_KEY", None) in keys
    obs = _obs("imports", "requests")
    assert matchers.matched_required(obs) == (RequiredKey("imports", "requests", None),)


def test_all_required_keys_enumerates_every_category() -> None:
    spec = _load_spec("comprehensive.yaml")
    matchers = compile_spec(spec)
    categories = {key.category for key in matchers.all_required_keys()}
    assert categories == {
        "network.outbound",
        "fs.read",
        "fs.write",
        "subprocess",
        "imports",
        "env.read",
        "db.read",
        "db.write",
    }


def test_required_keys_are_ordered_deterministically() -> None:
    spec = _load_spec("comprehensive.yaml")
    matchers = compile_spec(spec)
    keys = matchers.all_required_keys()
    assert list(keys) == sorted(keys, key=lambda k: (k.category, k.parameter, k.scope or ""))


def test_scoped_required_matches_only_inside_handler_file() -> None:
    spec = _load_spec("per_handler.yaml")
    matchers = compile_spec(spec)
    inside = Observation(
        category="subprocess",
        parameter="session-check",
        file=Path("/abs/repo/auth/views.py"),
        line=10,
    )
    outside = Observation(
        category="subprocess",
        parameter="session-check",
        file=Path("/abs/repo/auth/other.py"),
        line=10,
    )
    inside_keys = matchers.matched_required(inside)
    assert RequiredKey("subprocess", "session-check", "auth/views.py::login") in inside_keys
    assert matchers.matched_required(outside) == ()


def test_scoped_required_distinct_keys_per_handler() -> None:
    spec = _load_spec("per_handler.yaml")
    matchers = compile_spec(spec)
    keys = [k for k in matchers.all_required_keys() if k.category == "subprocess"]
    assert len(keys) == 3
    assert all(k.parameter == "session-check" for k in keys)
    assert {k.scope for k in keys} == {
        "auth/views.py::login",
        "auth/views.py::logout",
        "auth/views.py::reset_password",
    }


def test_unresolved_observation_is_unspecified_and_records_no_required() -> None:
    spec = _load_spec("comprehensive.yaml")
    matchers = compile_spec(spec)
    obs = _obs("imports", UNRESOLVED)
    assert matchers.classify(obs) == "unspecified"
    assert matchers.matched_required(obs) == ()


def test_matched_required_independent_of_classify_for_forbidden_overlap() -> None:
    spec_text = """
version: 1
imports:
  required:
    - pickle
  forbidden:
    - pickle
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    obs = _obs("imports", "pickle")
    assert matchers.classify(obs) == "forbidden"
    assert matchers.matched_required(obs) == (RequiredKey("imports", "pickle", None),)


def test_path_glob_matches_relative_pattern_against_relative_observation() -> None:
    spec_text = """
version: 1
fs:
  read:
    required:
      - config.yaml
"""
    spec = validate(spec_text).spec
    assert spec is not None
    matchers = compile_spec(spec)
    obs = _obs("fs.read", "config.yaml")
    assert matchers.matched_required(obs) == (RequiredKey("fs.read", "config.yaml", None),)
