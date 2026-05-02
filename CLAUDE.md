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

## Workflow rules — earned the hard way

These exist because we hit each of them in practice. They are not negotiable.

- **Never run parallel `gh pr merge` on more than one PR.** GitHub serializes squash-merges but silently drops some of them when the queue moves faster than its base-ref recomputation: the dropped PRs end up marked `MERGED` with a valid `mergedAt` and a real squash commit, but the squash commit is **orphan** — never attached to `main`. Symptoms: PR shows merged, branch deleted, but `git log main` doesn't contain the expected commit and the files aren't in the tree. Always merge sequentially, one at a time, waiting for each to land in `main` before invoking the next.
- **Never fire dependent agents from a non-merged base branch.** Branching new work off an unmerged feature branch creates rolling merge conflicts that compound across every dependent PR. The right pattern is sequential: merge the blocking PR, then fire dependents from `main`. The cost of waiting is much smaller than the cost of untangling 6 cascading conflicts.
- **Watch the `__init__.py` aggregation pattern.** When N parallel agents each add an import line to the same file at the same alphabetical position, they all conflict against each other. Two solutions: (a) fire serially so each PR sees the previous import on `main`, or (b) strip the `__init__.py` change from each PR and add all imports in one follow-up PR. Pick (b) when N ≥ 3.
- **Force-push and PR-merge always need explicit user authorization.** The hooks block both by default. The user authorizes per-action — "merge all" applies to the batch open at the time, not to PRs created later. Always re-confirm before merging a freshly-opened PR or force-pushing a branch you didn't just create yourself.
- **Use absolute, worktree-relative paths inside subagents.** Multiple agents observed `cd`-ing into the main checkout instead of their isolated worktree, which led to cross-agent file pollution. Subagent prompts should explicitly require `cd $WORKTREE_PATH` or absolute paths under it for every Write/Edit/Bash call that touches files.
- **Verify the actual landed state, not the PR status.** GitHub's `state=MERGED` is a self-report; `git log main` is the ground truth. After every merge wave, do `git ls-tree main` or `git diff origin/main~N..origin/main --stat` to confirm the changes actually landed.
