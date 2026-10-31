# Planted dataset worksheet

Data design is allowed before coding starts. Everything here feeds `cases/gen.py` (session b1) and the demo. Hackathon rule 4: the agent never contacts anyone; Crustdata records are real people and companies, so the allegations are about our **fictional** ledger, phrased as facts about records, and names are redacted in the public video.

Filled by b1 at 11:40 on 31 Oct. Every real vendor was checked with `POST /company/identify` (free, 0 credits) on 31 Oct; ids and confidences below are from those calls. Fixtures in `fixtures/` use exactly these choices.

## 1. The audited company (fictional)

| item | value |
| --- | --- |
| Name | Halvexa Precision Components Pvt Ltd (Identify: no Halvexa match; top hit is an unrelated 0.6 "Renata Precision Components") |
| Sector | precision components |
| City | Pune |
| Ledger period | 2024-04-01 to 2026-03-31 (two financial years) |
| Approval limits | Manager INR 5,00,000; Senior Manager INR 10,00,000; Director INR 25,00,000 |

## 2. Staff (8)

`POST /person/identify` (email) returns 403 on our key (b2, 11:36), so anyone who must resolve to one specific real person needs a `linkedin_url` in `staff.csv`. Staff without a URL fall back to Person Search by name and employer, which finds nobody at a fictional employer, so they stay `unresolved`.

| staff_id | name | LinkedIn URL | role in the ledger | past employers Crustdata should have | planted role |
| --- | --- | --- | --- | --- | --- |
| S001 | Meera Kulkarni (fictional) | | Director - Finance, limit 25L | | clean |
| S002 | Vikram Shah (fictional) | | Senior Manager, limit 10L | | clean |
| S003 | Anil Deshpande (fictional; `Mr. Anil Deshpande` in the list, `A. Deshpande` in the ledger) | | Manager - Procurement, limit 5L, creates vendors | | shell vendor owner (address and phone shared with V023) |
| S004 | team member A (**pending**; placeholder `Rohan Joshi` in fixtures) | **pending** | Manager - Procurement, limit 5L, approver | **pending** (becomes V017) | career-overlap conflict (true positive) |
| S005 | team member B (**pending**; placeholder `Rahul Verma` in fixtures) | **pending** | Analyst, no approval limit | **pending** | false lead: the tip says S005 used to work at V031. A real namesake did; our S005 (resolved by LinkedIn URL) did not, so T15 refutes and the verdict is `Unfounded` |
| S006 | Sunita Patil (fictional) | | AP clerk, posts entries | | clean |
| S007 | Farhan Qureshi (fictional) | | Manager - Procurement, limit 5L | | clean |
| S008 | Priya Nair (fictional) | | Manager - Finance, limit 5L | | clean |

Change from the original worksheet: the false lead uses team member B (consent is ours, and the profile resolves live) instead of a fictional common name, because a fictional S005 could only end `unresolved`, which forces `Unsubstantiated`, never `Unfounded`. V031 is then whichever real company a namesake of B demonstrably worked at (found with Person Search, exact mode).

## 3. Vendors (12)

Resolve real vendors by **website domain** or by the suffix-stripped name, not the legal name: on 31 Oct, "Tata Steel Limited" returned a Borivali branch (id 28232275, 0.8) on top and "Cummins India Ltd" returned "Valvoline Cummins" (0.8) on top, while "Tata Steel" and "Cummins India" returned the right records at 1.0.

| vendor_id | name in vendors.csv (ledger variants) | real? | Crustdata id (identify query, confidence) | employee range | planted role |
| --- | --- | --- | --- | --- | --- |
| V001 | Tata Steel Limited (`TATA STEEL LTD`) | yes, large | 5042 ("Tata Steel", 1.0) | 10001+ | clean control (must_clear) |
| V002 | Bharat Forge Ltd | yes, large | 646 ("Bharat Forge Ltd", 1.0) | 10001+ | clean control (must_clear) |
| V003 | Sundram Fasteners Limited (`Sundram Fasteners Ltd.`) | yes, large | 4860 ("Sundram Fasteners", 1.0) | 1001-5000 | duplicate billing (non_accomplice_vendor) |
| V004 | Mahindra Logistics Ltd | yes, large | 2885 ("Mahindra Logistics", 1.0) | 10001+ | clean |
| V005 | Blue Dart Express Ltd | yes, large | 736 ("Blue Dart", 1.0; "Blue Dart Express" only 0.6) | 10001+ | clean |
| V006 | Pune Metrology | yes, small | 72073831 ("Pune Metrology", 0.8), punemetrology.in | 2-10 | clean |
| V007 | Atomic Gauges | yes, small | 15339565 ("Atomic Gauges", 1.0), atomicgauges.co.in | 2-10 | clean (kickback velocity optional) |
| V008 | Zentravik Industrial Supplies Pvt Ltd | fictional | none (top hit unrelated, 0.6) | none | expected `unresolved` → any allegation Unsubstantiated |
| V009 | Castool Precision Tooling | yes, small | 2310938 ("Castool Precision Tooling", 1.0), castool.com | 2-10 | clean |
| V017 | **pending** S004's past employer (placeholder `Persistent Systems Limited`, id 3647, in fixtures; variants `PERSISTENT SYSTEMS`, `Persistant Systems Ltd`) | yes | pending | | conflict of interest, true positive |
| V023 | Brindora Engineering Traders Pvt Ltd (`BRINDORA ENGINEERING TRADERS PRIVATE LIMITED`, `Brindora Enginering Traders`) | fictional | none (no Brindora match; top hit unrelated, 0.6) | none | shell: address and phone = S003's; created 2025-01-10, first invoice 2025-01-18; round amounts 4,90,000–4,99,000 under S003's 5L limit |
| V031 | **pending** a company a namesake of team member B worked at (placeholder `Cummins India Ltd`, id 1085, in fixtures) | yes | pending | | false lead, expected Unfounded for S005 |

Rejected: "Orbital Fasteners" (the brief's example shell name) collides with a real UK company, Orbital Fasteners Ltd (id 9469227); "Quorvane" exists (id 69779436); "Larsen & Toubro" returns two 1.0 matches (2744 and 28126659).

For `shared_office_honest` (gen.py): two small real vendors registered at one coworking address, to be picked at 13:00 and listed here.

## 4. The tip (fixture version; S005 and V017/V031 names swap when the pending rows are filled)

```
Subject: procurement payments - please look

I work in finance at Halvexa. For the last year a manager in procurement has been pushing payments to Brindora Engineering Traders and Persistent Systems. Brindora didn't exist before January and nobody on the shop floor has seen anything delivered from them. Their invoices are always just under five lakh and some get approved late at night. I also heard Rahul Verma used to work for Cummins India and still gets them contracts. Something is off with how fast these get approved. Please look at the invoices from last year. I'd rather not say who I am.
```

## 5. Thresholds we will state as assumptions

| name | value | why |
| --- | --- | --- |
| new_vendor_days | 90 | FinCEN alert language "recent incorporation"; Vona heuristic |
| threshold_band_pct | 5 | standard CAAT band under approval limits |
| shell_headcount_max | 2 | FATF/FinCEN "no personnel or a single person" |
| career_gap_days | 365 | close association within a year of payments |
| identify_accept | 0.85 | Crustdata confidence; observed: correct records at 1.0 for clean names, branches and lookalikes at 0.8, unrelated at 0.6 |

## 6. Held-out case

Same generator, different seed, different planted ids and vendor names, generated by b1 at 14:45, stored in a private gist, never run before the recording.
