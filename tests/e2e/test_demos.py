"""End-to-end demo fixture tests (T33).

Each fixture under ``tests/fixtures/<name>/`` ships a ``spec.yaml`` plus a
``clean.py`` (must pass review) and a ``violating.py`` (must trip a specific
Finding). These tests spawn the installed ``spectate`` CLI as a subprocess
and assert on the JSON Bulletin, proving the end-to-end pipeline works
against representative drift scenarios.

Marked ``e2e`` so they can be excluded from fast unit runs via
``pytest -m 'not e2e'``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"


@dataclass(frozen=True)
class DemoCase:
    name: str
    expected_violation_kind: str  # "added-unspecified" | "added-forbidden" | "missing-required"
    expected_category: str
    expected_parameter: str

    @property
    def fixture_dir(self) -> Path:
        return FIXTURES_ROOT / self.name

    @property
    def spec(self) -> Path:
        return self.fixture_dir / "spec.yaml"

    @property
    def clean(self) -> Path:
        return self.fixture_dir / "clean.py"

    @property
    def violating(self) -> Path:
        return self.fixture_dir / "violating.py"


CASES: tuple[DemoCase, ...] = (
    DemoCase("vanished_auth", "missing-required", "imports", "auth"),
    DemoCase("library_swap", "added-unspecified", "imports", "httpx"),
    DemoCase("new_outbound", "added-unspecified", "network.outbound", "telemetry.somerandom.dev"),
    DemoCase("persistent_state", "added-unspecified", "fs.write", "/var/log/.cache/state.bin"),
    DemoCase("subprocess", "added-unspecified", "subprocess", "git"),
    DemoCase("hardcoded_webhook", "added-unspecified", "network.outbound", "discord.com"),
    DemoCase("typosquat", "added-unspecified", "imports", "reqeusts"),
    DemoCase("stale_spec", "added-unspecified", "imports", "pydantic"),
)


def _spectate_bin() -> str:
    path = shutil.which("spectate")
    if path is None:
        pytest.skip("spectate CLI not on PATH; install with `pip install -e .[dev]`.")
    return path


def _run(case_path: Path, spec_path: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [_spectate_bin(), "review", str(case_path), "--spec", str(spec_path), "--json"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc.returncode, payload


@pytest.mark.e2e
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_clean_passes(case: DemoCase) -> None:
    code, payload = _run(case.clean, case.spec)
    assert code == 0, f"clean run failed; payload={payload}"
    assert payload["schema_version"] == 1
    findings = payload["findings"]
    assert findings["missing-required"] == []
    assert findings["added-forbidden"] == []
    assert findings["added-unspecified"] == []


@pytest.mark.e2e
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_violating_fires(case: DemoCase) -> None:
    code, payload = _run(case.violating, case.spec)
    assert code == 1, f"violating run did not exit 1; payload={payload}"
    bucket_key = case.expected_violation_kind  # already in dashed form
    bucket = payload["findings"][bucket_key]
    assert bucket, f"expected at least one {bucket_key} finding; payload={payload}"
    matches = [
        f
        for f in bucket
        if f["category"] == case.expected_category and f["parameter"] == case.expected_parameter
    ]
    assert matches, (
        f"no {bucket_key} finding matched "
        f"category={case.expected_category!r} parameter={case.expected_parameter!r}; "
        f"got bucket={bucket}"
    )
