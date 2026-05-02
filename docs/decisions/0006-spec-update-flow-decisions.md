# ADR-0006: `spec update` flow — skill, conflict UX, equivalence, and bootstrap behavior

- **Status:** Accepted
- **Date:** 2026-04-27
- **Applies to:** The Spec stage — `spectate spec update`, the bundled `spec-update` skill
- **Supersedes:** —
- **PR:** [#19](https://github.com/netarvd/spectate/pull/19)

## Context

`spec init` (ADR-0005) bootstraps a Spec from English. `spec from-plan` (T36) bootstraps from a plan document. Neither handles the much more common case once a project has a Spec: **evolving it as requirements change**. Re-running `spec init` would clobber the existing file (and trigger the warn-on-existing-file guard). The need is for a delta-aware update.

T37 surfaces four real choices that constrain this evolution surface.

## Decision

### Skill strategy

A new dedicated `spec-update` skill (sibling to `spec-init` and `spec-from-plan`). The skill receives both the existing Spec YAML and the new English / plan text as inputs, and emits **only** a structured delta (additions, removals) — not a full rewritten Spec.

Rejected: reusing `spec-init` and computing the diff client-side. The dedicated skill gives the model context about what already exists, which lets it reason about additions vs. revisions vs. genuinely new effects more reliably than diffing two independently-generated Specs.

### Conflict UX

Interactive per-change `y/n` loop for non-conflicting additions and removals. **Conflicts always abort** the entire update — refuse-to-overwrite, exit code 1, file untouched.

Rejected: the `.spec.yaml.proposed` batch-review file (cognitive load splits the workflow), and any auto-resolution rule (silently picking a side defeats the closed-world contract).

### Effect-equivalence rule (for conflict detection)

Exact string match at v1. `api.example.com` and `api.*.example.com` are treated as different effects even though one structurally subsumes the other. A bare-string `required` and a scoped-required (or differently-scoped) `required` for the same effect are treated as a conflict.

Rejected for v1: normalized matching (lowercase host expansion, glob equivalence) and semantic subsumption. Both are viable v2 directions; the gap is documented.

### No-existing-Spec behavior

Error out with exit code 2 and a message pointing the user at `spec init`. Do not silently fall back; do not interactively prompt.

Rejected: silent fallback (couples two distinct workflows; surprises the user) and interactive prompt (extra friction in the common case where the user just typo'd `update` instead of `init`).

## Rationale

The dedicated `spec-update` skill is the only choice that gives the model enough context to distinguish "add this new effect" from "revise this existing effect" reliably. Any client-side diff approach loses the model's ability to disambiguate.

Hard-abort on conflicts is consistent with the closed-world contract: Spectate never silently makes a destructive choice on the user's behalf. The user must explicitly resolve, even if that means hand-editing the YAML.

Exact-match equivalence is the simplest correct rule for v1. It will produce some false positives (treating overlapping patterns as distinct effects), but those errors fail in the safe direction — surface for review rather than silently merge.

Erroring on no-existing-Spec preserves intent: `update` only makes sense when there's something to update. Conflating it with `init` would hide bugs in the user's workflow.

## Consequences

**Enabled.** The Spec authoring loop is now closed end-to-end:
- `spec init` — bootstrap from English
- `spec from-plan` — bootstrap from a plan document
- `spec update` — evolve an existing Spec

The Spec genuinely is a living artifact, not a one-time bootstrap.

**Constraints accepted:**
- Each `spec update` invocation spawns a fresh `claude -p` subprocess (per ADR-0005) and re-reads the entire Spec. Acceptable for the expected call frequency (a handful of times per repo per quarter).
- Hard-abort on conflicts means even small conflicts require a fresh `update` invocation after the user manually resolves. Acceptable as a safety floor.
- Exact-match equivalence will sometimes flag conflicts that a smarter rule would auto-resolve. Documented; v2 candidate.

## Alternatives considered

- **Reuse `spec-init` + client-side diff.** Rejected — loses model context, harder to distinguish revision vs. addition.
- **`.spec.yaml.proposed` batch file.** Rejected — splits the workflow across the CLI and the editor; defeats interactivity.
- **Auto-resolve conflicts** (last-write-wins, additive-only, etc.). Rejected — silent destructive choice violates closed-world.
- **Normalized / semantic equivalence rule at v1.** Rejected — added complexity without proven need; v2 candidate when real false-positive volume is observed.
- **Silent fallback to `init` when no Spec exists.** Rejected — hides workflow bugs; conflates two distinct entry points.
