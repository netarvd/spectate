# Example 3 — filesystem and subprocess slots

English:

> The build script may write anywhere under /tmp and read ./config.yaml. It must invoke git, may invoke rg or jq, and must never invoke curl or wget.

YAML:

---
version: 1

fs:
  read:
    allowed:
      - ./config.yaml
  write:
    allowed:
      - /tmp/**

subprocess:
  required:
    - git
  allowed:
    - rg
    - jq
  forbidden:
    - curl
    - wget
