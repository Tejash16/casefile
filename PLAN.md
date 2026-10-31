# Casefile: build plan for ContextCon 03, IIT Bombay (Sat 31 Oct 2026) — two people, six sessions

**What we ship:** `casefile investigate` takes an insider tip plus a company's ledger, vendor master and staff list, and returns an audit-committee case file in which every sentence is cited to a ledger row or a Crustdata record, every tool call sits in a hash-chained log, and each allegation is **Substantiated**, **Unfounded** or **Unsubstantiated**. Zero human steps between the command and the file.

**Win condition for the video:** one cold-start command on a held-out case; the hidden career link found, the false lead refuted, the clean vendor cleared; one citation clicked through to its record; `casefile verify` passing, then failing after one byte is changed.

Research behind every choice: `docs/research-brief.md`. Nothing from the three-person plan is cut; the six workstreams are the same, split three per person.

---

## 1. Team and sessions

Two people, six Claude Code sessions, three per laptop, each in its own git worktree, each owning its own directories. Nobody edits outside their directories; changes to shared files go through a1. The split keeps dependencies on one laptop: B's three sessions are the data pipeline in order (ingest → Crustdata → rules), A's three are the spine and the output (contract and CLI → agents → audit and report).

| Person | Role on the day | Session | Owns | First prompt to paste |
| --- | --- | --- | --- | --- |
| **A** (Tejash) | Merge captain, product owner, demo driver | **a1** | `src/casefile/{schemas.py, pipeline.py, cli.py, stubs/}`, `pyproject.toml`, `README.md` | `docs/session-briefs/A1-contract-cli.md` |
| | | **a2** | `src/casefile/agents/` | `docs/session-briefs/A2-agents.md` |
| | | **a3** | `src/casefile/audit/`, `src/casefile/report/`, `tests/` (structure, harness), `verify.py` | `docs/session-briefs/A3-audit-report-eval.md` |
| **B** | Data pipeline owner, demo narrator | **b1** | `src/casefile/ingest/`, `fixtures/`, `cases/` | `docs/session-briefs/B1-ingest-data.md` |
| | | **b2** | `src/casefile/crustdata/`, `src/casefile/resolve/` | `docs/session-briefs/B2-crustdata-resolve.md` |
| | | **b3** | `src/casefile/rules/`, `src/casefile/graph/` | `docs/session-briefs/B3-rules-graph.md` |

Each person runs three terminals (tmux with three panes, or three Claude tabs in VS Code: `Ctrl/Cmd+Shift+Esc` opens a new one). Session names match the table so sessions can message each other as `@a1`, `@b3`, etc.

---

## 2. Running three sessions each without losing accuracy (the attention protocol)

Three sessions per person works only if each session can run 30 to 45 minutes unattended. The briefs are written for that: each starts with a long, self-contained first task, every interface is in `docs/contract.md`, and sessions message each other instead of waiting for you.

- **Start in `acceptEdits` mode** (`claude --worktree a2 --name a2 --permission-mode acceptEdits`): file edits inside the worktree never block; shell commands still ask. That removes most of the prompts that would otherwise stall a session while you are looking at another one.
- **Stagger starts by two minutes** (session 1, then 2, then 3) so their first questions do not arrive together.
- **Round-robin every 10 to 15 minutes:** glance at terminal 1, 2, 3; answer prompts; read the last status line. Every brief tells the session to end each turn with one line: `STATUS: <done> | NEXT: <next step> | BLOCKED: <who>`.
- **Let sessions ask each other, not you.** Interface questions go `@a1`; "is X on main yet" goes to the owning session. You are the human of last resort, not the message bus.
- **Use the idle notice:** in one session, "Tell me when @b2 finishes" so you are told when a sibling needs you.
- **`/handoff` at 12:15 and 14:00** in every session (one line each to `@a1`), **`/review` before any merge** larger than 200 lines. The review is a fresh-context subagent inside the session, so it costs you no attention.
- **One human decision rule:** if a session asks a question the brief or the contract already answers, reply "see brief / see contract section N" and move on; if it needs a real decision, decide fast and write the decision into the session as one line.
- **Never run two sessions on the same directory.** Ownership is per session, not per person.

---

## 3. Timeline (IST)

