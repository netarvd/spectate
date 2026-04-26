# Example 2 — required outbound host plus forbidden hosts

English:

> The exporter must call api.example.com to publish results, may also use any subdomain of example.com, but must never reach evil.com or its subdomains.

YAML:

---
version: 1

network:
  outbound:
    required:
      - api.example.com
    allowed:
      - "*.example.com"
    forbidden:
      - evil.com
      - "*.evil.com"
