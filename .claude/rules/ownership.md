---
paths:
  - "src/**"
  - "tests/**"
  - "cases/**"
  - "fixtures/**"
---

# Ownership

Check `CLAUDE.md` for the directory you are about to edit. If it belongs to another session, do not edit it: write a local shim in your own directory, and send the owning session a one-line message describing the change you need (for example "Tell @a1 that `VendorRecord` needs a `address_type` enum"). Shared files `schemas.py`, `pipeline.py`, `cli.py` and `pyproject.toml` are a1's only.

Before every push: `git fetch origin && git rebase origin/main && uv run pytest -q tests/<your module>`.
