# Casefile shared contract

This is the one document every session codes against. a1 transcribes it into `src/casefile/schemas.py` (Pydantic v2) in the first 15 minutes; until that lands, use these names and fields exactly. Changes to this contract go through a1 only.

Conventions: ids are strings; dates are ISO `YYYY-MM-DD`; money is `Decimal` in INR unless `currency` says otherwise; every object that leaves a module is one of these models.

## 1. Inputs

### Tip
| field | type | notes |
| --- | --- | --- |
| text | str | free text as received |
| received_at | str | ISO datetime |
| sha256 | str | hash of the raw file |

### LedgerRow
| field | type | notes |
| --- | --- | --- |
| row_id | str | `L000123`, stable, assigned at ingest |
| date | date | posting or invoice date, parsed |
| vendor_name_raw | str | as in the file |
| vendor_key | str | normalised key (see `normalize_company_name`) |
| vendor_id | str or None | filled after matching to VendorRecord |
| invoice_no | str or None | |
| amount | Decimal | positive = payment out |
| currency | str | default `INR` |
| approver_name_raw | str or None | |
| approver_id | str or None | filled after matching to StaffRecord |
| created_by | str or None | user who created the entry |
| posted_at | datetime or None | for off-hours test |
| description | str or None | |
| po_number | str or None | |
| bank_account | str or None | payee account if present |
| quality_flags | list[str] | e.g. `date_coerced`, `amount_lakh_format`, `vendor_spelling_variant` |

### VendorRecord
| field | type | notes |
| --- | --- | --- |
| vendor_id | str | `V017` from the master, or assigned |
| name_raw | str | |
| name_norm | str | lowercase, legal suffixes stripped (Pvt Ltd, Private Limited, LLP, Ltd, Inc, LLC, & Co) |
| address | str or None | |
| address_type | enum | `commercial`, `residential`, `po_box`, `virtual`, `coworking`, `unknown` (heuristic from text; `coworking` from `THRESHOLDS.coworking_markers`) |
| city, state, country | str or None | |
| phone, email, website | str or None | |
| tax_id | str or None | GSTIN or PAN if present |
| bank_account | str or None | |
| created_on | date or None | vendor master creation |
| created_by | str or None | |
| resolution | Resolution | see below |
| crustdata | CompanyFacts or None | filled by resolve |

### StaffRecord
| field | type | notes |
| --- | --- | --- |
| staff_id | str | `S004` |
| name_raw, name_norm | str | |
| title, department | str or None | |
| address, phone, email, bank_account | str or None | |
| joined_on | date or None | |
| approval_limit | Decimal or None | INR; threshold test uses this per approver |
| linkedin_url | str or None | if the staff list has it |
| resolution | Resolution | |
| crustdata | PersonFacts or None | |

## 2. Resolution and Crustdata facts

### Resolution
| field | type | notes |
| --- | --- | --- |
| status | enum | `resolved`, `ambiguous`, `unresolved`, `not_attempted` |
| method | enum or None | `domain`, `identify_exact`, `identify_fuzzy`, `person_identify_email`, `linkedin_url`, `person_search`, `llm_judge` |
| confidence | float or None | 0..1; Crustdata `confidence_score` or fuzzy score / 100 |
| candidates_considered | int | |
| log_record_id | str or None | the audit record of the deciding call |

### CompanyFacts
| field | type | notes |
| --- | --- | --- |
| crustdata_company_id | str | |
| name | str | |
| primary_domain, website, linkedin_url | str or None | |
| year_founded | int or None | |
| status | str or None | `active` / `deleted` |
| employee_count_range | str or None | |
| headcount_total | int or None | |
| headcount_timeseries | list[(date, int)] | may be empty |
| hq_city, hq_country, street_address | str or None | |
| founders, decision_makers | list[PersonBrief] | name, title, linkedin_url, start_date, end_date |
| total_funding_usd | Decimal or None | |
| description | str or None | |
| updated_at | str | from the record; part of every citation |
| source_request_id | str | `X-Request-Id` of the call |
| cache_hit | bool | |

### PersonFacts
| field | type | notes |
| --- | --- | --- |
| crustdata_person_id | str | |
| name | str | |
| profile_url | str | |
| current_title, current_company, location | str or None | |
| employment | list[Employment] | `company_name, crustdata_company_id, company_domain, title, start_date, end_date, is_current` |
| updated_at | str | |
| source_request_id | str | |
| cache_hit | bool | |

