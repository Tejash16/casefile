# Two-minute demo script (record 14:45, three takes, held-out case, cold start)

Setup: 1080p, terminal font 18pt+, dark theme, notifications off, A drives, B narrates and times with a phone; OBS records on A's laptop. Dataset: 10 vendors, 8 staff so the cold run finishes in about 90 seconds; speed up the middle 2x in the edit if needed.

| Time | On screen | Voice-over |
| --- | --- | --- |
| 0:00–0:15 | Tip text file and the three messy CSVs side by side; cursor highlights "Orbital Fastners" vs "ORBITAL FASTENERS PRIVATE LIMITED" and a `14-Mar-25` date | "An anonymous tip, a ledger nobody cleaned, a vendor list and a staff list. This is what a forensic auditor starts with. Casefile does the whole investigation." |
| 0:15–0:25 | Terminal: `uv run casefile investigate --tip tip.txt --ledger ledger.csv --vendors vendors.csv --staff staff.csv --out out/demo/` | "One command. No human in the loop from here." |
| 0:25–1:05 | Rich progress: hypotheses listed by typology; "identify 12 vendors → 11 resolved, 1 unresolved"; a `429 retry in 4s` line; "enrich 11 companies, 22 credits"; "person search S004 → 1 candidate → enrich"; rule tests T01–T17 firing with evidence counts; gate decisions | "It turns the tip into hypotheses from the ACFE fraud tree, resolves every vendor and person in Crustdata's identity graph, and tests each hypothesis with coded rules, not opinions. Every call you see is being written to a hash-chained log." |
| 1:05–1:35 | `out/demo/case_file.md` rendered: executive summary with three verdict badges; click `[E12]` → exhibit shows `employment[2]: Orbital Fasteners, Analyst, 2021-06-01 to 2024-11-30` beside `first payment 2025-02-03`; scroll to the Unfounded finding (two candidates considered, different employer and city); the cleared vendor line | "Substantiated: the approver worked at the vendor until three months before the first payment, per Crustdata's record updated last week. Unfounded: the person named in the tip is not the person who worked there. Cleared: a real company with 2,000 staff and normal invoices." |
| 1:35–1:50 | `python verify.py out/demo/log.jsonl` → "312 records, chain ok, root 9f3a…"; open the log, change one digit in record 40, run again → "FAIL: record 40 hash mismatch" | "Every tool call is in a tamper-evident log. Change one byte and verification fails." |
| 1:50–2:00 | README eval table: 5 planted cases, 3 runs each, precision, false-clear rate, citation validity 100% | "On planted cases it finds the hidden link, refutes the false lead and clears clean vendors, three runs out of three. Casefile." |

Rules: no slides, no title card over two seconds, say "a request it has never seen" out loud at 0:15. If Crustdata is unreachable at 14:45, run with `--offline` on the cache and say so on camera; the log shows `cache_hit: true` so it stays truthful.

Live final (17:30): same script, same held-out case, `--offline` ready; A drives, B answers the judges. Three answers prepared: endpoints used and 429 handling; how false accusations are avoided (coded gate, unresolved → Unsubstantiated, refuting evidence); what the log proves (chain, Merkle root, pre/post records, credits and request ids).
