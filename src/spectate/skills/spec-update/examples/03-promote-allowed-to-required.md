# Example 3 — promote an allowed host to required (slot move = add + remove)

EXISTING SPEC:

```
version: 1

network:
  outbound:
    allowed:
      - api.stripe.com
      - api.openai.com
```

CHANGE REQUEST:

> Calling api.stripe.com is now mandatory — the service must call it.

DELTA:

---
version: 1

network:
  outbound:
    required:
      - api.stripe.com
    removed:
      allowed:
        - api.stripe.com
