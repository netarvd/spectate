"""Claude Code PreToolUse hook for `spectate review`.

Reads a Claude Code hook payload on stdin. For PreToolUse on file-mutating
tools (Write, Edit, MultiEdit), runs Spectate review against the project's
.spectate/spec.yaml and emits Findings as `additionalContext` so the user
sees drift before the next agent action overwrites it.

Behavior:
  - No spec file -> silent no-op (exit 0, empty stdout).
  - Non file-mutating tool -> silent pass-through.
  - Clean review -> silent pass-through.
  - Drift / missing-required -> emits a JSON additionalContext payload.
  - Any unexpected error -> silent no-op (never block the agent on hook
    crashes; Spectate is a drift detector, not a security gate).

Latency target: < 1s on a clean repo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

WATCHED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})
SPEC_RELATIVE = Path(".spectate/spec.yaml")
HOOK_EVENT = "PreToolUse"


def _emit(payload: dict[str, Any] | None) -> None:
    if payload is not None:
        sys.stdout.write(json.dumps(payload))


def _project_root(cwd: str | None) -> Path:
    if cwd:
        return Path(cwd)
    return Path.cwd()


def _read_payload(stream: Any) -> dict[str, Any]:
    raw = stream.read()
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _summary_line(summary: dict[str, Any]) -> str:
    return (
        f"high={summary.get('high_total', 0)} "
        f"drift={summary.get('drift_total', 0)} "
        f"missing-required={summary.get('missing_required', 0)} "
        f"added-forbidden={summary.get('added_forbidden', 0)} "
        f"added-unspecified={summary.get('added_unspecified', 0)}"
    )


def _format_finding(f: dict[str, Any]) -> str:
    loc = ""
    if f.get("file"):
        loc = f" ({f['file']}"
        if f.get("line"):
            loc += f":{f['line']}"
        loc += ")"
    return f"  - [{f.get('kind')}] {f.get('category')} :: {f.get('parameter')}{loc}"


def _build_context(bulletin: dict[str, Any], spec_path: Path) -> str | None:
    summary = bulletin.get("summary", {})
    high = summary.get("high_total", 0)
    drift = summary.get("drift_total", 0)
    if high == 0 and drift == 0:
        return None

    findings = bulletin.get("findings", {})
    bullets: list[str] = []
    for kind in ("missing-required", "added-forbidden", "added-unspecified"):
        for f in findings.get(kind, [])[:5]:
            bullets.append(_format_finding(f))

    header = (
        f"Spectate detected drift against {spec_path.as_posix()} "
        f"({_summary_line(summary)}). Run `spectate review` for the full bulletin."
    )
    if not bullets:
        return header
    return header + "\n" + "\n".join(bullets)


def _run_review(project_root: Path, spec_path: Path) -> dict[str, Any] | None:
    """Run Spectate review in-process. Returns the JSON bulletin dict, or None on failure."""
    try:
        import spectate.watchers  # noqa: F401  populates the Watcher registry
        from spectate.bulletin import render_json
        from spectate.critique.diff import critique
        from spectate.critique.expected import compile_spec
        from spectate.observations.aggregate import aggregate
        from spectate.spec import validate
    except Exception:
        return None

    try:
        spec_text = spec_path.read_text()
        result = validate(spec_text)
        if not result.ok or result.spec is None:
            return None
        observations = aggregate(project_root)
        matchers = compile_spec(result.spec)
        findings = critique(observations, matchers)
        return json.loads(render_json(findings))  # type: ignore[no-any-return]
    except Exception:
        return None


def process(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pure entrypoint suitable for tests. Returns the JSON dict to write to
    stdout, or None for a silent pass-through."""
    if payload.get("hook_event_name") != HOOK_EVENT:
        return None
    tool_name = payload.get("tool_name")
    if tool_name not in WATCHED_TOOLS:
        return None

    project_root = _project_root(payload.get("cwd"))
    spec_path = project_root / SPEC_RELATIVE
    if not spec_path.exists():
        return None

    bulletin = _run_review(project_root, spec_path)
    if bulletin is None:
        return None

    context = _build_context(bulletin, spec_path)
    if context is None:
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "additionalContext": context,
        }
    }


def main() -> int:
    try:
        payload = _read_payload(sys.stdin)
        out = process(payload)
        _emit(out)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
