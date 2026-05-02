# ADR-0008: `Observation` carries `tags` (labels) and `metadata` (kind=value pairs) as separate fields

- **Status:** Accepted
- **Date:** 2026-05-02
- **Applies to:** Tier 0 contract — `src/spectate/observations/observation.py`. All Watchers and consumers of `Observation`.
- **Supersedes:** —
- **PR:** TBD

## Context

The Tier 0 `Observation` dataclass was designed with a single optional `tags: tuple[str, ...]` field. Two Watchers ended up using it for semantically different purposes:

- **ImportsWatcher** (T12) sets `tags=("stdlib",)` — an informational *label* describing what the Observation is.
- **SqlWatcher** (T14) sets `tags=("unresolved:parse_failed",)` — colon-namespaced *kind=value* metadata explaining why the Observation is unresolved.

T15 (effect aggregator) and T17 (Critique) need to consume Observations consistently. Without a locked convention, every future Watcher would invent its own tag scheme, and downstream code would have to handle each ad-hoc format.

## Decision

`Observation` carries **two** auxiliary fields with distinct semantics:

```python
@dataclass(frozen=True, slots=True, order=True)
class Observation:
    category: str
    parameter: str
    file: Path
    line: int
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
```

- **`tags`** holds bare informational labels. Examples: `("stdlib",)`, future candidates: `("deprecated",)`, `("framework_internal",)`. Filterable, append-only set semantics. Affects ordering and equality.
- **`metadata`** holds structured key=value pairs for context. Examples: `{"unresolved_reason": "parse_failed"}`. Does **not** affect identity, equality, or hash — it's auxiliary context for the Bulletin to render and the dev to read.

### Identity rule

Two Observations with the same `(category, parameter, file, line, tags)` are the **same Observation** for deduplication purposes, regardless of `metadata`. The aggregator (T15) dedupes on these five fields; metadata of the surviving copy wins (or merges, at the aggregator's discretion).

### Convention for `metadata` keys

- Keys are bare snake_case strings (e.g. `unresolved_reason`, not `unresolved-reason` or `unresolved.reason`).
- Values are plain strings — no nested structures.
- New metadata keys can be introduced freely by Watchers without an ADR; documenting them in the Watcher's docstring is sufficient.
- The single existing key in v1 is `unresolved_reason` (used by SqlWatcher).

## Rationale

- **Two fields, two purposes.** A filterable label and a typed-value pair are different things. Forcing them through one stringly-typed bag (the original `tags`) puts that distinction in every consumer's head.
- **Identity stability.** Metadata is auxiliary; it shouldn't change what counts as "the same Observation." Excluding it from `__eq__` and `__hash__` (`compare=False, hash=False`) keeps deduplication predictable.
- **No schema migration required for v1's only real use.** SqlWatcher's `unresolved:parse_failed`-style strings are mechanically translated to `metadata={"unresolved_reason": "parse_failed"}`.

## Consequences

**Enabled.**
- T15 dedupes on `(category, parameter, file, line, tags)` deterministically.
- T17/Bulletin can render tags as inline labels and metadata as a structured "details" block per Finding.
- Future Watchers have a clear answer to "where do I put context X?": label = tags; key/value = metadata.

**Constraints.**
- `metadata` is `dict[str, str]` — no nested values. If we ever need richer structure, that's a new ADR.
- Mutating a metadata dict in place is technically possible (Python doesn't deep-freeze). Watchers are expected to construct and forget; nobody mutates an emitted Observation. No defensive copying for v1.

**Migration.** SqlWatcher's four `tags=("unresolved:...",)` emissions become `metadata={"unresolved_reason": "..."}`. Tests updated to assert on `metadata.get("unresolved_reason")` instead of substring-matching tags. No other Watcher needed changes.

## Alternatives considered

- **A. Free-form bag, document the convention.** Rejected — convention drift is exactly the problem we just hit; one shared field doesn't enforce anything.
- **C. Tags + typed `unresolved_reason: str | None`.** Rejected — too narrow. Solves the immediate case but doesn't generalize when the next Watcher wants to attach a different kind of context (e.g. `db_dialect`, `import_alias_chain`).
- **Keep the `tags=("kind:value",)` colon convention.** Rejected — strings carrying structure are a code smell; consumers parse, mistakes happen, schema is implicit.
