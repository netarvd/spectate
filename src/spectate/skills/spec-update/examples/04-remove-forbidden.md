# Example 4 — drop a previously forbidden host

EXISTING SPEC:

```
version: 1

network:
  outbound:
    allowed:
      - api.stripe.com
    forbidden:
      - tracking.example.com
```

CHANGE REQUEST:

> The forbidden tracking.example.com restriction no longer applies — drop it.

DELTA:

---
version: 1

network:
  outbound:
    removed:
      forbidden:
        - tracking.example.com
