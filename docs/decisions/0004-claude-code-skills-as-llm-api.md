# ADR-0004: Claude Code skills as the LLM API for The Spec authoring stage

- **Status:** Accepted
- **Date:** 2026-04-26
- **Applies to:** The Spec stage — `spectate spec init`, `spectate spec transcribe`
- **Supersedes:** —
- **PR:** TBD

## Context

The Spec stage is the only LLM-touching part of Spectate. Originally (in the discarded #6) the LLM client was a direct integration with the Anthropic Python SDK: API key management, model selection, prompt caching, retry policy, all owned by Spectate.

Spectate's audience is overwhelmingly developers already running Claude Code. Asking those users to set up `ANTHROPIC_API_KEY` and pick a model when their environment already has both configured is friction without value. It also forces Spectate to own a surface (model choice, caching strategy, retry, SDK version) that has no inherent connection to the tool's purpose.

## Decision

`spectate spec init` and `spectate spec transcribe` invoke the LLM by shelling to `claude -p` against a Spectate-shipped skill at `.claude/skills/spec-init/`. The LLM client (T05) is a thin `SkillClient` that wraps subprocess invocation, captures the skill's text output, and returns it.

The provider-abstraction Protocol designed in the original T05 is preserved:

```python
class LLMClient(Protocol):
    def generate_spec(english: str) -> str: ...
```

`SkillClient` is the v1 implementation. An `AnthropicAPIClient` could be added later behind the same interface if non-CC users need direct access; not built now.

The skill itself (T04) is a `SKILL.md` file in `.claude/skills/spec-init/` with the system prompt and few-shot examples. Spectate ships a `spectate install-skills` command (or equivalent install step) that copies the skill to `~/.claude/skills/` for user-wide availability.

## Rationale

- **Dependency surface shrinks.** No `anthropic` SDK in `pyproject.toml`, no `ANTHROPIC_API_KEY`, no model name in code, no retry/caching code to maintain.
- **Audience fit.** Spectate's users are in Claude Code. Reusing the auth and model selection they already have is the path of least resistance.
- **Editable prompt as a first-class artifact.** The skill is a markdown file. Users can read, fork, customize the prompt without touching Spectate's code or redeploying anything.
- **Distribution alignment.** Skills are how the Claude Code ecosystem ships LLM capabilities. Spectate becomes "a tool that ships a skill" — natural in the ecosystem.
- **The escape hatch is preserved.** The `LLMClient` Protocol means a future `AnthropicAPIClient` can land behind the same seam without touching T07.

## Consequences

**Enabled.** Simpler T05 (~30 LOC vs ~150). T04 becomes a markdown skill spec, editable by users. No API key onboarding for the dominant install path.

**Constraints.** `spectate spec init` and `spectate spec transcribe` require `claude` to be installed and authenticated. `spectate review`, `spectate accept`, and the rest of the deterministic pipeline have no such requirement and continue to work for any Python user.

**Performance.** Each spec init / transcribe spawns a `claude -p` subprocess (one-time cost: process startup + skill load). Acceptable — these commands run a handful of times per repo lifetime, not in a hot loop.

**Output parsing.** The skill emits raw YAML; `SkillClient` invokes `claude -p` with `--output-format text` and trusts the skill spec to enforce YAML-only output. Any wrapping (code fences, prose) is the skill author's bug.

## Alternatives considered

- **Continue with Anthropic SDK directly.** Rejected — re-imposes API key onboarding on users who already have `claude` configured; Spectate owns surface (model, caching, retry) it has no domain reason to own.
- **Multi-backend from day one (CC skill + API key).** Rejected for v1 — adds complexity without addressing a known user need. The `LLMClient` Protocol leaves the door open.
- **Custom LLM gateway / provider router.** Rejected — heavyweight; Spectate doesn't have a multi-LLM use case driving it.
- **Use `claude` Python SDK if/when it exists.** No stable Python binding for invoking skills programmatically at the time of writing. `subprocess` is the contract.