## 3. Hypotheses, evidence, findings

### Hypothesis
| field | type | notes |
| --- | --- | --- |
| hypothesis_id | str | `H1` |
| typology | enum | `shell_company`, `pass_through`, `conflict_of_interest`, `kickback`, `non_accomplice_vendor`, `duplicate_billing`, `threshold_structuring`, `ghost_vendor` (see `docs/typologies.md`) |
| statement | str | one sentence, worst-case form, as the ACFE method prescribes |
| subjects | list[str] | staff_ids |
| objects | list[str] | vendor_ids |
| tests_to_run | list[str] | test ids `T01`.. |
| prior_score | float | 0..1 from the proposer, re-ranked by rules + graph centrality |
| origin | enum | `tip`, `screen` (found by rules without the tip) |
| rationale | str | ≤ 2 sentences |

### EvidenceObject
| field | type | notes |
| --- | --- | --- |
| evidence_id | str | `E12`, assigned in order of creation |
| test_id | str | `T05` |
| hypothesis_ids | list[str] | may be empty for screening evidence |
| subject_ids, object_ids | list[str] | staff / vendor ids |
| direction | enum | `supports`, `refutes`, `neutral` |
| strength | float | 0..1, from the test's own scale |
| summary | str | one sentence, plain words, no verdict |
| quote | str | literal rows or fields, e.g. `L00042 2025-03-14 Orbital Fasteners 4,98,000 approver S004` or `employment[2]: Orbital Fasteners, Analyst, 2021-06-01 to 2024-11-30` |
| source | Source | below |
| sha256 | str | hash of the source payload the quote came from |
| log_record_id | str | audit record of the test run or call |

### Source
| field | type | notes |
| --- | --- | --- |
| kind | enum | `ledger_rows`, `vendor_master`, `staff_list`, `crustdata_company`, `crustdata_person`, `graph`, `derived_stat` |
| refs | list[str] | row ids, or `crustdata:company:<id>@<updated_at>` |
| as_of | str or None | record `updated_at` for Crustdata sources |

### Finding
| field | type | notes |
| --- | --- | --- |
| hypothesis_id | str | |
| verdict | enum | `Substantiated`, `Unfounded`, `Unsubstantiated` |
| verdict_by | enum | `gate`, `gate_override_of_model` |
| model_verdict | enum or None | what the critic proposed |
| supporting_evidence | list[str] | evidence ids |
| counter_evidence | list[str] | |
| confidence | float | from gate rules |
| amount_at_issue_inr | Decimal or None | sum of implicated ledger rows |
| rationale | list[Sentence] | each sentence carries evidence ids |
| data_gaps | list[str] | e.g. `vendor V017 unresolved in Crustdata` |

### Sentence
| field | type | notes |
| --- | --- | --- |
| text | str | |
| evidence_ids | list[str] | must be non-empty for anything in Findings or Executive Summary |

### CaseFile
| field | type | notes |
| --- | --- | --- |
| case_id, company_name, generated_at | str | |
| predication | Sentence | the tip, summarised |
| executive_summary | list[Sentence] | |
| scope | list[str] | period, row counts, sources |
| approach | list[str] | stages, endpoints, tests run |
| findings | list[Finding] | ordered Substantiated first |
| data_quality | list[str] | from ingest |
| assumptions | dict[str, str] | threshold name → value, from `rules/config.py` |
| exhibits | list[EvidenceObject] | every cited evidence object |
| metrics | dict | wall_seconds, crustdata_calls, credits_used, model_calls, tokens_in, tokens_out |
| merkle_root | str | |
| verify_command | str | |

## 4. Audit log

### LogRecord (one JSON object per line in `log.jsonl`)
| field | type | notes |
| --- | --- | --- |
| record_id | str | uuid4 |
| seq | int | 0.. |
| timestamp | str | ISO UTC with ms |
| agent_id | str | `casefile@<git sha>` |
| session_id | str | one per run |
| action_type | enum | `file_read`, `tool_call`, `model_call`, `rule_test`, `gate`, `render` |
| action_detail | dict | `name` (endpoint, test id, model), `args_sha256`, `model`, `prompt_sha256`, `cache_hit` |
| outcome | dict or None | `status`, `result_sha256`, `credits_used`, `request_id`, `tokens_in`, `tokens_out`, `evidence_ids`, `error` |
| record_phase | enum | `pre_execution`, `post_execution` |
| parent_record_id | str or None | post points at pre |
| prev_hash | str | SHA-256 of the previous record's canonical JSON (RFC 8785), 64 zeros for the first |
| record_hash | str | SHA-256 of this record's canonical JSON with `record_hash` omitted |

