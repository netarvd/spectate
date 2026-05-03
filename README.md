# Spectate

> A drift detector for AI-generated code. Declare the boundaries your code may touch; Spectate flags every divergence the agent introduces.

**Status:** MVP complete. Not yet published to PyPI.

## What it does

You write a small YAML file declaring what your code is allowed to touch at the boundaries — outbound network hosts, filesystem paths, subprocess binaries, imported packages, env vars read, database tables. Spectate scans your code with stdlib `ast`, compares what it finds against the spec, and reports four kinds of Findings:

- **`missing-required`** (high) — declared required, absent from code
- **`added-forbidden`** (high) — declared forbidden, present in code
- **`added-unspecified`** (drift) — present in code, not mentioned in spec
- **`within-spec`** (info, suppressed by default) — present and allowed

The Spec is closed-world: anything not declared is flagged as drift. Your response to every flag is binary: **approve and add to the Spec, or investigate.** No silent third path.

## Quickstart (5 minutes)

Requires Python 3.11+ and (for the `spec init` / `spec from-plan` flows) the [Claude Code CLI](https://code.claude.com) on `PATH`.

```bash
# Install
pip install -e ".[dev]"      # not yet on PyPI; clone from GitHub for now

# In your project, declare what the code is allowed to do
spectate spec init "this service may call api.stripe.com and read OPENAI_API_KEY"
# Or, transcribe an existing project
spectate spec transcribe ./src

# Inspect / edit .spectate/spec.yaml as needed

# Review your code
spectate review

# Pipeable variants for tooling
spectate review --json
spectate review --markdown
```

`spectate review` exits 0 on no drift, 1 on drift, 2 on configuration errors. Use `--fail-on=added|missing|both` (default `both`) to scope what counts as failure.

## CLI surface

| Command | Purpose |
|---|---|
| `spectate spec init "<english>"` | Draft a Spec from a one-line English description (uses Claude Code skill) |
| `spectate spec from-plan <path>` | Draft a Spec from a structured plan document (uses Claude Code skill) |
| `spectate spec transcribe <path>` | Bootstrap a draft Spec from existing code by running the Watchers |
| `spectate spec update "<english>"` | Add new effects to an existing Spec, with conflict-aware merging |
| `spectate review [path]` | Compare code against the Spec; emit Findings (terminal/JSON/markdown) |
| `spectate accept <finding-id>` | Move a flagged effect into the Spec's `allowed` slot |

## Effect categories (taxonomy v1)

Spectate tracks six categories. See [`docs/taxonomy.md`](docs/taxonomy.md) for the full contract.

- `network.outbound(host)` — hostname glob match
- `fs.read(path)` / `fs.write(path)` — gitignore-style glob match
- `subprocess(binary)` — exact (or `*`)
- `imports(package)` — exact, top-level package name
- `env.read(var)` — exact env var name
- `db.read(table)` / `db.write(table)` — exact, raw SQL only at v1

## Workflow integrations

### Pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/netaarvd/spectate
    rev: v0.0.1  # pin to a release tag
    hooks:
      - id: spectate-review
```

The hook installs Spectate into pre-commit's managed Python environment, runs `spectate review` at the `pre-commit` stage, and exits non-zero on any drift.

### Claude Code pre-tool-use hook

Spectate ships a `spectate-cc-hook` script that integrates with Claude Code's hook system. When configured, it runs after Write / Edit / MultiEdit tool calls in a CC session and surfaces Findings as additional context (warn-only — never blocks the agent). See [`docs/integrations/claude-code-hook.md`](docs/integrations/claude-code-hook.md) for the `settings.json` snippet.

### Direct CI integration

```bash
# In your CI workflow
pip install -e .   # or pip install spectate when published
spectate review --json > spectate.json
# … pipe the JSON to your bot of choice, or just rely on the exit code
```

## Honest scope and limits

- **Python only at v1.** The Watchers are AST-based; no JavaScript / Go / Rust.
- **Static analysis ceiling.** Dynamic patterns (variable URLs, computed paths, ORM-mediated SQL) emit `unresolved` Observations rather than producing false positives. Documented in the taxonomy.
- **Per-handler `required` matching is file-only at v1.** Function-level scope is a deferred enhancement (ADR-0009).
- **`spec init` and `spec from-plan` require Claude Code on PATH.** They invoke the `spec-init` / `spec-from-plan` skills bundled in the wheel. `spectate review`, `transcribe`, `accept`, and the rest of the deterministic pipeline have no such requirement.
- **The MVP demo arc covers eight scenarios** — see [`tests/fixtures/`](tests/fixtures/) for the canonical examples.

## Develop

```bash
git clone https://github.com/netaarvd/spectate
cd spectate
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

ruff check .
ruff format --check .
mypy src
pytest

spectate --help
```

The architecture lives in `docs/decisions/` (ADRs 0001–0009). Start with the [README there](docs/decisions/README.md) for the versioning policy and the index.
