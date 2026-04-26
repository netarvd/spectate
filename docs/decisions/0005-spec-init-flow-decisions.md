# ADR-0005: `spec init` flow — skill packaging, invocation, and overwrite semantics

- **Status:** Accepted
- **Date:** 2026-04-26
- **Applies to:** The Spec stage — `spectate spec init`, the bundled `spec-init` skill, and any future Spectate-shipped skills (`spec-from-plan`, `spec-update`)
- **Supersedes:** —
- **PR:** [#9](https://github.com/netarvd/spectate/pull/9)

## Context

ADR-0004 locked the architectural decision (Claude Code skills as the LLM API). Implementing it surfaced a cluster of concrete decisions that constrain how every Spectate-shipped skill is packaged, invoked, and integrated. They're collected here so future skills (T36 `spec-from-plan`, T37 `spec-update`) inherit the same patterns rather than relitigating them.

## Decision

### Skill packaging

Skills ship inside the Python wheel under `src/spectate/skills/<skill-name>/` and are made discoverable to `claude` via **runtime materialization**: on first invocation, `SkillClient` copies the bundled skill files to a tempdir cache that follows the layout `<cache>/.claude/skills/<skill-name>/`. The client then invokes `claude --add-dir <cache>`, which causes `claude` to auto-load the skill.

`pyproject.toml` uses `[tool.hatch.build.targets.wheel.force-include]` to guarantee the skill directory ships in the wheel (regular `package-data` doesn't reliably include non-Python files for `src/` layouts).

No user-facing install step is required (`spectate install-skills` is not built). The skill works the moment `pip install spectate` finishes.

### Hermetic vs auth-reusing invocation

`SkillClient` does **not** pass `--bare` by default. Reasoning: ADR-0004's primary motivation is reusing the user's existing Claude Code auth, and `--bare` blocks that auth path along with hooks/plugins/MCP. Users who need hermetic invocation (CI, reproducibility audits) opt in via the `SPECTATE_CLAUDE_BARE=1` environment variable.

### Output discipline

Invoke `claude` with `--output-format text` and instruct the skill to emit raw YAML only (no prose, no code fences). Defensive parsing on the client side: a `_strip_code_fences()` helper strips ` ```yaml ... ``` ` wrappers if the model regresses on that instruction (observed in real-world testing during PR #9).

JSON-schema-wrapped output (`--output-format json --json-schema '{...}'`) was considered and rejected for v1 — added robustness wasn't worth the parsing layer when defensive stripping handled the only observed deviation.

### Skill frontmatter defaults

Spectate-shipped skills set `disable-model-invocation: true` and `allowed-tools: []` by default. Reasoning:
- These skills are purpose-built for Spectate's CLI; auto-invocation by Claude in unrelated CC sessions is noise.
- Pure text-generation skills don't need tool access.

Future skills should follow this default unless they have a documented reason to differ.

### Existing-file overwrite semantics

When `spec init`'s output target already exists, the confirmation prompt surfaces that fact and the default flips to **No**. `--yes / -y` still overwrites silently for scripted use. This pattern (`cp -i`-style guard with explicit override) applies to any future Spec-writing command.

A smart upsert flow (`spectate spec update`) is tracked separately in T37 — this ADR governs only the destructive-overwrite case.

### Other locked details

- **Few-shot count in `spec-init`:** 5 (covers Spec slots × at least 4 effect categories without bloating context).
- **`claude`-not-on-PATH error:** typed `ClaudeNotFoundError` with actionable message naming the install requirement.
- **Default output path:** `.spectate/spec.yaml` (re-confirms ADR-0002).

## Rationale

The skill-packaging path (wheel-bundled + runtime materialization + `--add-dir`) is the cleanest distribution story Claude Code currently supports for tools that bundle their own skills — the Spectate package is self-contained, no separate install step, no manual user-side `~/.claude/skills/` copy. Among existing devtools, no published examples were found of pip packages bundling skills this way; Spectate establishes the pattern.

`--bare` off by default is the more user-friendly choice given ADR-0004's audience assumption (CC users). Hermetic mode stays accessible behind an env var for the CI / reproducibility cases.

The defensive `_strip_code_fences()` helper trades a small amount of cleanup code for resilience against the one model deviation observed in practice. Cheaper than a JSON-schema layer.

The overwrite guard exists because the prior behavior (silent overwrite on `Y` default) was a real footgun caught in PR #9 review.

## Consequences

**Enabled:** every future Spectate-shipped skill (T36 `spec-from-plan`, T37 `spec-update`, anything later) inherits the packaging, invocation, output-discipline, and frontmatter conventions without re-deciding. Adding a new skill is mostly writing a new `SKILL.md` and wiring a new CLI command.

**Constraints accepted:**
- Spectate's spec-authoring commands require `claude` on PATH. `spectate review` and the deterministic pipeline have no such requirement.
- Tempdir materialization happens on every fresh process. Acceptable — `spec init` runs a handful of times per repo lifetime.
- `--output-format text` puts a small clean-output burden on each skill author (must instruct the model to emit raw output, must remember the user might not).

**Forward-compat:** if Anthropic ships a richer Python binding for skill invocation, `SkillClient` is the only place to change. The `LLMClient` Protocol stays.

## Alternatives considered

- **`spectate install-skills` user-side install step.** Rejected — adds a manual step for zero functional benefit over runtime materialization.
- **`--bare` on by default.** Rejected — blocks user's CC auth, defeating ADR-0004's main draw.
- **JSON-schema-wrapped output.** Rejected for v1 — defensive fence-stripping handled the only real-world deviation; not worth the additional parsing layer yet.
- **Silent overwrite (status quo before the PR #9 fix).** Rejected after explicit user feedback.