| Time | Everyone | A (a1 a2 a3) | B (b1 b2 b3) |
| --- | --- | --- | --- |
| 07:30–08:15 | Read `PLAN.md`, your three briefs, `docs/contract.md`. Install and check tools (section 4). Fill `docs/dataset-design.md` together on a call: fictional company name, 12 real vendor candidates, both of your LinkedIn URLs and past employers, the tip text. | Create empty GitHub repo `casefile`, add B as collaborator. No code pushed. | Check Python 3.12, `uv`, `claude --version` ≥ 2.1.236 on both laptops; tmux or three VS Code tabs ready. |
| 08:15–09:00 | Travel. Laptops charged, chargers packed, college ID. | | |
| 09:00–09:30 | Check-in, badge, **Crustdata API key** each. `export CRUSTDATA_API_KEY=...` and `export ANTHROPIC_API_KEY=...` in every shell. `curl` to `/account/credits` works. | | |
| 09:30–10:00 | Kickoff. Listen for any change to judging or rules. | | |
| 10:00–10:30 | Crustdata API walkthrough. Ask the five questions in section 6. Confirm Identify on 3 of your vendor names and Person Search on one of your names with curl (reading data is not coding). | | |
| **10:30** | **Code starts.** Launch sequence, section 5. | a1 10:30: init repo from kit, push, skeleton, `schemas.py`, stubs. a2 10:33: agent client + propose prompt. a3 10:36: hash-chained log + `verify.py`. | b1 10:32: fixtures first, then loaders. b2 10:34: Crustdata client, limiter, cache. b3 10:36: rule registry + ledger tests. |
| 10:45 | `main` has `pyproject.toml`, package skeleton, `schemas.py`, fixture stubs. Every session: `git pull --rebase origin main && uv sync`. | | |
| 10:45–12:30 | **Build block 1.** Core of each workstream against `contract.md`. Push every 30 minutes; rebase before each push. Round-robin your three terminals every 10 to 15 minutes. | a1: pipeline end-to-end on stubs by 11:15, CLI 11:30, then integration glue. a2: propose 11:30, match 12:00, critique 12:40. a3: log + Merkle + verify 11:15 (announce to all), tamper tests 11:30, renderer 12:15. | b1: fixtures 10:50 (announce), loaders 11:45, `ledger_stats` 12:15. b2: identify + enrich + cache + offline 11:30, person search + enrich 12:00, resolve vendors 12:30. b3: T04–T09, T12 by 11:45; master tests T01–T03, T07, T10, T11, T14 by 12:30; graph 12:45. |
| **12:30** | **Checkpoint 1** (10 min, both laptops side by side). Pass: `casefile investigate` on `fixtures/` runs end to end with real Crustdata resolution, real log, rendered file; stubs allowed only in agents or rules. Eat at the desk. Nobody goes to the lightning talks. | | |
| 12:40–14:15 | **Build block 2.** Real everything. Planted cases run. | a1: `--redact` plumbing, metrics panel, README with Mermaid picture and eval table. a2: gate 13:00, writer with `search_result` + citations 14:00, cache hits confirmed 14:15. a3: citation check 12:45, redaction 13:00, eval harness 14:00, metrics panel 14:00. | b1: `cases/gen.py` with all six planted cases (incl. `shared_office_honest`) on main by 14:00; held-out case generated and stored outside the repo. b2: Haiku disambiguation wired to a2's `agents.match` 13:15, resolve staff 13:15, founders 13:45. b3: T13, T15, T17 by 13:45, `rerank` 13:45, full test suite under 2 s. |
| 13:30 | Mentor checkpoint (optional, 10 min). B takes a laptop to a Crustdata engineer; B's three sessions keep running on their current tasks. A keeps all six in view only loosely; B's sessions queue questions. | | |
| **14:15** | **Feature freeze. Checkpoint 2.** Pass: all planted cases correct 3/3; `verify.py` passes and fails on tamper; README has the eval table; the held-out case has never been run. Anything not passing is cut (section 9), not fixed. | | |
| 14:15–14:45 | Polish and one full rehearsal of the demo script on a planted case (not the held-out one). Terminal font 18pt, dark theme, notifications off. OBS on A's laptop. | A drives. | B narrates and times with a phone. |
| **14:45–15:15** | **Record.** Three full takes on the held-out case, cold start. Pick the best, trim to 2:00, export 1080p. | | |
| 15:15–15:30 | Final push: README, video link, tag `v1.0`. **Submit by 15:30.** Confirm receipt. | | |
| 15:30–17:00 | Eat. Warm the `--offline` cache for the live run. Prepare three answers: endpoints used and 429 handling; how false accusations are avoided; what the log proves. | | |
| 17:00 | Finalists announced. | | |
| 17:30 | Live final: run the held-out case live, same script; if the network fails, `--offline`. | A drives. | B answers judges. |

---

## 4. Before 10:30: allowed preparation (no code)

The rules allow "ideas, system sketches, and architecture blueprints" and "set up your accounts and tools". The kit is markdown and config. Writing Python before 10:30 is not allowed; do not do it.

