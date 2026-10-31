---
paths:
  - "src/casefile/agents/**"
---

# Agent rules

- Three call sites only: propose (strong model, temperature 0.3), match (fast model, temperature 0), critique and write (strong model, temperature 0). All through `agents/client.py`, which logs pre/post audit records and marks static system blocks with `cache_control`.
- XML tags with consistent names: `<tip>`, `<typologies>`, `<ledger_stats>`, `<vendors>`, `<staff>`, `<candidates>`, `<candidate index="n">`, `<hypothesis>`, `<evidence id="E12" test="T15" direction="supports" strength="0.9">`, `<instructions>`. Long data first, instructions last.
- Structured output through strict tool schemas or `output_config.format`, validated with Pydantic, at most 2 retries. Never prefill. Never combine citations with structured output in one call.
- The writer is the only call using the Citations API, over `search_result` blocks built from evidence objects. The model never sees raw ledger rows or raw tool output.
- The model never decides a verdict; `agents/gate.py` does, deterministically, per `docs/contract.md` section 7.
- Prompts live in `agents/prompts/*.md` and are loaded at runtime.
