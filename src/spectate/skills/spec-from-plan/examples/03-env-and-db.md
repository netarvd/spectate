# Example 3 — env vars and database tables

Plan:

> # Audit log replicator
>
> ## Configuration
> - Reads `DATABASE_URL` (required) for the source connection.
> - Reads `LOG_LEVEL` (optional).
>
> ## Data flow
> - Reads from the `audit_events` table.
> - Writes summarized rows to the `audit_log` table.

YAML:

---
version: 1

env:
  read:
    required:
      - DATABASE_URL
    allowed:
      - LOG_LEVEL

db:
  read:
    required:
      - audit_events
  write:
    required:
      - audit_log
