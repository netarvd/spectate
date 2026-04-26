# Example 4 — "non-goals" / "must not" become forbidden slots

Plan:

> # Stripe webhook handler
>
> ## Goals
> Receive Stripe webhook events and write them to the `webhook_events` table.
>
> ## Components
> - HTTP endpoint, no outbound calls except to `api.stripe.com` for event verification.
>
> ## Non-goals
> - Must not call any other external host.
> - Must never invoke `curl` or `wget` from the handler process.
> - Must never write to disk.

YAML:

---
version: 1

network:
  outbound:
    allowed:
      - api.stripe.com

subprocess:
  forbidden:
    - curl
    - wget

fs:
  write:
    forbidden:
      - /**

db:
  write:
    required:
      - webhook_events