Merkle root (RFC 6962): leaf = SHA-256(0x00 ‖ record_hash bytes), node = SHA-256(0x01 ‖ left ‖ right), odd node promoted. Printed in the case file and in `out/<case>/root.txt`. `verify.py` recomputes the chain and the root and exits non-zero on any mismatch.

## 5. Function signatures (what each module exports)

```text
ingest.load_tip(path) -> Tip
ingest.load_ledger(path) -> tuple[list[LedgerRow], list[str]]            # rows, quality notes
ingest.load_vendors(path) -> tuple[list[VendorRecord], list[str]]
ingest.load_staff(path) -> tuple[list[StaffRecord], list[str]]
ingest.normalize_company_name(raw) -> str
ingest.normalize_person_name(raw) -> str
ingest.link_ledger(rows, vendors, staff) -> list[LedgerRow]                # fills vendor_id / approver_id by key

crustdata.client.CrustdataClient(api_key, cache_dir, offline=False, audit=AuditLog)
  .identify_companies(names: list[str], exact=True) -> list[IdentifyResult]
  .enrich_companies(ids: list[str], fields) -> list[CompanyFacts]
  .search_person(name, employer=None, location=None) -> list[PersonCandidate]
  .enrich_persons(profile_urls: list[str]) -> list[PersonFacts]
  .identify_persons(emails: list[str]) -> list[PersonCandidate]
  .describe_scope(dataset: "company"|"person") -> dict
  .credits() -> dict
resolve.resolve_vendors(vendors, client, judge=None) -> list[VendorRecord]   # judge = agents.match.judge_candidates
resolve.resolve_staff(staff, client, judge=None) -> list[StaffRecord]

rules.registry.TESTS: dict[str, Test]        # Test(id, name, typologies, fn, families)
rules.run_tests(test_ids, ctx: RuleContext) -> list[EvidenceObject]
rules.config.THRESHOLDS: dict[str, Threshold]  # Threshold(name, value, unit, rationale, source_url)
graph.build(rows, vendors, staff) -> networkx.Graph
graph.path_evidence(G, staff_id, vendor_id, max_len=3) -> EvidenceObject | None
graph.centrality(G) -> dict[str, float]

agents.propose.propose(tip, ledger_stats, vendors, staff, typologies) -> list[Hypothesis]
agents.match.judge_candidates(query: str, candidates: list[dict], kind: "company"|"person") -> MatchDecision  # yes/no/unsure + index
agents.critique.critique(hypothesis, evidence: list[EvidenceObject]) -> CriticOutput  # model_verdict, rationale sentences with evidence ids
agents.gate.decide(hypothesis, evidence, critic: CriticOutput, resolutions) -> Finding
agents.write.write_case_file(findings, evidence, meta) -> CaseFile          # Citations over search_result blocks

audit.log.AuditLog(path)
  .pre(action_type, detail) -> record_id
  .post(parent_record_id, outcome) -> record_id
  .merkle_root() -> str
report.render.render(case: CaseFile, out_dir, redact=False) -> Path         # case_file.md, exhibits.md, evidence.json, root.txt
report.check.check_citations(case: CaseFile, evidence_index) -> list[str]   # errors; empty = ok; render refuses if non-empty

pipeline.run(tip_path, ledger_path, vendors_path, staff_path, out_dir, offline=False, redact=False) -> CaseFile
```

## 6. Test registry (b3 implements; a2's proposer picks from these ids)

