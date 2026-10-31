# Casefile: project memory for every Claude Code session

Casefile is an autonomous forensic-audit agent for ContextCon 03 (IIT Bombay, 31 Oct 2026). Input: an insider tip plus a company's ledger, vendor master and staff list. Output: an audit-committee case file where every sentence is cited to a ledger row or a Crustdata record, every tool call is in a hash-chained log, and each allegation is Substantiated, Unfounded or Unsubstantiated. Zero human intervention between the command and the file.

Two humans run six sessions (three each), so you will often work 30 to 45 minutes without a human reply. Work from your brief and `docs/contract.md`; ask other sessions by message before asking a human; end every turn with one line: `STATUS: <done> | NEXT: <next step> | BLOCKED: <who or none>`.

Read before writing code: `PLAN.md` (who owns what, timeline), `docs/contract.md` (the shared objects and signatures), your session brief in `docs/session-briefs/`.

## Commands

```bash
uv sync                                   # install into this worktree's .venv
uv run casefile investigate --tip fixtures/tip.txt --ledger fixtures/ledger.csv \
  --vendors fixtures/vendors.csv --staff fixtures/staff.csv --out out/fixture/
uv run casefile verify out/fixture/log.jsonl
uv run pytest -q tests/<your-module>       # your tests only, before every push
uv run pytest -q                           # full suite, before merging to main
uv run python tests/eval_harness.py        # planted cases, 3 runs each
uv run ruff format . && uv run ruff check --fix .
```

## Ownership (never edit outside your directories)

| Session | Human | Directories |
| --- | --- | --- |
| a1 | A | `src/casefile/schemas.py`, `pipeline.py`, `cli.py`, `stubs/`, `pyproject.toml`, `README.md`, `PLAN.md` |
| a2 | A | `src/casefile/agents/` |
| a3 | A | `src/casefile/audit/`, `src/casefile/report/`, `tests/` (structure and harness), `verify.py` |
| b1 | B | `src/casefile/ingest/`, `fixtures/`, `cases/` |
| b2 | B | `src/casefile/crustdata/`, `src/casefile/resolve/` |
| b3 | B | `src/casefile/rules/`, `src/casefile/graph/` |

Each session may create its own `tests/<module>/` directory. Need a change in someone else's directory? Send that session a message (you can: "Tell @a1 that Entity needs a `confidence` field") and carry on with a local shim until it lands. Shared files (`schemas.py`, `pipeline.py`, `cli.py`) change only through a1.

## Conventions

- Python 3.12, `uv`, `ruff`. Type hints everywhere. Pydantic v2 models from `docs/contract.md` are the only data structures that cross module boundaries.
- Pure functions for rules: `(ctx) -> list[EvidenceObject]`. No I/O, no model calls inside `rules/` or `graph/`.
- Model calls happen only in `agents/`, through `agents/client.py`. Three call sites: propose, match, critique/write. Nowhere else.
- Network calls happen only in `crustdata/client.py` (Crustdata) and `agents/client.py` (Anthropic). No other hosts. No email, phone, Slack or outreach of any kind (hackathon rule 4).
- Every external call and every rule test goes through `audit.log` with a pre-execution and a post-execution record. If the audit module has not landed yet, use the shim from `docs/contract.md` section 9 and swap later.
- Every fact that reaches the case file is an `EvidenceObject` with a literal `quote`, a `source` (ledger row ids or Crustdata record id + `updated_at`) and a `sha256`. The writer never sees raw tool output.
- Thresholds are named config in `rules/config.py`, printed in the case file under "Assumptions". Never hard-code a number in a test.
- Verdicts come from `agents/gate.py` (deterministic), not from the model. The model proposes a verdict and a rationale; the gate decides and logs any override.
- Unresolved entities are a legal state (`resolution.status == "unresolved"`), and any allegation depending on one is `Unsubstantiated` by rule.
- Temperature 0 for match and critique. Structured output (strict tool schemas) for anything another module consumes. XML tags in prompts: `<tip>`, `<typologies>`, `<ledger_stats>`, `<candidates>`, `<evidence id="E12">`, `<instructions>`. Long data first, instructions and question last.
- Never log or print secrets. `.env` is gitignored. Read keys from `CRUSTDATA_API_KEY` and `ANTHROPIC_API_KEY`.
- Tests live in `tests/<module>/`. A module is done when its tests pass on `fixtures/`.

## Crustdata quirks (see docs/research-brief.md section 3)

- Headers: `authorization: Bearer $CRUSTDATA_API_KEY`, `x-api-version: 2025-11-01`, `content-type: application/json`. Base `https://api.crustdata.com`.
- `POST /company/identify` is free: resolve names there first (25 per call), check `confidence_score` and `primary_domain`, never trust `matches[0]` blindly. Then `POST /company/enrich` **by `crustdata_company_ids` only** (2 credits per returned match; a name or domain can match several companies and cost N×2), 25 per call, with explicit `fields: ["basic_info","headcount","locations","people","funding"]`.
- Staff resolution order: email → `POST /person/identify` (enabled, 1 credit per match); else LinkedIn URL → `POST /person/enrich`; else name + employer → `POST /person/search` with `mode: "exact"`, then enrich the returned `profile_url`. `preview: true` on enrich is free. Cite the top-level `updated_at` only (`basic_profile.last_updated` is plan-gated and empty). Never call `batch_*` endpoints (403 on our plan).
- 429 carries `X-RateLimit-Reset` (seconds) and sometimes `Retry-After`; back off and retry. Enrich is 15 RPM, Identify and Search 30 RPM. 402 means no credits.
- Every response: store raw body + `X-Credits-Used` + `X-Request-Id` in `.cache/crustdata/<sha256(request)>.json`. `--offline` reads only the cache and logs `cache_hit: true`.
- Cite a record as `crustdata:company:<id>@<updated_at>` or `crustdata:person:<id>@<updated_at>`.

## Git

- You are in a worktree on branch `worktree-<session>`. Commit often with `[<session>] message`. Before every push: `git fetch origin && git rebase origin/main && uv run pytest -q tests/<your module>`.
- Merge to `main` yourself only when your tests pass and you touched only your directories. Conflicts go to a1 (the human A).
- Never commit `.env`, `out/` (except `out/demo/` and `out/eval/`), `.cache/`, `.venv/`.
- Use `/sync` to rebase, test and merge, `/handoff` to write a status note and commit, `/review` to get a fresh-context review of your diff.

## Definition of done (14:15 freeze)

`uv run casefile investigate` on every case in `cases/` produces the expected verdicts three runs out of three; `verify.py` passes and fails on a tampered log; a sentence without an evidence id fails the render; README has the eval table.
