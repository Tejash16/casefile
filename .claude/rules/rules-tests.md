---
paths:
  - "src/casefile/rules/**"
  - "src/casefile/graph/**"
---

# Rule-test rules

- Pure functions `(ctx) -> list[EvidenceObject]`. No I/O, no network, no model calls, no randomness.
- Every threshold comes from `rules/config.py` `THRESHOLDS` with a name, value, unit, rationale and source URL. No literal numbers in a test.
- Every evidence object has a one-sentence `summary` without a verdict, a literal `quote` a reviewer can find by row id, `source.refs`, and a `sha256` of the quoted payload.
- Emit refuting evidence when a pattern matches the population; the gate needs it to return Unfounded.
- Benford only on the whole population with n ≥ `benford_min_n`, strength cap 0.4.
- Register every test in `rules/registry.py` with its families and typologies; the proposer picks by id.
