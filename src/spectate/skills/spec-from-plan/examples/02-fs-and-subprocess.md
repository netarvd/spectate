# Example 2 — filesystem and subprocess from a build-tool plan

Plan:

> # Release packaging tool
>
> ## Goals
> Produce a signed tarball under `/tmp/release/` from a clean checkout.
>
> ## Side effects
> - Reads `./pyproject.toml` to determine the version.
> - Writes the tarball under `/tmp/release/**`.
>
> ## External binaries
> - Must invoke `git` to verify the working tree is clean.
> - May invoke `tar` and `gpg` to build and sign the tarball.

YAML:

---
version: 1

fs:
  read:
    allowed:
      - ./pyproject.toml
  write:
    allowed:
      - /tmp/release/**

subprocess:
  required:
    - git
  allowed:
    - tar
    - gpg
