from __future__ import annotations

from spectate.bulletin.terminal import render_terminal


def test_empty_findings_returns_positive_message(empty_findings):
    assert render_terminal(empty_findings) == "No drift detected."


def test_renders_all_buckets_in_priority_order(mixed_findings):
    out = render_terminal(mixed_findings, color=False)
    # Section headers in the right order.
    order = [
        "missing-required",
        "added-forbidden",
        "added-unspecified",
        "unresolved",
        "within-spec",
    ]
    positions = [out.index(name) for name in order]
    assert positions == sorted(positions)


def test_missing_required_shows_required_key(mixed_findings):
    out = render_terminal(mixed_findings, color=False)
    assert "network.outbound(api.example.com)" in out
    assert "env.read(DATABASE_URL)" in out
    assert "scope: jobs/run.py::main" in out


def test_observation_lines_show_file_and_line(mixed_findings):
    out = render_terminal(mixed_findings, color=False)
    assert "src/app.py:12" in out
    assert "subprocess(curl)" in out


def test_unresolved_includes_reason(mixed_findings):
    out = render_terminal(mixed_findings, color=False)
    assert "dynamic-fstring" in out


def test_color_off_produces_no_ansi(mixed_findings):
    out = render_terminal(mixed_findings, color=False)
    assert "\x1b[" not in out


def test_color_on_includes_ansi(mixed_findings):
    out = render_terminal(mixed_findings, color=True)
    assert "\x1b[" in out


def test_section_count_in_header(mixed_findings):
    out = render_terminal(mixed_findings, color=False)
    assert "(2 high)" in out  # missing-required has 2
    assert "(1 high)" in out  # added-forbidden has 1
    assert "(2 drift)" in out  # added-unspecified has 2
