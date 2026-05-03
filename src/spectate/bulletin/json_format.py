"""JSON renderer — stable, schema-versioned output for tooling.

Schema (version 1):

    {
      "schema_version": 1,
      "summary": {
        "missing_required": <int>,
        "added_forbidden": <int>,
        "added_unspecified": <int>,
        "unresolved": <int>,
        "within_spec": <int>,
        "high_total": <int>,
        "drift_total": <int>
      },
      "findings": {
        "missing-required": [Finding, ...],
        "added-forbidden":  [Finding, ...],
        "added-unspecified":[Finding, ...],
        "unresolved":       [Finding, ...],
        "within-spec":      [Finding, ...]
      }
    }

Each Finding object has:

    {
      "kind":      <bucket name>,
      "severity":  "high" | "drift" | "info",
      "category":  <effect category, e.g. "network.outbound">,
      "parameter": <observed/required value>,
      "file":      <POSIX path or null>,
      "line":      <int or null>,
      "tags":      [<str>, ...]   # optional, present iff non-empty
      "metadata":  {<str>: <str>} # optional, present iff non-empty
      "required_key": {           # present iff kind == "missing-required"
        "category": <str>,
        "parameter": <str>,
        "scope": <str or null>
      }
    }

Output is `json.dumps(..., indent=2, sort_keys=True)` for byte-stable
diffs. Empty Findings still emit the full schema with empty lists.
"""

from __future__ import annotations

import json
from typing import Any

from spectate.bulletin._common import bucket_for, total_drift, total_high
from spectate.critique.diff import Finding, Findings

SCHEMA_VERSION = 1

_BUCKET_KEYS = (
    "missing-required",
    "added-forbidden",
    "added-unspecified",
    "unresolved",
    "within-spec",
)


def render_json(findings: Findings) -> str:
    """Serialize Findings to deterministic JSON. See module docstring for schema."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "missing_required": len(findings.missing_required),
            "added_forbidden": len(findings.added_forbidden),
            "added_unspecified": len(findings.added_unspecified),
            "unresolved": len(findings.unresolved),
            "within_spec": len(findings.within_spec),
            "high_total": total_high(findings),
            "drift_total": total_drift(findings),
        },
        "findings": {
            kind: [_finding_to_dict(f) for f in bucket_for(findings, kind)]  # type: ignore[arg-type]
            for kind in _BUCKET_KEYS
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": finding.kind,
        "severity": finding.severity,
    }
    if finding.observation is not None:
        obs = finding.observation
        out["category"] = obs.category
        out["parameter"] = obs.parameter
        out["file"] = obs.file.as_posix()
        out["line"] = obs.line
        if obs.tags:
            out["tags"] = list(obs.tags)
        if obs.metadata:
            out["metadata"] = dict(obs.metadata)
    else:
        key = finding.required_key
        assert key is not None
        out["category"] = key.category
        out["parameter"] = key.parameter
        out["file"] = None
        out["line"] = None

    if finding.required_key is not None:
        key = finding.required_key
        out["required_key"] = {
            "category": key.category,
            "parameter": key.parameter,
            "scope": key.scope,
        }
    return out
