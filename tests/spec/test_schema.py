from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError
from pydantic import ValidationError as PydanticValidationError

from spectate.spec import Spec, load_schema

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples" / "specs"
EXAMPLE_FILES = ["minimal.yaml", "per_handler.yaml", "comprehensive.yaml"]


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_validates_against_jsonschema(validator: Draft202012Validator, filename: str) -> None:
    data = _load(EXAMPLES_DIR / filename)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    assert errors == [], "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_validates_against_pydantic(filename: str) -> None:
    data = _load(EXAMPLES_DIR / filename)
    Spec.model_validate(data)


def test_per_handler_required_round_trips() -> None:
    spec = Spec.model_validate(_load(EXAMPLES_DIR / "per_handler.yaml"))
    handlers = {entry.handler for entry in spec.subprocess.required if not isinstance(entry, str)}
    assert handlers == {
        "auth/views.py::login",
        "auth/views.py::logout",
        "auth/views.py::reset_password",
    }


def test_comprehensive_covers_all_categories() -> None:
    spec = Spec.model_validate(_load(EXAMPLES_DIR / "comprehensive.yaml"))
    assert spec.network and spec.network.outbound
    assert spec.fs and spec.fs.read and spec.fs.write
    assert spec.subprocess and spec.imports
    assert spec.env and spec.env.read
    assert spec.db and spec.db.read and spec.db.write
    for slots in (
        spec.network.outbound,
        spec.fs.read,
        spec.fs.write,
        spec.subprocess,
        spec.imports,
        spec.env.read,
        spec.db.read,
        spec.db.write,
    ):
        assert slots.required and slots.allowed and slots.forbidden


# ---------------------------------------------------------------------------
# Invalid Specs
# ---------------------------------------------------------------------------


INVALID_SPECS: list[tuple[str, dict, str]] = [
    (
        "missing_version",
        {"network": {"outbound": {"allowed": ["api.example.com"]}}},
        "version",
    ),
    (
        "wrong_version",
        {"version": 2, "network": {"outbound": {"allowed": ["x"]}}},
        "version",
    ),
    (
        "unknown_top_level_key",
        {"version": 1, "filesystem": {"read": {"allowed": ["x"]}}},
        "filesystem",
    ),
    (
        "unknown_effect_subkey",
        {"version": 1, "network": {"inbound": {"allowed": ["x"]}}},
        "inbound",
    ),
    (
        "unknown_slot",
        {"version": 1, "imports": {"banned": ["pickle"]}},
        "banned",
    ),
    (
        "bad_unresolved_handling_enum",
        {"version": 1, "unresolved_handling": "ignore"},
        "unresolved_handling",
    ),
    (
        "scoped_required_missing_value",
        {
            "version": 1,
            "subprocess": {"required": [{"handler": "a.py::f"}]},
        },
        "required",
    ),
    (
        "allowed_must_be_strings",
        {"version": 1, "subprocess": {"allowed": [{"handler": "a.py::f", "value": "git"}]}},
        "string",
    ),
]


@pytest.mark.parametrize("name,payload,needle", INVALID_SPECS, ids=[c[0] for c in INVALID_SPECS])
def test_invalid_spec_rejected_by_jsonschema(
    validator: Draft202012Validator, name: str, payload: dict, needle: str
) -> None:
    errors = list(validator.iter_errors(payload))
    assert errors, f"expected {name} to fail validation"
    blob = " ".join(e.message for e in errors) + " " + " ".join(str(list(e.path)) for e in errors)
    assert needle.lower() in blob.lower(), f"expected error to mention {needle!r}; got: {blob}"


@pytest.mark.parametrize("name,payload,_needle", INVALID_SPECS, ids=[c[0] for c in INVALID_SPECS])
def test_invalid_spec_rejected_by_pydantic(name: str, payload: dict, _needle: str) -> None:
    with pytest.raises((PydanticValidationError, ValidationError)):
        Spec.model_validate(payload)
