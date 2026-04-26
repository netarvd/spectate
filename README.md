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
