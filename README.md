# Spectate

> A drift detector for AI-generated code. Declare the boundaries your code may touch; Spectate flags every divergence the agent introduces.

**Status:** Work in progress. Not yet usable.

## Install

```bash
pip install spectate
```

Not yet published; install from source (see Develop).

## Develop

Requires Python 3.11+.

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

## Use as a pre-commit hook

Spectate ships a `pre-commit-hooks.yaml` so consumers can run `spectate review`
on every commit. Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/netaarvd/spectate
    rev: v0.0.1  # pin to a release tag
    hooks:
      - id: spectate-review
```

The hook installs Spectate into pre-commit's managed environment
(`language: python`), so consumers do not need a global install. It runs at
the `pre-commit` stage and exits non-zero on any drift, matching the CLI's
default `--fail-on both` behaviour.

