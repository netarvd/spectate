# ADR-0003: Project skeleton and tooling

- **Status:** Accepted
- **Date:** 2026-04-26
- **Applies to:** Project layout, build backend, CLI framework, lint/type/test, CI
- **Supersedes:** —
- **PR:** [#2](https://github.com/netarvd/spectate/pull/2)

## Context

Spectate is a Python project distributed as a CLI tool. The bootstrap needed a packaging layout, CLI framework, lint/type/test tooling, and CI — chosen to minimize friction for both human developers and the subagents that will implement the rest of the codebase.

## Decision

| Aspect | Choice |
|---|---|
| Package layout | `src/` layout |
| Build backend | hatchling |
| CLI framework | Typer |
| Python minimum | 3.11 |
| Lint + format | ruff (curated rule set: E, W, F, I, B, UP, SIM, RUF, N, C4, PTH, TID, ARG) |
| Type checker | mypy `strict = true` on `src/`, `ignore_errors = true` on `tests/` |
| Test runner | pytest |
| CI | GitHub Actions matrix on Python 3.11 + 3.12 + 3.13, `fail-fast: false` |
| Dependency management | pip + venv (lockfile/uv deferred) |

Console entry point: `spectate = "spectate.cli:app"`. CLI exposes four top-level commands stubbed: `spec init`, `spec transcribe`, `review`, `accept`.

## Rationale

- **src layout** prevents accidental imports of in-tree code without installation; catches packaging bugs early.
- **hatchling** is simple, fast, and the de facto modern Python build backend.
- **Typer** wraps Click with type-hint-driven argument parsing — less boilerplate, same maturity.
- **Python 3.11** is the broadest reach with modern type-system features available.
- **Curated ruff rules** balance strictness with signal-to-noise; `ALL` is too noisy, defaults too lax.
- **Strict mypy on `src/` only** keeps production code honest without making test setup tedious.
- **Three-version CI matrix** catches version-specific regressions without exploding CI time.

## Consequences

**Enabled:** every subsequent code task has a working `pip install -e ".[dev]"` flow, a green CI baseline, and a CLI surface to plug into.

**Deferred:** uv / lockfile (revisit after MVP demo if reproducibility becomes an issue), pre-commit hook config (deferred to T23 which handles workflow integration).

**Locked-in defaults that are mildly opinionated:** strict mypy on `src/` will reject untyped code in production paths from day one. New contributors should expect to write type hints.

## Alternatives considered

- **CLI framework:** Click directly — more mature but more boilerplate. Argparse — too low-level for a multi-command tool.
- **Python minimum:** 3.12 — better PEP 695 type syntax but cuts off users on LTS distros. 3.10 — too many missing features.
- **Ruff rules:** defaults — too permissive; `ALL` — too many irrelevant rules to suppress.
- **Build backend:** setuptools — works but slower and more config-heavy. poetry — heavier and opinionated about dep management.
- **CI matrix:** single version (the minimum) — cheaper but misses 3.12/3.13 regressions.
