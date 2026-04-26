# Example 1 — single allowed outbound host

English:

> This service may only call api.stripe.com.

YAML:

---
version: 1

network:
  outbound:
    allowed:
      - api.stripe.com
