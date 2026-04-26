---
name: spec-init
description: Converts an English description of what code may, must, or must not do into a Spectate Spec YAML conforming to schema version 1. Use when a user asks for a Spectate Spec, a drift-detection policy, or invokes `spectate spec init`.
allowed-tools: []
disable-model-invocation: true
---

# Spectate Spec authoring

Convert a single English description of a codebase's intended effects into a Spectate Spec YAML document (schema `version: 1`).

## Output contract

- Emit raw YAML only.
- No prose. No commentary. No code fences (no ```yaml, no ```).
- The first line of output must be `version: 1`.
- Output nothing after the YAML.

A downstream validator parses your output directly. Any wrapping is a bug.

## Spec shape

A Spec has six effect categories. Each category exposes three optional slots:

- `required` — must be present in code; absence is a high-severity Finding.
- `allowed` — may be present; suppressed in the Bulletin.
- `forbidden` — must not be present; presence is a high-severity Finding.

Effects not mentioned in any slot are flagged as drift (`added-unspecified`). The Spec is closed-world by default.

### Categories

| Category           | YAML key           | Slot value examples                                  |
|--------------------|--------------------|------------------------------------------------------|
| Outbound network   | `network.outbound` | hostnames or hostname globs (`api.stripe.com`, `*.example.com`) |
| Filesystem read    | `fs.read`          | path globs (`./config.yaml`, `/var/log/**`)          |
| Filesystem write   | `fs.write`         | path globs (`/tmp/**`)                               |
| Subprocess         | `subprocess`       | binary basenames (`git`, `rg`)                       |
| Imports            | `imports`          | top-level package names (`requests`, `httpx`)        |
| Env var read       | `env.read`         | env var names (`OPENAI_API_KEY`)                     |
| Database read      | `db.read`          | table names (`users`)                                |
| Database write     | `db.write`         | table names (`audit_log`)                            |

Per-handler scope (advanced): an entry under `required` may be an object `{handler: "path/file.py::function", value: "..."}` to scope the requirement to a specific function (pytest nodeid style).

Top-level fields beyond categories:

- `version: 1` (required)
- `unresolved_handling: surface | flag | drop` (default `surface`)
- `stdlib_auto_allow: true | false` (default `true`)

## Authoring rules

1. **Closed-world default.** When in doubt, leave an effect unspecified rather than over-allow. Unspecified surfaces as drift; over-allowed silently passes.
2. **Use the right slot.** "Must call X" → `required`. "May call X" → `allowed`. "Must not call X" → `forbidden`.
3. **Normalize values to taxonomy form.** Hostnames lowercase, no scheme, no port, no path. Subprocess binary basename only. Imports top-level package only. Tables lowercase.
4. **Omit empty sections.** Don't emit `network: null` or empty slot lists — leave them out.
5. **Don't invent effects.** Only encode what the English explicitly names or directly implies (e.g. "calls Stripe" implies `network.outbound: api.stripe.com` only if Stripe's API is the obvious referent; otherwise leave it out).

## Few-shot examples

The `examples/` sibling directory contains worked input → output pairs. Study them, then mirror their style. Each example file holds one English line followed by `---` and the YAML.

- `examples/01-allowed-host.md`
- `examples/02-required-and-forbidden.md`
- `examples/03-fs-and-subprocess.md`
- `examples/04-env-and-imports.md`
- `examples/05-per-handler-required.md`
