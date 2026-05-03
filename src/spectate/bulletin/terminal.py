"""Terminal renderer — colored, sectioned text for an interactive shell."""

from __future__ import annotations

from collections.abc import Sequence
from io import StringIO

from rich.console import Console
from rich.text import Text

from spectate.bulletin._common import BUCKET_BLURB, BUCKET_ORDER, bucket_for
from spectate.critique.diff import Finding, FindingKind, Findings

_BUCKET_STYLE: dict[FindingKind, str] = {
    "missing-required": "bold red",
    "added-forbidden": "bold red",
    "added-unspecified": "yellow",
    "unresolved": "cyan",
    "within-spec": "dim",
}


def render_terminal(findings: Findings, *, color: bool = True) -> str:
    """Render Findings as grouped, prioritized sections for terminals.

    Sections appear in fixed priority order: missing-required,
    added-forbidden, added-unspecified, unresolved, within-spec. Each
    section header is `bucket-name (count severity) — blurb`. Empty
    buckets are omitted. Empty Findings render a single positive line.

    `color=False` returns plain text suitable for piping.
    """
    if _is_empty(findings):
        return "No drift detected."

    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=color,
        no_color=not color,
        width=120,
        highlight=False,
        emoji=False,
        legacy_windows=False,
    )

    first = True
    for kind in BUCKET_ORDER:
        items = bucket_for(findings, kind)
        if not items:
            continue
        if not first:
            console.print()
        first = False
        _render_section(console, kind, items)

    return buf.getvalue().rstrip("\n") + "\n"


def _render_section(console: Console, kind: FindingKind, items: Sequence[Finding]) -> None:
    severity = items[0].severity
    header = Text()
    header.append(kind, style=_BUCKET_STYLE[kind])
    header.append(f" ({len(items)} {severity})", style="bold")
    header.append(f" — {BUCKET_BLURB[kind]}")
    console.print(header)
    for f in items:
        console.print(_format_line(f))


def _format_line(finding: Finding) -> Text:
    line = Text("  ")
    if finding.kind == "missing-required":
        key = finding.required_key
        assert key is not None
        scope = f" [scope: {key.scope}]" if key.scope else ""
        line.append(f"{key.category}({key.parameter}){scope}", style="red")
        return line

    obs = finding.observation
    assert obs is not None
    location = f"{obs.file.as_posix()}:{obs.line}"
    line.append(location, style="dim")
    line.append("  ")
    line.append(f"{obs.category}({obs.parameter})")
    if finding.kind == "unresolved":
        reason = obs.metadata.get("unresolved_reason")
        if reason:
            line.append(f"  [{reason}]", style="cyan")
    return line


def _is_empty(findings: Findings) -> bool:
    return not (
        findings.missing_required
        or findings.added_forbidden
        or findings.added_unspecified
        or findings.unresolved
        or findings.within_spec
    )
