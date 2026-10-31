Test registry. Each test is deterministic code that emits evidence objects; it supports, refutes or is neutral on a hypothesis. Use only these ids.

| id | name | family | typologies | supports when |
| --- | --- | --- | --- | --- |
| T01 | vendor_staff_identifier_match | identity | shell_company, pass_through, ghost_vendor | vendor and a staff member (or two vendors) share address, phone, bank account, tax id or email; a coworking address alone is neutral |
| T02 | thin_vendor_footprint | footprint | shell_company, ghost_vendor | PO box / residential / virtual address, or missing phone + tax id + website |
| T03 | vendor_age_vs_first_payment | timing | shell_company | vendor created or founded shortly before its first invoice |
| T04 | duplicate_invoices | billing | duplicate_billing, non_accomplice_vendor | same vendor + amount within 30 days, same invoice no., or same no. + amount across vendors |
| T05 | threshold_structuring | billing | threshold_structuring, kickback | invoices in the band just under the approver's limit; splits summing over the limit within days |
| T06 | round_amounts | billing | shell_company, kickback | vendor's share of round amounts well above the population's |
| T07 | sequential_invoice_numbers | billing | shell_company, ghost_vendor | invoice numbers gap-free or in a narrow range for one vendor |
| T08 | benford_population | statistical | screen only | first-two-digit spikes on the whole population; a lead, never proof |
| T09 | off_hours_postings | control | shell_company, kickback | postings or approvals on weekends, holidays or at night |
| T10 | dormant_vendor_reactivated | timing | ghost_vendor | payment after a year or more of no activity |
| T11 | segregation_of_duties | control | shell_company, ghost_vendor | same user created the vendor and approved or posted its invoices |
| T12 | velocity_and_share | billing | kickback, conflict_of_interest | vendor spend growth or category share well above normal |
| T13 | existence_and_capacity | footprint | shell_company, pass_through | Crustdata: unresolved, tiny headcount, no website, or billed volume per head too high; refutes when headcount is large and a website exists |
| T14 | lookalike_vendor_names | identity | duplicate_billing, ghost_vendor | near-identical names under different ids, or one tax id under several ids |
| T15 | career_overlap | identity | conflict_of_interest, pass_through | approver's Crustdata employment at the vendor overlaps or ends shortly before the payment window; refutes when the person is resolved and has no employment there |
| T16 | graph_path | graph | all | a short path between approver and vendor via shared attributes or Crustdata ids |
| T17 | founders_match | identity | shell_company, pass_through | vendor founders or decision makers match a staff name |

Refuting evidence: T13 refutes shell_company for a large company with a website; T15 refutes conflict_of_interest when the person is resolved with no employment at the vendor; T04/T05/T06 refute billing typologies when the vendor's patterns match the population.
