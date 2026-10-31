# Planted cases

Each subdirectory is one case: `tip.txt`, `ledger.csv`, `vendors.csv`, `staff.csv`, `case.json` (format in `docs/contract.md` section 8). All six are written by `cases/gen.py` with fixed seeds; design, Crustdata ids and the checks behind every name are in `docs/dataset-design.md`.

```bash
uv run python cases/gen.py --all          # rewrites the six directories below, byte for byte
uv run pytest -q tests/ingest/test_cases.py
```

Audited company: Halvexa Precision Components Pvt Ltd (fictional), Pune; ledger FY 2024-25 and 2025-26; about 80 rows and 10 vendors per case. Every case carries the same messiness as `fixtures/`: BOM, CRLF, a trailing-space header with synonyms that change by seed, one blank row, one repeated header, three date formats, four amount formats (`4,98,000`, `498000.00`, `₹ 4,98,000.00`, `Rs. 4,98,000`), vendor spelling variants, and approver names in lower case or as initials. Every case also contains the clean controls V001 Tata Steel and V002 Bharat Forge, V003 Sundram Fasteners, and V008, a fictional vendor that must come back `unresolved`.

| case | seed | plant | expected | must_clear |
| --- | --- | --- | --- | --- |
| `career_overlap` | 1000 | S004 Tejash Chauhan (team member, LinkedIn URL) approves all 6 invoices of V017 DocRack, 2025-06 to 2026-03, growing 2.1L → 4.6L. Crustdata: S004 is Co-Founder at DocRack (71095782) from 2026-03-01. V017 was created by S004 and has no website | conflict_of_interest [S004] [V017] Substantiated | every real clean vendor |
| `shell_vendor` | 1001 | V023 Brindora Engineering Traders (fictional, no Crustdata record) shares address and phone with S003 (spelled differently). Created 2025-01-10 by S003, who posts and approves its 8 sequential, round invoices of 4,90,000–4,99,000 under his 5L limit; first on a Saturday, half after 22:00 | shell_company [V023] Substantiated (**open**: see note below) | every real clean vendor |
| `false_lead` | 1002 | The tip says S005 Kedar Sharma (team member, LinkedIn URL) used to work at V031 HCLTech. A namesake in Noida (person 6677240) did; S005 (person 420958731) never did and approves nothing | conflict_of_interest [S005] [V031] Unfounded | V031 + every real clean vendor |
| `duplicate_billing` | 1003 | One V003 Sundram Fasteners invoice paid again 6–14 days later, same number and amount, through V044 "Sundram Fastenrs Limited": a look-alike copy of V003's master record (same website) created a few weeks earlier. Two independent families: billing (T04, same number and amount across vendors) and identity (T14, look-alike names under two ids) | duplicate_billing [V003] Substantiated; V003 itself is not a shell | every real clean vendor except V003 (V044 is not listed) |
| `clean_controls` | 1004 | The tip accuses V001 and V002; nothing is planted | none | every real vendor |
| `shared_office_honest` | 1005 | V041 TechLadd (958646) and V042 E Giraffes Digital (615149) are real, unrelated tenants of WeWork Futura, Magarpatta Road, Pune; the tip calls them a ring. They share no phone, bank, tax id, email or staff link | none | V041, V042 + every real vendor |

**Open (A / a2):** the gate forces `Unsubstantiated` when any subject or object is not `resolved`, and V023 is fictional, so it is always `unresolved`. `shell_vendor` therefore cannot reach `Substantiated` until the gate scopes that rule to Crustdata-dependent evidence. `SHELL_VERDICT` in `gen.py` is one line to change once A decides.

**Known noise:** S005 Kedar Sharma is also DocRack's co-founder (Crustdata, from 2025-06). Only the held-out case has both S004/V017 and S005 on one staff list; S005 approves nothing, so T15 support stays at 0.5, below the gate's 0.6.

The held-out case (`--shuffle-ids`, a different seed, different ids, staff names, shell name and unresolved vendor) lives outside the repo until the recording.