- [ ] Python 3.12 and `uv` on both laptops (`uv --version`).
- [ ] Claude Code ≥ 2.1.236 (`claude --version`), logged in; VS Code extension installed; one test `claude --worktree test` then exit and `git worktree prune`.
- [ ] tmux (three panes) or three VS Code Claude tabs tested on each laptop.
- [ ] `gh` CLI logged in on A's laptop.
- [ ] Anthropic API key with credit on each laptop (`ANTHROPIC_API_KEY`), separate from the Claude Code login.
- [ ] Screen recorder tested (OBS or QuickTime or Xbox Game Bar), microphone tested, 1080p.
- [ ] `docs/dataset-design.md` filled in on a call: company name, vendor candidates, both LinkedIn URLs and past employers, tip text, thresholds.
- [ ] Each person has read their three briefs and `docs/contract.md`.
- [ ] A has created the empty GitHub repo and invited B.
- [ ] Kit unzipped at `~/casefile-kit` on A's laptop.

---

## 5. Launch sequence at 10:30 (minute by minute)

**A, terminal 1 (10:30–10:36):**

```bash
mkdir ~/casefile && cd ~/casefile
git init -b main
cp -r ~/casefile-kit/. . && rm KIT-README.md
cp .env.example .env            # fill CRUSTDATA_API_KEY and ANTHROPIC_API_KEY
git add -A && git commit -m "[kit] plan, CLAUDE.md, briefs, rules, config"
git remote add origin git@github.com:<you>/casefile.git
git push -u origin main
claude --worktree a1 --name a1 --permission-mode acceptEdits   # paste docs/session-briefs/A1-contract-cli.md
```

**A, terminals 2 and 3 (10:33, 10:36):**

```bash
cd ~/casefile && claude --worktree a2 --name a2 --permission-mode acceptEdits   # paste A2-agents.md
cd ~/casefile && claude --worktree a3 --name a3 --permission-mode acceptEdits   # paste A3-audit-report-eval.md
```

**B, three terminals (10:32, 10:34, 10:36):**

```bash
git clone git@github.com:<you>/casefile.git ~/casefile && cd ~/casefile
cp .env.example .env            # fill both keys
claude --worktree b1 --name b1 --permission-mode acceptEdits   # paste B1-ingest-data.md
# terminal 2
cd ~/casefile && claude --worktree b2 --name b2 --permission-mode acceptEdits   # paste B2-crustdata-resolve.md
# terminal 3
cd ~/casefile && claude --worktree b3 --name b3 --permission-mode acceptEdits   # paste B3-rules-graph.md
```

**Everyone at 10:45**, when a1 has pushed the skeleton (a1 messages all sessions):

```bash
git pull --rebase origin main   # inside each worktree
uv sync                          # creates .venv in that worktree
uv run casefile --help           # must print the CLI
```

Until then, code against `docs/contract.md`; the first 15 minutes are for files that need no shared imports (client, loaders, log, prompts).

---

## 6. Five questions for the Crustdata engineers at 10:00

1. What `confidence_score` on Company Identify should we treat as a safe auto-accept, and when should we fall back to `exact_match: false`?
2. For small companies (under 10 people), is `headcount.timeseries` populated, and how is `year_founded` sourced?
3. What are the MCP tool names, and is there a dry-run mode that costs no credits? (Docs point to `crustdata://catalog/tools` and `crustdata://catalog/dry-run`.)
4. Is Person Identify (by email) enabled on hackathon keys, or should we go name + employer through Person Search only?
5. If we hit 429 on `/company/enrich` at 15 RPM with 25 companies per request, is the batch counted as one request?

---

## 7. Integration checkpoints

**Checkpoint 1, 12:30.** `uv run casefile investigate --tip fixtures/tip.txt --ledger fixtures/ledger.csv --vendors fixtures/vendors.csv --staff fixtures/staff.csv --out out/fixture/` completes; `out/fixture/case_file.md`, `log.jsonl`, `evidence.json` exist; vendors and staff show Crustdata IDs; `uv run casefile verify out/fixture/log.jsonl` passes. Agents or rules may still be stubs.

**Checkpoint 2, 14:15.** `uv run pytest -q` green; `uv run python tests/eval_harness.py` shows every planted case correct on all three runs; the sentence-to-evidence check rejects a deliberately uncited sentence; README has the eval table; `--redact` works; the held-out case exists and has not been run.

---

## 8. Merge protocol

- Branches are the worktree branches (`worktree-a1` ... `worktree-b3`). Push your branch every 30 minutes, more often when something lands that others need.
- Before every push: `git fetch origin && git rebase origin/main && uv run pytest -q tests/<your module>`. The `/sync` skill does all of it.
- Merge to `main` yourself when your tests pass and you touched only your directories.
- Conflicts or changes to `schemas.py`, `pipeline.py`, `cli.py`: message `@a1` and a1 makes the change. A is the only human who resolves conflicts.
- Commit messages start with your session tag: `[b2] identify + enrich with disk cache`.
- Never force-push `main`. Never commit `.env`, `out/`, `.cache/`.

---

## 9. Cut list (drop in this order if behind at 14:15)

