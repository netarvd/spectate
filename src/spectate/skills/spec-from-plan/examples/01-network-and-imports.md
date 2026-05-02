# Example 1 — network and imports from a small plan

Plan:

> # Weather sync worker
>
> ## Goals
> Pull current conditions from the National Weather Service API every 15 minutes
> and republish to our internal events bus.
>
> ## Components
> - HTTP client using `httpx` against `api.weather.gov`.
> - Publisher using `kafka-python` against the internal broker.
>
> ## Dependencies
> - `httpx` for HTTP.
> - `kafka-python` for the broker.

YAML:

---
version: 1

network:
  outbound:
    required:
      - api.weather.gov

imports:
  required:
    - httpx
    - kafka-python