| id | name | families | typologies | supports when |
| --- | --- | --- | --- | --- |
| T01 | vendor_staff_identifier_match | identity | shell_company, pass_through, ghost_vendor | vendor and a staff member (or two vendors) share address, phone, bank account, tax id or email (exact or fuzzy ≥ 92); an address match at a `coworking` address is neutral unless phone, bank or tax id also match |
| T02 | thin_vendor_footprint | footprint | shell_company, ghost_vendor | PO box / residential / virtual address, or missing phone + tax id + website; a `coworking` address alone is not a signal |
| T03 | vendor_age_vs_first_payment | timing | shell_company | vendor `created_on` or Crustdata `year_founded` within `new_vendor_days` of first invoice |
| T04 | duplicate_invoices | billing | duplicate_billing, non_accomplice_vendor | same vendor + amount within 30 days, same invoice no., or same no. + amount across vendors |
| T05 | threshold_structuring | billing | threshold_structuring, kickback | invoices in the `threshold_band_pct` band under the approver's limit; splits summing over the limit within `split_window_days` |
| T06 | round_amounts | billing | shell_company, kickback | share of round amounts per vendor exceeds population share by `round_ratio_min` |
| T07 | sequential_invoice_numbers | billing | shell_company, ghost_vendor | invoice numbers gap-free or in a narrow range for one vendor |
| T08 | benford_population | statistical | screen only | first-two-digit spikes on the whole population, n ≥ 1000; strength capped at 0.4 (lead, not proof) |
| T09 | off_hours_postings | control | shell_company, kickback | postings or approvals on weekends, holidays or 22:00–06:00 |
| T10 | dormant_vendor_reactivated | timing | ghost_vendor | payment after ≥ 365 idle days |
| T11 | segregation_of_duties | control | shell_company, ghost_vendor | same user created the vendor and approved or posted its invoices |
| T12 | velocity_and_share | billing | kickback, conflict_of_interest | vendor spend growth or category share above `velocity_z` |
| T13 | existence_and_capacity | footprint | shell_company, pass_through | Crustdata: unresolved, headcount ≤ `shell_headcount_max`, no website, or billed volume per head above `volume_per_head_max` |
| T14 | lookalike_vendor_names | identity | duplicate_billing, ghost_vendor | names within fuzzy ≥ 90 but different ids, or same tax id under several ids |
| T15 | career_overlap | identity | conflict_of_interest, pass_through | approver's Crustdata employment at the vendor overlaps or ends within `career_gap_days` of the payment window; refutes when no such employment and record is resolved |
| T16 | graph_path | graph | all | NetworkX path of length ≤ 3 between approver and vendor via shared attributes or Crustdata ids |
| T17 | founders_match | identity | shell_company, pass_through | vendor founders / decision makers match a staff name (fuzzy ≥ 92) |

Refuting evidence: T13 refutes shell_company when headcount ≥ 50 and website present; T15 refutes conflict_of_interest when the person is resolved with high confidence and has no employment at the vendor; T04/T05/T06 refute billing typologies when the vendor's patterns match the population.

## 7. Gate rules (agents/gate.py, deterministic)

- `Substantiated`: ≥ 2 supporting evidence objects from ≥ 2 different families, each strength ≥ 0.6, and no refuting evidence with strength ≥ 0.7.
- `Unfounded`: ≥ 1 refuting evidence with strength ≥ 0.7 and no supporting evidence with strength ≥ 0.6.
- Otherwise `Unsubstantiated`.
- Any subject or object with `resolution.status != resolved` forces `Unsubstantiated` and adds a `data_gaps` entry, regardless of the model.
- If the gate's verdict differs from `model_verdict`, `verdict_by = gate_override_of_model` and a `gate` log record explains why.

## 8. Case JSON (cases/<name>/case.json)

```json
{
  "name": "career_overlap_true_positive",
  "inputs": {"tip": "tip.txt", "ledger": "ledger.csv", "vendors": "vendors.csv", "staff": "staff.csv"},
  "expected": [
    {"typology": "conflict_of_interest", "subjects": ["S004"], "objects": ["V017"], "verdict": "Substantiated"},
    {"typology": "shell_company", "objects": ["V023"], "verdict": "Unfounded"}
  ],
  "must_clear": ["V002", "V009"],
  "notes": "S004 is a team member whose LinkedIn shows employment at V017 until 2024-11."
}
```

## 9. Shim for the audit log (use until `audit/` lands)

Any module may start with a local `_audit.py` exposing `pre(action_type, detail) -> str` and `post(parent_id, outcome) -> str` that append plain JSON lines to `out/_shim_log.jsonl`. Replace the import with `from casefile.audit.log import AuditLog` when a3 announces it.