1. PDF export (Markdown is enough; judges read GitHub).
2. Web Search / Web Fetch enrichment of vendors.
3. Benford test T08 (keep threshold-band test T05).
4. Metrics panel in the case file (keep it in the terminal output).
5. Haiku disambiguation (fall back to threshold-only resolution with `unresolved` state).
6. Founders match T17.
7. Velocity test T12 and dormant test T10.

Never cut: the six-stage pipeline running end to end, the hash-chained log and verifier, citations on every sentence, the three verdicts with the coded gate, the planted cases with the false lead and the clean control, the video.

---

## 10. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| A person is pulled away (mentor checkpoint, food, judges) | Their three sessions keep working on their current task; every brief has 30 to 45 minutes of autonomous work per task. Queue questions; the other person does not touch those sessions. |
| Crustdata 429s or outage during the recording | `--offline` reads the disk cache from an earlier run on the same case; the log records `cache_hit: true`. Warm the cache before 14:45 on a different planted case; the held-out case's recording run is the cold run. If the network is down at 14:45, record with `--offline` and say so on camera. |
| A team member's LinkedIn has no past employer in Crustdata | Use a vendor's `people.founders` from Company Enrich as the planted staff link instead; names redacted in the video. |
| A session falls behind | The owner of the dependent module uses the stub for that stage; cut list applies at 14:15. |
| Anthropic API rate limits | Three call sites only; Haiku for matching; cached prefix; retries with backoff. |
| Crustdata credits | Account holds 15,200 credits (read 10:27). Enrich by ids only (2 per returned match); never `batch_*` (403 on plan). Not a constraint; rate limits are. |
| Worktree confusion | `git worktree list`; each session prints `pwd` in its first message. |
| Rule 4 (no contact with real people) | The agent has no email, phone or outreach tool. Grep the repo for `smtp`, `twilio`, `sendgrid` before submission. |

---

## 11. Definition of done for submission (15:30)

- Public GitHub repo with README (what it is, one command, architecture picture, eval table, verifier instructions, Crustdata endpoints used, team).
- `uv run casefile investigate ...` works from a fresh clone with the two keys set.
- `cases/` contains the planted cases and `expected.json`; `tests/eval_harness.py` reproduces the eval table.
- `verify.py` passes on the submitted `out/demo/log.jsonl`.
- Two-minute video uploaded (YouTube unlisted or Drive) and linked at the top of the README.
- Tag `v1.0`.

---

## Repo layout

```
casefile/
├── README.md                      judge-facing: command, picture, eval table, verify, endpoints
├── CLAUDE.md                      memory for every session: commands, ownership, conventions
├── PLAN.md                        this file
├── .mcp.json                      Crustdata MCP server for Claude Code sessions (${CRUSTDATA_API_KEY})
├── .worktreeinclude               copies .env into each worktree
├── .gitignore
├── .env.example
├── pyproject.toml                 created by a1 at 10:30 (see A1 brief)
├── verify.py                      standalone log verifier (a3)
├── .claude/
│   ├── settings.json              hooks: ruff format on every edit
│   ├── rules/                     per-directory rules Claude loads when touching those paths
│   └── skills/                    /handoff, /sync, /review
├── docs/
│   ├── research-brief.md          the research doc, exported
│   ├── contract.md                THE shared contract: objects, fields, function signatures, test registry
│   ├── typologies.md              ACFE typology menu and the tests per typology (prompt material)
│   ├── dataset-design.md          worksheet for the planted dataset (fill before 10:30)
│   ├── demo-script.md             the two-minute script, shot by shot
│   └── session-briefs/            A1, A2, A3, B1, B2, B3 first prompts
├── src/casefile/
│   ├── schemas.py                 Pydantic models from contract.md (a1)
│   ├── pipeline.py                six stages wired together (a1)
│   ├── cli.py                     Typer CLI: investigate, verify (a1)
│   ├── stubs/                     canned stage implementations for integration (a1)
│   ├── agents/                    propose, match, critique, gate, write; prompts/ (a2)
│   ├── audit/                     hash-chained log, Merkle root (a3)
│   ├── report/                    Jinja2 templates, sentence-evidence check, redaction (a3)
│   ├── ingest/                    loaders, normalisation, data-quality notes (b1)
│   ├── crustdata/                 HTTP client, limiter, cache, offline (b2)
│   ├── resolve/                   vendor and person resolution (b2)
│   ├── rules/                     T01–T17 as pure functions, thresholds config (b3)
│   └── graph/                     NetworkX build and path evidence (b3)
├── fixtures/                      tiny messy ledger/vendors/staff + canned Crustdata JSON (b1)
├── cases/                         planted cases: inputs + expected.json; gen.py (b1)
├── tests/                         pytest per module; eval_harness.py (a3)
└── out/                           generated case files (gitignored except out/demo/)
```
