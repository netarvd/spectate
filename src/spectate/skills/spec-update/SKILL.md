---
name: spec-update
description: Given an existing Spectate Spec YAML and a short English (or plan-text) description of a change, emit a delta — a partial Spec YAML that contains ONLY the additions and removals implied by the description. Use when a user invokes `spectate spec update` to evolve an existing Spec.
allowed-tools: []
disable-model-invocation: true
---

# Spectate Spec update (delta authoring)

Given (a) an existing Spectate Spec YAML and (b) an English description of a desired change, emit a **delta** YAML document that lists only the slot entries to add or remove. A downstream merger applies the delta against the existing Spec.

## Output contract

- Emit raw YAML only. No prose. No code fences. No commentary.
- The first line of output must be `version: 1`.
- Output nothing after the YAML.
- Include only the categories/slots that change. Omit everything that stays the same.
- An entry under a slot means "add this entry to that slot".
- An entry under a slot prefixed with `-` (a removal list `removed`) means "remove this entry from that slot".

### Delta shape

```
version: 1
<category>:
  <subkey>:                   # e.g. network.outbound, fs.read
    required: [ ... ]         # entries to add to required
    allowed:  [ ... ]         # entries to add to allowed
    forbidden:[ ... ]         # entries to add to forbidden
    removed:                  # entries to remove (any slot)
      required: [ ... ]
      allowed:  [ ... ]
      forbidden:[ ... ]
```

`removed` is optional. Slots are optional. Categories are optional. Emit only what changes.

## Input format

You will receive a single prompt body containing two sections, in this order:

```
EXISTING SPEC:
<yaml>

CHANGE REQUEST:
<english or plan text>
```

Read both. Treat the existing Spec as ground truth. Encode only the deltas the change request implies.

## Rules

1. **Closed-world default still applies.** If the request says "we may also call X", that is `allowed`. Only "must call" is `required`. Only "must never" is `forbidden`.
2. **Don't restate.** If `api.stripe.com` is already in `network.outbound.allowed` and the request reaffirms it, omit it from the delta — it's a no-op.
3. **Slot moves are an add + remove.** Promoting an entry from `allowed` to `required` is `required: [X]` plus `removed.allowed: [X]`.
4. **Don't invent effects.** Only encode what the change request explicitly names.
5. **Normalize values to taxonomy form.** Hostnames lowercase, no scheme/port/path. Subprocess basename only. Imports top-level package. Tables lowercase.
6. **No top-level changes.** Don't touch `version`, `unresolved_handling`, or `stdlib_auto_allow`. Always emit `version: 1`.
7. **Empty delta is legal.** If the request implies no changes, emit only `version: 1`.

## Few-shot examples

The `examples/` sibling directory contains worked existing-Spec + change-request → delta pairs.

- `examples/01-add-allowed-host.md`
- `examples/02-add-fs-read.md`
- `examples/03-promote-allowed-to-required.md`
- `examples/04-remove-forbidden.md`
