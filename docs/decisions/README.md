# Architecture Decision Records

Immutable records of decisions about what Spectate does and doesn't support.

## Conventions

- **Numbered sequentially.** `0001-`, `0002-`, etc. Numbers are never reused.
- **Immutable once merged.** The only post-merge edit allowed is changing the `Status` line and adding a brief "Superseded by ADR-XXXX" note.
- **One decision unit per file.** A "unit" is the locked v1 (or vN) state of a coherent component (taxonomy, schema, tooling). Sub-decisions inside a unit are listed within the same ADR, not split out.
- **Status values:** `Proposed` (in-flight PR), `Accepted` (merged, in effect), `Superseded by ADR-XXXX`, `Deprecated`.
- **Applies to.** Each ADR names the component(s) and version(s) it constrains.

## Versioning policy

Spectate has two version tracks that evolve independently:

1. **Taxonomy version** — header in `docs/taxonomy.md`. Effect categories, normalized forms, match semantics.
2. **Spec schema version** — `version: N` field at the top of every Spec YAML; enforced by `src/spectate/spec/spec.schema.json`.

Within a major version, **additions that are backward-compatible** (new optional fields, new effect categories) do not bump. **Breaking changes** (removing/renaming a field, changing match semantics, changing default behavior in a way that would re-flag previously-clean code) bump the version and trigger a new superseding ADR.

When a decision is reversed:
1. Write a new ADR with the next free number.
2. The new ADR's `Supersedes` line points at the old ADR.
3. The old ADR's `Status` is updated to `Superseded by ADR-XXXX` (the only allowed edit).
4. If the change is breaking, bump the relevant component version in the new ADR's `Applies to` line.

## Adding a new ADR

When a decision raised in a PR is locked (user review or merge):

1. Copy `0000-template.md` to `XXXX-short-title.md` using the next free number.
2. Fill in Context, Decision, Rationale, Consequences, Alternatives considered.
3. Link the PR that locked the decision.
4. Land the ADR in the same PR if practical, otherwise in a follow-up PR — but never silently.

This is a project-wide working rule. See `CLAUDE.md`.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-effect-taxonomy-v1.md) | Effect taxonomy v1 | Accepted |
| [0002](0002-spec-schema-v1.md) | Spec YAML schema v1 | Accepted |
| [0003](0003-project-skeleton-and-tooling.md) | Project skeleton and tooling | Accepted |
| [0004](0004-claude-code-skills-as-llm-api.md) | Claude Code skills as the LLM API for The Spec authoring stage | Accepted |
| [0005](0005-spec-init-flow-decisions.md) | `spec init` flow — skill packaging, invocation, and overwrite semantics | Accepted |
