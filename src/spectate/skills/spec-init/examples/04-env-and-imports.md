# Example 4 — env vars and imports

English:

> The agent reads OPENAI_API_KEY (required) and may read LOG_LEVEL. It uses the requests library and may use httpx, but must never import pickle.

YAML:

---
version: 1

imports:
  required:
    - requests
  allowed:
    - httpx
  forbidden:
    - pickle

env:
  read:
    required:
      - OPENAI_API_KEY
    allowed:
      - LOG_LEVEL
