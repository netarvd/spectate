"""Shared helpers for the three Bulletin renderers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spectate.critique.diff import Finding, FindingKind, Findings

# Bucket render order — matches the priority specified in T18-T20 brief and
# the severity gradient in ADR-0001 (high → drift → info).
BUCKET_ORDER: tuple[FindingKind, ...] = (
    "missing-required",
    "added-forbidden",
    "added-unspecified",
    "unresolved",
    "within-spec",
)

BUCKET_BLURB: dict[FindingKind, str] = {
    "missing-required": "declared required, absent from code",
    "added-forbidden": "declared forbidden, present in code",
    "added-unspecified": "present in code, not mentioned in Spec",
    "unresolved": "watcher could not resolve a parameter statically",
    "within-spec": "present and allowed (suppressed by default)",
}


def bucket_for(findings: Findings, kind: FindingKind) -> Sequence[Finding]:
    return {
        "missing-required": findings.missing_required,
        "added-forbidden": findings.added_forbidden,
        "added-unspecified": findings.added_unspecified,
        "within-spec": findings.within_spec,
        "unresolved": findings.unresolved,
    }[kind]


def total_high(findings: Findings) -> int:
    return len(findings.missing_required) + len(findings.added_forbidden)


def total_drift(findings: Findings) -> int:
    return len(findings.added_unspecified)
