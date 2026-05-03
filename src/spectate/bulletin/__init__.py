"""Bulletin — output formatters for Critique Findings.

Three renderers, one per surface:

- `render_terminal` — colored, sectioned text for an interactive shell.
- `render_json`     — stable, schema-versioned JSON for tooling.
- `render_markdown` — GitHub-flavored markdown for PR comments.

Selection (terminal vs JSON vs markdown) is the CLI's job (T21); each
renderer here is pure: `Findings -> str`.
"""

from spectate.bulletin.json_format import render_json
from spectate.bulletin.markdown import render_markdown
from spectate.bulletin.terminal import render_terminal

__all__ = ["render_json", "render_markdown", "render_terminal"]
