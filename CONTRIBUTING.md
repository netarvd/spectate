# Contributing

## Before you open a PR

Run all three checks and fix everything before pushing:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

The e2e suite spawns the installed CLI as a subprocess and is slower (~40s). Run it separately if you've touched `demo/` or `tests/fixtures/`:

```bash
pytest tests/e2e -v
```

### pytest environment note

This repo uses a uv-managed pytest (`~/.local/bin/pytest`). If you get `ModuleNotFoundError` during collection, the uv-isolated Python is missing the project's dependencies. Fix it once:

```bash
uv pip install --python ~/.local/share/uv/tools/pytest/bin/python -e ".[dev]"
```

## Branch naming

No enforced convention, but existing branches follow `feat/<scope>` (e.g. `feat/t21-review-cli`). Claude Code sessions generate branches under `claude/`.

## PR description format

Every PR body answers three things in order:

**## What** — what code was added or changed. One section per logical unit; bullet points for multi-part PRs.

**## Value** — one line: what the user can do now that they couldn't before.

**## Verify** — exact commands the reviewer can run to confirm it works. Use fenced bash blocks. Include the expected output or exit code.

**## Decisions raised** _(optional)_ — list every contested design choice with options and a recommendation. Never decide silently. If the user locks a decision in review, it becomes an ADR (see below).

**## Test plan** _(optional)_ — checklist of what was tested. Include linting, type-checking, and any manual checks beyond `pytest`.

Small, uncontentious changes (doc fixes, formatting) can collapse to a single paragraph.

## Merging

**Merge one PR at a time.** GitHub serializes squash-merges but silently drops PRs when the queue moves faster than its base-ref recomputation. Symptom: PR shows merged, branch deleted, but the commit is not in `git log main`. Always wait for each PR to appear in `main` before merging the next.

**Verify the landed state, not the PR status.** After merging, confirm with:

```bash
git fetch origin main
git log origin/main --oneline -5
```

`state=MERGED` on GitHub is a self-report. `git log` is the ground truth.

**Never branch new work off an unmerged PR.** Creates compounding merge conflicts across every dependent PR. Merge the blocker first, then branch from `main`.

## ADRs

When a decision raised in a PR is locked (by user review, comment, or merge), it becomes an Architecture Decision Record in `docs/decisions/`.

1. Copy `docs/decisions/0000-template.md` to the next free number.
2. Fill in Context, Decision, Rationale, Consequences, Alternatives considered.
3. Link the PR that locked it.
4. Bundle related sub-decisions into the same ADR if they share rationale; split otherwise.
5. Update the index table in `docs/decisions/README.md`.

ADRs are immutable once merged. The only allowed post-merge edit is updating the `Status` line to `Superseded by ADR-XXXX` and adding a one-line note. Never silently lock a decision without an ADR.

## Versioning

Components are versioned independently. Adding optional fields doesn't bump a version; breaking changes do and require a new superseding ADR. See `docs/decisions/README.md` for the full policy.
