from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError as PydanticValidationError

from spectate.spec.models import Spec, load_schema

_KNOWN_TOP_LEVEL = {
    "version",
    "unresolved_handling",
    "stdlib_auto_allow",
    "network",
    "fs",
    "subprocess",
    "imports",
    "env",
    "db",
}
_KNOWN_SUBKEYS: dict[str, set[str]] = {
    "network": {"outbound"},
    "fs": {"read", "write"},
    "env": {"read"},
    "db": {"read", "write"},
}
_KNOWN_SLOTS = {"required", "allowed", "forbidden"}


@dataclass(frozen=True)
class SpecError:
    path: str
    message: str
    suggestion: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    spec: Spec | None = None
    errors: list[SpecError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.spec is not None and not self.errors

    def __bool__(self) -> bool:
        return self.ok


def _format_path(parts: list[Any]) -> str:
    if not parts:
        return "$"
    out = "$"
    for p in parts:
        if isinstance(p, int):
            out += f"[{p}]"
        else:
            out += f".{p}"
    return out


def _suggest(unknown: str, candidates: set[str]) -> str | None:
    matches = difflib.get_close_matches(unknown, candidates, n=1, cutoff=0.6)
    if matches:
        return f"did you mean {matches[0]!r}?"
    return None


def _suggestion_for_jsonschema(path: list[Any], message: str) -> str | None:
    if "Additional properties are not allowed" not in message:
        return None
    start = message.find("(")
    end = message.find(" was unexpected")
    if start < 0 or end < 0:
        return None
    raw = message[start + 1 : end].strip()
    unknown = raw.split(",")[0].strip().strip("'\"")
    if not unknown:
        return None
    if not path:
        return _suggest(unknown, _KNOWN_TOP_LEVEL)
    head = path[0]
    if isinstance(head, str) and head in _KNOWN_SUBKEYS and len(path) == 1:
        return _suggest(unknown, _KNOWN_SUBKEYS[head])
    return _suggest(unknown, _KNOWN_SLOTS)


def _from_jsonschema_errors(validator: Draft202012Validator, data: Any) -> list[SpecError]:
    errors: list[SpecError] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = list(err.absolute_path)
        errors.append(
            SpecError(
                path=_format_path(path),
                message=err.message,
                suggestion=_suggestion_for_jsonschema(path, err.message),
            )
        )
    return errors


def _from_pydantic_error(err: PydanticValidationError) -> list[SpecError]:
    return [SpecError(path=_format_path(list(e["loc"])), message=e["msg"]) for e in err.errors()]


def validate(yaml_text: str) -> ValidationResult:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return ValidationResult(errors=[SpecError(path="$", message=f"invalid YAML: {exc}")])

    if not isinstance(data, dict):
        return ValidationResult(errors=[SpecError(path="$", message="Spec root must be a mapping")])

    validator = Draft202012Validator(load_schema())
    errors = _from_jsonschema_errors(validator, data)

    try:
        spec = Spec.model_validate(data)
    except PydanticValidationError as exc:
        errors.extend(_from_pydantic_error(exc))
        return ValidationResult(errors=_dedupe(errors))

    if errors:
        return ValidationResult(errors=_dedupe(errors))
    return ValidationResult(spec=spec)


def _dedupe(errors: list[SpecError]) -> list[SpecError]:
    seen: set[tuple[str, str]] = set()
    out: list[SpecError] = []
    for e in errors:
        key = (e.path, e.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
