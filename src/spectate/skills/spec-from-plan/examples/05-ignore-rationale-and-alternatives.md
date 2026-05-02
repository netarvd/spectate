# Example 5 — ignore rationale and "alternatives considered"

Plan:

> # Image thumbnailer
>
> ## Goals
> Generate thumbnails for uploads stored under `/var/uploads/**` and write them to `/var/thumbs/**`.
>
> ## Why a separate worker
> We previously did this inline in the upload handler, which slowed responses.
> Splitting it out lets the upload return faster and isolates image-processing
> CPU spikes from the request path. We also evaluated a hosted thumbnailing
> service but rejected it on cost grounds.
>
> ## Implementation
> - Uses `pillow` for image manipulation.
> - Reads source files from `/var/uploads/**`.
> - Writes thumbnails to `/var/thumbs/**`.
>
> ## Alternatives considered
> - ImageMagick via `convert` subprocess — rejected, harder to sandbox.
> - A managed service (e.g. imgix) — rejected, cost.

YAML:

---
version: 1

fs:
  read:
    required:
      - /var/uploads/**
  write:
    required:
      - /var/thumbs/**

imports:
  required:
    - pillow
