"""Markdown renderer — GitHub-flavored output for PR comments.

Layout:

    **Spectate found N high-severity issues, M drift items, K unresolved**

    <details><summary>missing-required (N high) — blurb</summary>

    - `path/file.py:LN` — `category(parameter)` [scope: ...]
    - ...

    </details>

    <details><summary>added-forbidden ...</summary>...</details>
    ...

`summary_only=True` returns the banner alone, for compact comments. Empty
Findings render a single positive banner.
"""

from __future__ import annotations

from collections.abc import Sequence

from spectate.bulletin._common import (
    BUCKET_BLURB,
    BUCKET_ORDER,
    bucket_for,
    total_drift,
    total_high,
)
from spectate.critique.diff import Finding, FindingKind, Findings


def render_markdown(findings: Findings, *, summary_only: bool = False) -> str:
    """Render Findings as GitHub-flavored markdown for PR comments."""
    banner = _banner(findings)
    if summary_only or _is_empty(findings):
        return banner + "\n"

    parts: list[str] = [banner, ""]
    for kind in BUCKET_ORDER:
        items = bucket_for(findings, kind)
        if not items:
            continue
        parts.append(_section(kind, items))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _banner(findings: Findings) -> str:
    if _is_empty(findings):
        return "**Spectate: no drift detected.**"
    high = total_high(findings)
    drift = total_drift(findings)
    unresolved = len(findings.unresolved)
    return (
        f"**Spectate found {high} high-severity issue{_s(high)}, "
        f"{drift} drift item{_s(drift)}, {unresolved} unresolved**"
    )


def _section(kind: FindingKind, items: Sequence[Finding]) -> str:
    severity = items[0].severity
    header = f"{kind} ({len(items)} {severity}) — {BUCKET_BLURB[kind]}"
    body_lines = [f"- {_format_item(f)}" for f in items]
    body = "\n".join(body_lines)
    # Default closed: keep PR comments compact; reviewers expand on demand.
    return f"<details><summary>{header}</summary>\n\n{body}\n\n</details>"


def _format_item(finding: Finding) -> str:
    if finding.kind == "missing-required":
        key = finding.required_key
        assert key is not None
        scope = f" [scope: `{key.scope}`]" if key.scope else ""
        return f"`{key.category}({key.parameter})`{scope}"

    obs = finding.observation
    assert obs is not None
    location = f"`{obs.file.as_posix()}:{obs.line}`"
    base = f"{location} — `{obs.category}({obs.parameter})`"
    if finding.kind == "unresolved":
        reason = obs.metadata.get("unresolved_reason")
        if reason:
            base += f" _({reason})_"
    return base


def _is_empty(findings: Findings) -> bool:
    return not (
        findings.missing_required
        or findings.added_forbidden
        or findings.added_unspecified
        or findings.unresolved
        or findings.within_spec
    )


def _s(n: int) -> str:
    return "" if n == 1 else "s"
