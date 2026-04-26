# ADR-0001: Effect taxonomy v1

- **Status:** Accepted
- **Date:** 2026-04-26
- **Applies to:** Taxonomy v1 (`docs/taxonomy.md`)
- **Supersedes:** —
- **PR:** [#1](https://github.com/netarvd/spectate/pull/1)

## Context

Spectate compares developer-articulated intent (the Spec) against the agent's code (Observations). Both sides need to speak the same vocabulary about effects. The taxonomy is the shared contract — every Watcher emits Observations in this language, and every Spec slot references it.

## Decision

Six effect categories, each with a defined parameter, normalized form, and Spec-match semantics:

| Category | Parameter | Spec match |
|---|---|---|
| `network.outbound(host)` | hostname (lowercase, no scheme/port/path) | hostname glob |
| `fs.read(path-glob)` | path as written | gitignore-style glob |
| `fs.write(path-glob)` | path as written | gitignore-style glob |
| `subprocess(binary)` | binary basename | exact, `*` for all |
| `imports(package)` | top-level package name | exact |
| `env.read(var)` | literal var name | exact |
| `db.read(table)` | lowercase unquoted table name (raw SQL only) | exact |
| `db.write(table)` | lowercase unquoted table name (raw SQL only) | exact |

When a Watcher cannot statically resolve a parameter, it emits the **unresolved sentinel** `effect(*)`. Default behavior: surface in the Bulletin under a distinct `unresolved` severity rather than silently passing or counting as drift.

### Sub-decisions locked in v1

1. **Network host granularity:** hostname only, no port. Most policies care about destination, not port.
2. **Unresolved handling:** configurable via `unresolved_handling` (`surface` | `flag` | `drop`), default `surface`.
3. **Path expansion:** none at v1. Spec authors write what the code writes; no `~` or env-var resolution.
4. **Glob support:** restricted to `network.outbound` (host glob) and `fs.{read,write}` (path glob). `imports`, `env.read`, `db.*` are exact-match only at v1.
5. **Stdlib auto-allow:** configurable via `stdlib_auto_allow` (bool), default `true`. Reduces noise; can be disabled to route stdlib through Spec slots with a `[stdlib]` Bulletin tag.
6. **Path normalization:** none. Absolute stays absolute; relative stays relative; trailing slashes stripped only.

## Rationale

The six categories cover the eight MVP demo scenarios end-to-end (vanished auth, library swap, new outbound, persistent state, subprocess intro, hardcoded webhook, typosquat, stale spec). They map to the boundaries that matter most for AI-generated code: external IO, dependencies, environment, data.

The unresolved sentinel keeps the closed-world contract honest — without it, dynamic dispatch would silently pass and erode trust in the tool.

## Consequences

**Enabled:** every Watcher and every Spec slot has a stable contract. T02 (Spec schema) and T09–T14 (Watchers) can be implemented in parallel without coordinating on naming or normalization.

**Forbidden at v1:** WebSockets/gRPC/HTTP/2 client libs, inbound network surface, file-descriptor IO, mmap, IPC, threading primitives, time/randomness as effects, logging destinations, ORM-mediated SQL.

**Configurable surface:** two top-level config keys (`unresolved_handling`, `stdlib_auto_allow`), both with safe defaults. Users opt into noisier or quieter behavior.

## Alternatives considered

Each sub-decision had alternatives. See PR #1 for the original framing of the six trade-offs:

- **Host granularity:** include port (`api.example.com:8080`) — rejected; rare in target audience.
- **Unresolved handling:** silently drop (dishonest) or treat as drift (noisier, may train users to disable).
- **Path expansion:** expand `~` and env vars — rejected for v1; couples Spec to runtime environment.
- **Globs everywhere:** support globs uniformly — rejected at v1; package/env/table names lack natural hierarchy.
- **Stdlib tag only (no auto-allow):** route all imports through Spec slots — rejected as default; too noisy.
- **Path normalization to absolute:** resolve against repo root — rejected; Spec authors should match what the code says.
