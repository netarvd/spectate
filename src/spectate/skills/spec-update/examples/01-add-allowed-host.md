# Example 1 — add a new allowed outbound host

EXISTING SPEC:

```
version: 1

network:
  outbound:
    allowed:
      - api.stripe.com
```

CHANGE REQUEST:

> The service may also call api.openai.com.

DELTA:

---
version: 1

network:
  outbound:
    allowed:
      - api.openai.com
