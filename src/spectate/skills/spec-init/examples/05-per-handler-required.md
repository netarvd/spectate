# Example 5 — per-handler required scope

English:

> Every login, logout, and reset_password handler in auth/views.py must call the session-check helper. The helper itself is allowed everywhere.

YAML:

---
version: 1

subprocess:
  required:
    - handler: auth/views.py::login
      value: session-check
    - handler: auth/views.py::logout
      value: session-check
    - handler: auth/views.py::reset_password
      value: session-check
  allowed:
    - session-check
