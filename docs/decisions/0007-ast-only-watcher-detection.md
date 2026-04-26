# ADR-0007: AST-only Watcher detection at v1; Semgrep deferred

- **Status:** Accepted
- **Date:** 2026-04-27
- **Applies to:** The Watch stage — all Watchers (T09–T14 and future)
- **Supersedes:** —
- **PRs:** [#13](https://github.com/netarvd/spectate/pull/13), [#14](https://github.com/netarvd/spectate/pull/14), [#15](https://github.com/netarvd/spectate/pull/15), [#16](https://github.com/netarvd/spectate/pull/16), [#17](https://github.com/netarvd/spectate/pull/17), [#18](https://github.com/netarvd/spectate/pull/18)

## Context

The original Notion task DoDs for T09–T14 specified "Semgrep + AST as appropriate" as the detection mechanism for each Watcher. When the six Watchers were implemented, all six agents converged on **pure stdlib `ast`**-based detection without invoking Semgrep. This ADR is a retroactive lock — capturing the decision that was made implicitly so future Watchers (and any reconsideration) have a documented rationale rather than a silent drift.

## Decision

All v1 Watchers use Python's stdlib `ast` module for detection. Semgrep is **not** a runtime dependency of Spectate.

External libraries are used only when stdlib is genuinely insufficient: SqlWatcher uses `sqlglot` for SQL parsing (no stdlib equivalent); ImportsWatcher uses `sys.stdlib_module_names` (stdlib); NetworkWatcher uses `urllib.parse` (stdlib).

## Rationale

For Spectate's v1 use case — Python-only, narrow literal-extraction patterns at specific call sites — `ast` is strictly better than Semgrep:

- **Self-contained.** No external binary, no subprocess invocation per file, no packaging story for the Semgrep CLI.
- **Faster.** AST parsing happens in-process; Semgrep boots a JVM-or-equivalent runtime per invocation.
- **More precise for our patterns.** Watchers need to walk specific call-argument structures (e.g. "the first positional arg of `requests.get` if it's a string literal"); this is what `ast` is for. Semgrep's pattern language can express most of these but adds an indirection.
- **No new learning curve.** Every Watcher author (human or agent) knows `ast`; Semgrep YAML rule syntax is one more thing to learn.

Semgrep would become attractive if any of the following emerge:

- **Cross-language support.** Watchers for JavaScript, Go, Rust, etc. (Spectate is Python-only at v1.)
- **User-authored Watchers.** If end users want to write their own detection rules, Semgrep YAML is more accessible than writing a Python AST visitor.
- **Distribution as a non-Python tool.** If Spectate ships a single binary that doesn't bundle Python.

None of these are v1 concerns.

## Consequences

**Enabled.** Watcher implementations are short (50–250 LOC each), self-contained Python, and have zero non-Python runtime dependencies (sqlglot is the lone exception, and it's pip-installable).

**Forbidden until reconsidered.** No Watcher may shell out to Semgrep, semgrep-core, or any other non-Python AST tool. If a future Watcher needs more than `ast` provides, prefer `astroid` (stronger name resolution, still Python) or `libcst` (concrete syntax tree) before reaching for Semgrep.

**Library reuse posture.** Watcher authors should briefly enumerate existing-library options before writing custom AST traversal (e.g. `findimports` for ImportsWatcher, `bandit`'s rule pack for subprocess detection). Reuse only when the library does what's needed without imposing significant deps; otherwise stdlib `ast` remains the default.

## Alternatives considered

- **Semgrep + AST hybrid (the original DoD).** Rejected for v1 — Semgrep's value (cross-language, declarative rules) doesn't pay off on a Python-only narrow-pattern surface.
- **`astroid` from day one.** Rejected — stronger name resolution would help NetworkWatcher's session-detection accuracy, but the v1 NetworkWatcher's "emit unresolved on variable receivers" pattern is honest and acceptable. Reconsider if accuracy gaps surface.
- **`libcst`.** Rejected — concrete syntax tree is overkill for read-only analysis; we don't preserve formatting.
- **Custom regex-based detection.** Rejected at design time; never seriously considered. AST gives us free correctness on syntax-level concerns.
