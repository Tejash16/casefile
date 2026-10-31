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
| S004 | Tejash Chauhan (team member A) | https://www.linkedin.com/in/tejash-chauhan-5424a9252 | Manager - Procurement, limit 5L, approver | Crustdata person 177265563 (enrich 1.0): DocRack, Co-Founder, 2026-03-01 → current (company 71095782); Just, 2023-01 → 2023-06 (no company id) | career-overlap conflict (true positive) with V017 = DocRack |
| S005 | Kedar Sharma (team member B) | https://www.linkedin.com/in/kedar-sharma-67aa9b253 | Analyst, no approval limit | Crustdata person 420958731 (enrich 1.0): DocRack, Co-Founder, 2025-06 → current (71095782); Abhyuday IIT Bombay 2024-05 → 2025-04 (6121131); Just 2023-01 → 2023-06 (4562904) | false lead: the tip says S005 used to work at V031 (HCLTech). A namesake in Noida (person 6677240) did, 2023-02 → 2025-03; our S005 never did, so T15 refutes and the verdict is `Unfounded` |
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
| V009 | Fox Precision Tooling | yes, small | 8697742 (domain foxprecisiontooling.co.uk, 1.0) | 2-10 | clean (replaced Castool: castool.com resolves to 6938202, 118 staff) |
| V017 | DocRack (`DOCRACK`, `Docrak`) | yes, small | 71095782 ("DocRack", 1.0). **No website in vendors.csv on purpose**: docrack.ai resolves to a different record, "Orvyn Labs" (6337171) | 2-10 | conflict of interest, true positive: S004 co-founder from 2026-03-01; payments 2025-06-12 → 2026-03-19, all approved by S004 |
| V023 | Brindora Engineering Traders Pvt Ltd (`BRINDORA ENGINEERING TRADERS PRIVATE LIMITED`, `Brindora Enginering Traders`) | fictional | none (no Brindora match; top hit unrelated, 0.6) | none | shell: address and phone = S003's; created 2025-01-10, first invoice 2025-01-18; round amounts 4,90,000–4,99,000 under S003's 5L limit |
| V031 | HCL Technologies Ltd (`HCLTech`) | yes, large | 1910 (domain hcltech.com, 1.0; the name "HCLTech" alone gives three 1.0 matches) | 10001+ | false lead, expected Unfounded for S005 |

Known noise: S005 is also DocRack's co-founder (from 2025-06), so a Crustdata path S005–V017 exists in any case that contains both. S005 approves nothing; in single-plant cases only one of them is on the staff list.

**Open conflict (needs A / a2):** the gate forces `Unsubstantiated` when any subject or object is not `resolved` (CLAUDE.md says the same). V023 is fictional, so it is always `unresolved`, and every fictional staff member comes back `ambiguous` or `unresolved` (b2, 11:55). As written, the planted shell case (S003 + V023) can never be `Substantiated`, which contradicts `cases/README.md`. b2's proposal: apply the rule only when the hypothesis rests on Crustdata evidence about that entity (T13/T15/T17), and let T13 treat `unresolved` as support for shell_company. Until decided, `cases/shell_vendor/case.json` expects whatever A decides.

Rejected: "Orbital Fasteners" (the brief's example shell name) collides with a real UK company, Orbital Fasteners Ltd (id 9469227); "Quorvane" exists (id 69779436); "Larsen & Toubro" returns two 1.0 matches (2744 and 28126659).

For `shared_office_honest` (gen.py): two small real vendors registered at one coworking address, to be picked at 13:00 and listed here.

## 4. The tip (fixture version)

```
Subject: procurement payments - please look

I work in finance at Halvexa. For the last year a manager in procurement has been pushing payments to Brindora Engineering Traders and DocRack. Brindora didn't exist before January and nobody on the shop floor has seen anything delivered from them. Their invoices are always just under five lakh and some get approved late at night. I also heard Kedar Sharma used to work for HCLTech and still gets them contracts. Something is off with how fast these get approved. Please look at the invoices from last year. I'd rather not say who I am.
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
