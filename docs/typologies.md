# Typology menu (prompt material for the proposer; from the ACFE fraud tree)

The proposer may only choose from this list. Each entry: what the scheme is, what it looks like in the data, which tests apply, and what would refute it. Verdict wording in the case file follows investigative practice: Substantiated, Unfounded, Unsubstantiated. Never "guilty".

| id | ACFE branch | What it is | Ledger / master signals | Crustdata signals | Tests | Refuted by |
| --- | --- | --- | --- | --- | --- | --- |
| `shell_company` | Asset misappropriation → billing scheme | An employee sets up a company that bills for goods or services never delivered | Vendor shares address, phone, bank or tax id with staff; no PO or receiving; round amounts; vendor created days before first invoice; sequential invoice numbers | Headcount 0–2 or no record; no website; `year_founded` just before first payment; HQ residential or mail drop; founders match a staff name | T01 T02 T03 T06 T07 T09 T11 T13 T16 T17 | Headcount ≥ 50 with website (T13); patterns match population (T06/T07) |
| `pass_through` | Billing scheme variant | An employee-owned intermediary buys from a real supplier and resells at a markup | Invoices mirror a genuine supplier's cadence; margin visible if both appear | Tiny headcount; same officers as a staff member | T01 T13 T15 T16 T17 | Vendor is an established distributor with staff (T13) |
| `conflict_of_interest` | Corruption → purchasing scheme | An approver steers spend to a company they or family have an undisclosed interest in | One approver, rising spend, sole-source; approval just under limit | Approver's career history includes the vendor, dates overlapping or shortly before payments; founders match | T05 T12 T15 T16 T17 | Resolved person with no employment at vendor (T15); spend share normal (T12) |
| `kickback` | Corruption → bribery | Vendor pays the approver to win or keep business | Vendor's share of category spend climbs; prices above peers; fast approvals; threshold band | Vendor headcount flat while invoice volume climbs | T05 T06 T09 T12 T15 | Share and velocity normal (T12) |
| `non_accomplice_vendor` | Billing scheme | Fake or inflated invoices routed through a real, unknowing vendor | Duplicate invoices, same number + amount, overbilling, refunds to employee | Large established company | T04 T05 T06 | No duplicates; patterns match population (T04) |
| `duplicate_billing` | Billing scheme | Same invoice paid twice or re-submitted | Same vendor + amount within 30 days; same invoice number; same number + amount across vendors | — | T04 T14 | No duplicates (T04) |
| `threshold_structuring` | Control circumvention | Invoices split or sized to stay under an approval limit | Cluster in the 5% band under the approver's limit; splits summing over the limit within days | — | T05 T06 T11 | Band share matches population (T05) |
| `ghost_vendor` | Billing scheme | A dormant or fictitious vendor record used to divert payments | Payment after long dormancy; bank or address change then reversed; vendor created and approved by same user | No record in Crustdata; no footprint | T02 T07 T10 T11 T13 T14 | Resolved established company (T13) |

## Hypothesis statement form

Worst-case, one sentence, ids not names: "Approver S004 steered INR 48.6 lakh over 14 invoices to vendor V017, a company S004 worked for until 2024-11 (conflict_of_interest)."

## Statistics on which this menu rests (ACFE Report to the Nations 2026)

Tips detect 43% of cases; billing schemes are 21% of cases with median loss $90,000 and median duration 14 months; "unusually close association with a vendor or customer" is a red flag in 17% of perpetrators; organisations with proactive data monitoring cut median loss by 53%. Sources in `docs/research-brief.md` section 2.
