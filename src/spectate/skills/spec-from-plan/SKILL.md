---
name: spec-from-plan
description: Converts a structured plan document (markdown with sections like goals, components, side effects, dependencies, non-goals, alternatives) into a Spectate Spec YAML conforming to schema version 1. Use when a user has an existing plan or design doc and asks for a Spectate Spec, or invokes `spectate spec from-plan`.
allowed-tools: []
disable-model-invocation: true
---

# Spectate Spec from a plan document

Convert a structured plan document (markdown, multi-section) into a Spectate Spec YAML document (schema `version: 1`).

## Output contract

- Emit raw YAML only.
- No prose. No commentary. No code fences (no ```yaml, no ```).
- The first line of output must be `version: 1`.
- Output nothing after the YAML.

A downstream validator parses your output directly. Any wrapping is a bug.

## Spec shape (recap)

A Spec has six effect categories, each with three optional slots:

- `required` — must be present in code; absence is a high-severity Finding.
- `allowed` — may be present; suppressed in the Bulletin.
- `forbidden` — must not be present; presence is a high-severity Finding.

Effects not mentioned in any slot surface as drift. The Spec is **closed-world by default**.

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

Top-level fields: `version: 1` (required), `unresolved_handling: surface | flag | drop` (default `surface`), `stdlib_auto_allow: true | false` (default `true`).

## What to extract

Read the plan and pull out **concrete external touch points the code will have**:

- HTTP/network: hostnames the code will call.
- Filesystem: specific paths or path globs read or written.
- Subprocess: binary names the code will exec.
- Imports: third-party packages (top-level name).
- Env vars: variable names read.
- DB tables: table names read or written.

Use the section headers as hints — sections titled "components", "side effects", "dependencies", "external services", "data stores", "interfaces", "I/O", "integrations", "environment" usually contain the extractable material. Imperative or declarative statements ("the worker fetches X", "writes to /tmp/...", "must call Y", "must never touch Z") map directly to slots.

## What to ignore

Plans contain prose that is not a contract on the code. Do not extract from:

- Rationale paragraphs ("we chose X because...").
- Alternatives considered / "rejected options" sections.
- Prior art, related work, history, "how we got here".
- Motivation and trade-off discussion.
- Future work / "later we may..." / "out of scope".
- Vague aspirational language without a concrete touchpoint ("scalable", "observable", "secure").

If a section title or paragraph is about *why* or *what we didn't do*, skip it.

## Slot mapping

- "Must call X", "must read Y", "is required to ..." → `required`.
- "May call X", "uses X", "depends on X", "calls X" without a "must" → `allowed`.
- "Must never X", "forbidden", "must not", "non-goal: X" → `forbidden`.
- Items only mentioned as "considered" or "alternative" → omit (not a contract).

## Authoring rules

1. **Closed-world default.** When in doubt, leave an effect unspecified rather than over-allow. Plans hedge ("we might also..."); resist the urge to encode hedges as `allowed`. Unspecified surfaces as drift; over-allowed silently passes.
2. **Use the right slot.** See mapping above.
3. **Normalize values to taxonomy form.** Hostnames lowercase, no scheme, no port, no path. Subprocess binary basename only. Imports top-level package only. Tables lowercase.
4. **Omit empty sections.** Don't emit `network: null` or empty slot lists — leave them out.
5. **Don't invent effects.** Only encode what the plan explicitly names. If a plan says "talks to a payment processor" without naming Stripe, do not write `api.stripe.com`.
6. **Forbidden non-goals are extractable.** A "non-goals" section that says "must not write to disk" is a real contract: encode it as `fs.write.forbidden` (use a glob like `/**` if the prohibition is global).

## Few-shot examples

The `examples/` sibling directory contains worked plan → YAML pairs. Each example file holds a small markdown plan, then `---`, then the YAML.

- `examples/01-network-and-imports.md`
- `examples/02-fs-and-subprocess.md`
- `examples/03-env-and-db.md`
- `examples/04-non-goals-as-forbidden.md`
- `examples/05-ignore-rationale-and-alternatives.md`
