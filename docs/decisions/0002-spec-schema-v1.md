# ADR-0002: Spec YAML schema v1

- **Status:** Accepted
- **Date:** 2026-04-26
- **Applies to:** Spec schema v1 (`src/spectate/spec/spec.schema.json`, `src/spectate/spec/models.py`)
- **Supersedes:** —
- **PR:** [#3](https://github.com/netarvd/spectate/pull/3)

## Context

The Spec is the developer's articulated intent — the closed-world contract for what the code may, must, and must not do. Both humans and LLMs author it; the rest of Spectate consumes it. The schema needs to be writable, parseable, validatable, and forward-compatible.

## Decision

JSONSchema (draft 2020-12) at `src/spectate/spec/spec.schema.json`, with mirrored pydantic v2 models at `src/spectate/spec/models.py`. The Spec lives at `.spectate/spec.yaml` in each repo. Every Spec carries `version: 1` at the top.

Each effect category from ADR-0001 has three optional slots: `required`, `allowed`, `forbidden`. Closed-world enforcement:

- `required` absent in code → `missing-required` Finding (high severity).
- `forbidden` present in code → `added-forbidden` Finding (high severity).
- Effect present and not in `required` / `allowed` (and not auto-allowed via stdlib config) → `added-unspecified` Finding (drift severity).

### Sub-decisions locked in v1

1. **Per-handler scope syntax:** pytest nodeid style — `path/file.py::function_name`. Bare `function_name` is a shortcut for any-file match. `path/file.py::*` matches all functions in a file.
2. **Effect-key shape inside slots:** nested by category — e.g. `network.outbound.allowed: [...]`. Chosen over flat-dotted keys and typed-object lists.
3. **Spec file location:** `.spectate/spec.yaml` (per-repo, single file).
4. **Wildcard `*` semantics:** the schema treats slot values as opaque strings. Match semantics (`*` as wildcard, glob behavior) live in the matcher (T16, The Critique stage), not the schema.

## Rationale

Pytest nodeid is familiar to most Python devs and resolves the file-vs-function disambiguation cleanly. Nested-by-category mirrors how developers think about effects ("everything network-related goes here"). Locating the Spec at `.spectate/spec.yaml` follows the convention pattern set by `.github/`, `.vscode/`, etc. Pushing wildcard semantics out of the schema keeps the schema simple and lets the matcher evolve independently.

## Consequences

**Enabled:** T04 (English→Spec prompt) has a stable target shape. T06 (Spec validator), T16 (Spec→Observations normalizer), and T17 (Critique algorithm) all derive from this schema directly.

**Forbidden at v1:** multi-file Specs (no per-service splits), alternative scope addressing (decorators, glob over directories), schema-level pattern matching.

**Forward-compat:** the `version: 1` field allows schema evolution. Adding new optional fields doesn't bump; breaking changes do and trigger a new superseding ADR.

## Alternatives considered

- **Per-handler scope:** decorator marker (`@spectate.handler("name")`) — rejected because it requires importing Spectate into application code; coupling.
- **Effect-key shape:** flat dotted (`allowed: { "network.outbound": [...] }`) — rejected for harder-to-skim layout. Typed object list (`allowed: [{ effect: "network.outbound", value: "..." }]`) — rejected for verbosity.
- **Spec location:** project-root `spectate.yaml` — rejected; clutters root. Inside `pyproject.toml` — rejected; couples Spec to Python tooling and breaks language-agnostic story.
- **Schema-level glob enforcement:** force `*` only in specific positions — rejected; couples schema to matcher logic.
