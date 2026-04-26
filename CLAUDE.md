# Spectate

A drift detector for AI-generated code. Spectate watches what an agent's code actually touches at the boundaries (network, filesystem, subprocess, imports, env vars, databases) and surfaces every divergence from a developer-authored Spec.

## The story (four stages)

1. **The Spec** — the developer articulates intent in a YAML file. Three slots per effect category: `required`, `allowed`, `forbidden`. Anything not mentioned is **unspecified**.
2. **The Watch** — Watchers (one per effect category) inspect the code statically and emit **Observations** (a normalized set of effect facts).
3. **The Critique** — Observations are compared to the Spec, producing **Findings** in four buckets:
   - `missing-required` (high — declared required, absent from code)
   - `added-forbidden` (high — declared forbidden, present in code)
   - `added-unspecified` (drift — present in code, not mentioned in Spec)
   - `within-spec` (suppressed — present and allowed)
4. **The Bulletin** — Findings are surfaced to the developer (terminal, JSON, PR comment).

## Closed-world by default

The Spec is closed-world: anything not declared is flagged as drift. This is the contract that makes Spectate useful — open-world (denylist) collapses the tool to a linter. The dev's response to every flag is binary: **approve and add to the Spec, or investigate**. No silent third path.

## The spec is the audit

Runtime tools audit *behavior* and require the developer to mentally reconstruct intent on every alert. Spectate collapses intent and audit into a single artifact: the Spec. Flags carry the developer's own prior words as context, and the audit lands at authoring time, not after deploy.

## Module layout

- `spectate/spec/` — Spec model, validator, LLM client
- `spectate/watchers/` — Watchers, one per effect category
- `spectate/observations/` — Observation data type and aggregator
- `spectate/critique/` — Spec → Observations normalizer and diff algorithm
- `spectate/bulletin/` — Output formatters (terminal, JSON, markdown)

## CLI

- `spectate spec init "<english description>"` — draft the Spec
- `spectate spec transcribe <path>` — bootstrap a draft Spec from existing code
- `spectate review [path]` — Watch + Critique + Bulletin in one command
- `spectate accept <finding-id>` — accept a Finding into the Spec

## Architecture Decision Records

Every locked support/unsupport decision lives in `docs/decisions/` as a numbered, immutable ADR. When a decision raised in your PR is locked (user review or merge), capture it there using the next free number — copy `0000-template.md`, fill it in, link the PR. Bundle related sub-decisions into the same ADR if they share rationale; otherwise split. Never silently lock a decision without an ADR.

Components are versioned independently (taxonomy v1 in `docs/taxonomy.md`, Spec schema v1 in `src/spectate/spec/spec.schema.json`). Adding optional fields doesn't bump; breaking changes do, and trigger a new ADR superseding the old one. See `docs/decisions/README.md` for the full versioning policy.

## For agents working in this repo

- **Output value-first.** Every PR description must answer three things: what code was added, what value it delivers (one line), exactly how the user can verify it works.
- **Raise, don't decide.** When you encounter a contested design choice, surface it in the PR description with options and a recommendation. Never decide silently in the Foundation phase. In later phases, prefer raising over deciding when uncertain.
- **Document locked decisions.** When the user locks a decision in your PR, add an ADR (see above). This is non-optional.
- **Stay in your stage.** Each task is scoped to one stage (Foundation, The Spec, The Watch, The Critique, The Stage, In the Loop, Curtain Up). Don't expand outside it without flagging.
- **Be terse.** No emoji unless asked. No comments explaining what well-named code already does. Default to writing no comments at all.
