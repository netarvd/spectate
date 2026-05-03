from __future__ import annotations

from spectate.bulletin.markdown import render_markdown


def test_empty_findings_positive_banner(empty_findings):
    out = render_markdown(empty_findings)
    assert "no drift detected" in out.lower()
    assert "<details>" not in out


def test_summary_banner_present(mixed_findings):
    out = render_markdown(mixed_findings)
    first_line = out.splitlines()[0]
    assert first_line.startswith("**Spectate found")
    assert "3 high-severity issues" in first_line
    assert "2 drift items" in first_line
    assert "1 unresolved" in first_line


def test_collapsible_sections(mixed_findings):
    out = render_markdown(mixed_findings)
    assert out.count("<details>") == 5  # one per non-empty bucket
    assert "<summary>missing-required (2 high)" in out
    assert "<summary>added-forbidden (1 high)" in out


def test_summary_only_returns_just_banner(mixed_findings):
    out = render_markdown(mixed_findings, summary_only=True)
    assert "<details>" not in out
    assert out.startswith("**Spectate found")


def test_observation_lines_have_file_and_param(mixed_findings):
    out = render_markdown(mixed_findings)
    assert "`src/app.py:12`" in out
    assert "`network.outbound(evil.example.com)`" in out


def test_missing_required_includes_scope(mixed_findings):
    out = render_markdown(mixed_findings)
    assert "scope: `jobs/run.py::main`" in out


def test_unresolved_reason_rendered(mixed_findings):
    out = render_markdown(mixed_findings)
    assert "dynamic-fstring" in out
