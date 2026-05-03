from __future__ import annotations

from pathlib import Path

import pytest

from spectate.critique.diff import Finding, Findings
from spectate.critique.expected import RequiredKey
from spectate.observations.observation import Observation


def _obs(category: str, parameter: str, file: str, line: int, **meta: str) -> Observation:
    return Observation(
        category=category,
        parameter=parameter,
        file=Path(file),
        line=line,
        tags=(),
        metadata=dict(meta),
    )


@pytest.fixture
def mixed_findings() -> Findings:
    """A Findings fixture with all five buckets populated."""
    missing = (
        Finding(
            kind="missing-required",
            observation=None,
            required_key=RequiredKey("network.outbound", "api.example.com", None),
            severity="high",
        ),
        Finding(
            kind="missing-required",
            observation=None,
            required_key=RequiredKey("env.read", "DATABASE_URL", "jobs/run.py::main"),
            severity="high",
        ),
    )
    forbidden = (
        Finding(
            kind="added-forbidden",
            observation=_obs("network.outbound", "evil.example.com", "src/app.py", 12),
            required_key=None,
            severity="high",
        ),
    )
    unspecified = (
        Finding(
            kind="added-unspecified",
            observation=_obs("subprocess", "curl", "src/util.py", 4),
            required_key=None,
            severity="drift",
        ),
        Finding(
            kind="added-unspecified",
            observation=_obs("imports", "requests", "src/app.py", 1),
            required_key=None,
            severity="drift",
        ),
    )
    within = (
        Finding(
            kind="within-spec",
            observation=_obs("imports", "json", "src/app.py", 2),
            required_key=None,
            severity="info",
        ),
    )
    unresolved = (
        Finding(
            kind="unresolved",
            observation=_obs(
                "network.outbound", "*", "src/dyn.py", 9, unresolved_reason="dynamic-fstring"
            ),
            required_key=None,
            severity="info",
        ),
    )
    return Findings(
        missing_required=missing,
        added_forbidden=forbidden,
        added_unspecified=unspecified,
        within_spec=within,
        unresolved=unresolved,
    )


@pytest.fixture
def empty_findings() -> Findings:
    return Findings(
        missing_required=(),
        added_forbidden=(),
        added_unspecified=(),
        within_spec=(),
        unresolved=(),
    )
