# ADR-0009: `SpecMatchers` contract — API shape, precedence, pattern libraries

- **Status:** Accepted
- **Date:** 2026-05-03
- **Applies to:** The Critique stage — `src/spectate/critique/expected.py`. The contract every consumer of compiled Spec matchers (T17 diff, future re-use) relies on.
- **Supersedes:** —
- **PR:** [#26](https://github.com/netarvd/spectate/pull/26)

## Context

T16 turns a parsed Spec into a structured matcher set so T17 (and any future consumer) can ask "does this Observation belong in the spec?" without carrying around the raw Spec or re-implementing match semantics. The matcher API is the contract every downstream stage hangs on; locking it explicitly here means future Watchers, Critique implementations, or alternative Spec frontends all speak the same language.

## Decision

### Public API

```python
def compile_spec(spec: Spec) -> SpecMatchers: ...

class SpecMatchers:
    def classify(obs: Observation) -> Literal["required", "allowed", "forbidden", "unspecified"]: ...
    def matched_required(obs: Observation) -> tuple[RequiredKey, ...]: ...
    def all_required_keys() -> tuple[RequiredKey, ...]: ...
```

`RequiredKey` is a hashable identifier for a single `required` entry (category + parameter + optional handler scope) so callers can dedupe and track which required-effects have been satisfied across an entire scan.

### Strongest-slot precedence

When a single Observation matches more than one slot in the Spec, `classify` returns the strongest:

```
forbidden > required > allowed > unspecified
```

The user is most served by the most-restrictive interpretation: if they explicitly forbade something *and* allowed it (or someone else did), the forbid wins.

### Pattern libraries

| Category | Library | Match style |
|---|---|---|
| `network.outbound` | `fnmatch` (stdlib) | Hostname glob (`*.example.com`) |
| `fs.read` / `fs.write` | `pathspec` (`GitWildMatchPattern`) | Gitignore-style globs (`/var/log/**`) |
| `subprocess` | string equality | Exact, with `*` matching all binaries |
| `imports`, `env.read`, `db.read`, `db.write` | string equality | Exact only at v1 |

Patterns are compiled once at `compile_spec` time, not per-Observation.

`forbidden` patterns use the same matcher style as `allowed` for each category — symmetric. (Globs in `network.outbound.forbidden`, exact-match in `imports.forbidden`, etc.)

### Unresolved Observations

An Observation with `parameter == UNRESOLVED` (`*`) classifies as `unspecified`. The Critique algorithm (T17) routes it to a distinct `unresolved` Findings bucket per ADR-0001 rather than treating it as drift or as within-spec — the matcher just declines to make a call.

### Per-handler scope at v1

Per-handler `required` entries match on **file path only** at v1. Function-level disambiguation (knowing which handler an Observation's line is "inside") is a deferred enhancement. A required entry scoped to `path/file.py::function_name` is satisfied by *any* Observation in `path/file.py`, regardless of which function the line is in. Documented gap; revisit when real false-positive volume warrants it.

## Rationale

The three-method API gives T17 exactly what it needs (per-Observation classification + required-key tracking) without leaking Spec internals. `RequiredKey` is the missing-required bookkeeping primitive — without it, T17 would have to re-walk the Spec to figure out which required entries weren't satisfied.

Strongest-slot precedence collapses what would otherwise be ambiguous overlap rules into a single rule that's both safe and easy to reason about.

The pattern-library choices are the cheapest stable options. `pathspec` is the de facto path-glob library; `fnmatch` is stdlib and sufficient for hostname globs. Exact match for the categories that don't have natural hierarchy (packages, env vars, table names) per ADR-0001.

File-only per-handler scope at v1 trades correctness for shippability. Real per-line function attribution requires parsing every file, building a line-range tree, and resolving the Observation against it. Deferred until the gap actually hurts.

## Consequences

**Enabled.** T17 (next) is straightforward to implement against this contract: walk Observations → call `classify` per → bucket into Findings → diff `matched_required` set against `all_required_keys` for missing-required.

**Constraints.**
- Every future consumer of compiled matchers uses this exact API. Adding methods is fine; changing signatures is a breaking change and requires a new ADR.
- Per-handler scope precision is bounded by file granularity. `Spec` files using `path/foo.py::bar` syntax are honest about this — the `::bar` is documentation in v1, not enforced.

**Forbidden until reconsidered.** No alternate matcher libraries. Don't introduce another glob engine; if a category's match needs evolve, evolve `compile_spec` rather than introducing a parallel matcher module.

## Alternatives considered

- **`compile_spec` returns expected Observations directly** (no matcher object). Rejected — globs don't compress to a finite set of expected literals; matchers are the right abstraction.
- **Strongest-slot order other than `forbidden > required > allowed > unspecified`.** Rejected — any ordering that puts `allowed` above `forbidden` would silently weaken explicit denies; any that puts `unspecified` above anything else doesn't make sense (unspecified means "no rule").
- **`wcmatch` instead of `pathspec` + `fnmatch`.** Rejected — more features than v1 needs; the two narrower libraries cover the categories cleanly.
- **Per-line function-level scope at v1.** Rejected — heavier implementation; deferred until concrete false-positive evidence justifies it.
