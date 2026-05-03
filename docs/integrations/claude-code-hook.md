# Claude Code hook integration

Wire `spectate review` into Claude Code's hook system so drift Findings
surface in your CC session before the next agent action overwrites them.

## What it does

Registered as a `PreToolUse` hook on `Write|Edit|MultiEdit`, the
`spectate-cc-hook` script:

1. Reads the CC hook payload from stdin.
2. Looks for `<project>/.spectate/spec.yaml` (per-project only at v1).
3. If the spec exists, runs the Spectate Watch + Critique pipeline.
4. If any `missing-required`, `added-forbidden`, or `added-unspecified`
   Finding is present, emits an `additionalContext` payload listing a
   summary line plus up to the first five Findings per bucket.
5. Otherwise: silent pass-through. The hook never blocks the tool call —
   Spectate is a drift detector, not a security gate. Run
   `spectate review` for the full bulletin.

If `.spectate/spec.yaml` is absent the hook no-ops silently, so it is
safe to enable globally.

Latency target: under 1s on a clean repo.

## Install

After `pip install spectate` (which exposes the `spectate-cc-hook`
console script), add the hook to either your user-global
`~/.claude/settings.json` or your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "spectate-cc-hook"
          }
        ]
      }
    ]
  }
}
```

That's it. Open a CC session in a project that has
`.spectate/spec.yaml`, edit a file, and any drift will appear in the
next turn's context.

## See also

- Claude Code hooks reference: <https://code.claude.com/docs/en/hooks>
- `spectate review --help` for the full bulletin and exit codes
