# Example 2 — add a filesystem read to a Spec that has none

EXISTING SPEC:

```
version: 1

network:
  outbound:
    allowed:
      - api.stripe.com
```

CHANGE REQUEST:

> The service also reads /etc/config.yaml at startup.

DELTA:

---
version: 1

fs:
  read:
    allowed:
      - /etc/config.yaml
