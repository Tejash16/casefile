# Case file: Audited company

| | |
| --- | --- |
| Case id | demo |
| Generated at | 2026-10-31T09:50:48+00:00 |
| Findings | 1 Substantiated, 2 Unfounded, 4 Unsubstantiated |
| Audit log | `log.jsonl`, 162 records at render time |
| Verify | `python verify.py out/demo/log.jsonl` |

**Merkle root:** `e9ac3a29d3fc0153211ff61b3a3cd6606249aa77bc4343f62309d41e4eb4a554` over 162 records (RFC 6962 over the audit log's record hashes)

*Person names are redacted to initials; staff ids and Crustdata record ids are unchanged.*

## 1. Background and predication

An insider tip received 2026-10-31T07:39:16+00:00 alleged: "Subject: procurement payments - please look I work in finance at Halvexa and I see most of the payment runs before they go out. I have kept quiet for a while because I could be wrong, but some things do not add up. For the last year a manager in procurement has been pushing payments to DocRack. They only started billing us in March, the amounts grow every month, and the same manager signs off …"

## 2. Executive summary

- H1 is Substantiated: vendor V017's Co-Founder T.C. has the same LinkedIn profile as staff member S004. [[E94]](#e94)
- H3 is Unfounded: V017's invoices sit just under the approver's limit no more often than the population (0.0% vs 0.0%), with no splits. [[E20]](#e20)
- H7 is Unfounded: none of vendor V001's 16 invoices repeats an invoice number or an amount within 30 days. [[E1]](#e1)
- H5 is Unsubstantiated, although Crustdata's record for vendor V017 shows headcount total 2. [[E60]](#e60)
- H6 is Unsubstantiated: vendor V008 has no matching Crustdata company record (resolution unresolved); its existence could not be confirmed. [[E56]](#e56)
- H4 is Unsubstantiated, although vendor V017's growth in spend is 2.9 standard deviations above the other 9 vendors. [[E50]](#e50)

## 3. Scope

- Ledger: 112 rows, 2024-04-26 to 2026-10-12
- Vendor master: 10 vendors; staff list: 8 staff
- External sources: Crustdata company and person records (offline cache)

## 4. Approach

- Ingest and normalise inputs
- Propose 7 hypotheses from a fixed ACFE typology menu
- Resolve vendors and staff against Crustdata
- Run deterministic tests: T01, T02, T03, T04, T05, T06, T07, T09, T10, T11, T12, T13, T14, T15, T16, T17; graph paths (T16)
- Fresh-context critique; deterministic gate decides each verdict

## 5. Findings

### 5.1 H1: conflict_of_interest — **SUBSTANTIATED**

| | |
| --- | --- |
| Verdict | **Substantiated** (decided by the coded gate; model proposed Substantiated) |
| Confidence | 0.79 |
| Subjects | S004 |
| Objects | V017 |
| Amount at issue | INR 21,73,588.25 |
| Origin | insider tip |

**Allegation tested:** Procurement manager S004 is the sole approver of all 8 invoices (INR 21.7 lakh) to vendor V017 and steered growing spend to it because of an undisclosed employment or ownership interest (conflict_of_interest).

**Rationale**

- S004's Crustdata employment record lists DocRack, Co-Founder, 2026-03-01 to present; first payment 2026-03-10 (L000077); last payment 2026-10-12 (L000112). [[E81]](#e81)
- Crustdata's company record for V017 lists person "T.C.", Co-Founder, https://www.linkedin.com/in/T.C.-5424a9252, and staff S004 "T.C." has linkedin.com/in/T.C.-5424a9252 (name score 100). [[E94]](#e94)
- V017's spend was 0 before 2025-07-19 and 21,73,588.25 from 2025-07-19 (growth z 2.9), and every listed invoice names approver S004. [[E50]](#e50)

**Supporting evidence:** [E81](#e81), [E94](#e94), [E95](#e95), [E50](#e50)

**Counter-evidence**

- None found.

### 5.2 H3: threshold_structuring — **UNFOUNDED**

| | |
| --- | --- |
| Verdict | **Unfounded** (decided by the coded gate; model proposed Unfounded) |
| Confidence | 0.70 |
| Subjects | S004 |
| Objects | V017 |
| Amount at issue | not quantified |
| Origin | screening rules, not in the tip |

**Allegation tested:** S004 sized or split V017 invoices to sit just under the INR 5 lakh approval limit so they escaped senior review and were approved quickly (threshold_structuring).

**Rationale**

- V017 had 0/8 invoices in the band, against a population rate of 0.0%. [[E20]](#e20)
- The amounts rise steadily from 1,15,972 inv DR/2026/585 to 4,26,822 inv DR/2026/1747. [[E20]](#e20)

**Counter-evidence**

- [E20](#e20) Vendor V017's invoices sit just under the approver's limit no more often than the population (0.0% vs 0.0%), with no splits.

### 5.3 H7: duplicate_billing — **UNFOUNDED**

| | |
| --- | --- |
| Verdict | **Unfounded** (decided by the coded gate; model proposed Unfounded) |
| Confidence | 0.70 |
| Subjects | S001 |
| Objects | V001 |
| Amount at issue | not quantified |
| Origin | screening rules, not in the tip |

**Allegation tested:** Vendor V001, the largest by spend at INR 2.7 crore and approved solely by S001, has been paid duplicate or resubmitted invoices (duplicate_billing).

**Rationale**

- The duplicate test over V001's 16 ledger invoices found no repeated invoice number and no repeated amount within 30 days. [[E1]](#e1)
- The quoted invoice numbers for V001 rise in sequence from TSL/31574 on 2024-04-26 to TSL/35143 on 2026-09-30, with no number appearing twice. [[E1]](#e1)
- The quoted posting dates for V001 are spaced weeks to months apart, and the amounts all differ, ranging from 12,25,048 to 22,18,776. [[E1]](#e1)
- All 16 V001 invoices list S001 as approver, but this concerns approval concentration rather than duplicate billing. [[E1]](#e1)
- The payee name appears in several spellings (TATA STEEL LTD, Tata Steel Ltd., Tata Steel Limited) within the single vendor V001. This evidence does not show whether invoices were also billed under another vendor record. [[E1]](#e1)

**Counter-evidence**

- [E1](#e1) None of vendor V001's 16 invoices repeats an invoice number or an amount within 30 days.

**Data gaps**

- staff S001 ambiguous in Crustdata

### 5.4 H5: pass_through — **UNSUBSTANTIATED**

| | |
| --- | --- |
| Verdict | **Unsubstantiated** (decided by the coded gate, overriding the model; model proposed Unfounded) |
| Confidence | 0.10 |
| Subjects | S004 |
| Objects | V017 |
| Amount at issue | not quantified |
| Origin | insider tip |

**Allegation tested:** V017 is an established document-management supplier with real headcount, and S004 has no employment or founder link to it, so the growth reflects a genuine new contract rather than a scheme by S004 (pass_through).

**Rationale**

- V017's Crustdata record shows headcount_total 2; website https://docrack.ai/. [[E60]](#e60)
- S004 is linked to vendor V017 in 3 steps through employment. [[E95]](#e95)

**Supporting evidence:** [E81](#e81), [E94](#e94), [E95](#e95), [E60](#e60)

**Counter-evidence**

- None found.

### 5.5 H2: shell_company — **UNSUBSTANTIATED**

| | |
| --- | --- |
| Verdict | **Unsubstantiated** (decided by the coded gate; model proposed Unsubstantiated) |
| Confidence | 0.10 |
| Subjects | S004 |
| Objects | V017 |
| Amount at issue | not quantified |
| Origin | insider tip |

**Allegation tested:** Vendor V017, created 2025-10-06 shortly before its first invoices, is a shell set up by S004 to bill for services never delivered (shell_company).

**Rationale**

- V017's Co-Founder T.C. has the same LinkedIn profile as staff member S004, and Crustdata's record for V017 shows headcount total 2. [[E60]](#e60) [[E94]](#e94)
- Against this, V017's invoice numbers advance by 166 on average between our invoices, consistent with a vendor billing many customers. [[E40]](#e40)
- V017's share of round amounts is no higher than the population's (0.0% vs 0.0%). [[E30]](#e30)

**Supporting evidence:** [E94](#e94), [E95](#e95), [E60](#e60)

**Counter-evidence**

- [E30](#e30) Vendor V017's share of round amounts is no higher than the population's (0.0% vs 0.0%).
- [E40](#e40) Vendor V017's invoice numbers advance by 166 on average between our invoices, consistent with a vendor billing many customers.

**Data gaps**

- test T01 produced no evidence for H2
- test T02 produced no evidence for H2
- test T03 produced no evidence for H2
- test T04 produced no evidence for H2
- test T05 produced no evidence for H2

### 5.6 H6: ghost_vendor — **UNSUBSTANTIATED**

| | |
| --- | --- |
| Verdict | **Unsubstantiated** (decided by the coded gate; model proposed Unsubstantiated) |
| Confidence | 1.00 |
| Subjects | S003 |
| Objects | V008 |
| Amount at issue | not quantified |
| Origin | screening rules, not in the tip |

**Allegation tested:** Vendor V008, created 2023-10 with a coined name and approved by S003, S007 and S008, is a fictitious record used to divert INR 15.1 lakh (ghost_vendor).

**Rationale**

- The vendor master lists V008 as "Zentravik Industrial Supplies Pvt Ltd", with Crustdata resolution unresolved after 25 candidates were considered. [[E56]](#e56)

**Supporting evidence:** [E56](#e56)

**Counter-evidence**

- None found.

**Data gaps**

- staff S003 ambiguous in Crustdata
- vendor V008 unresolved in Crustdata
- evidence E56 (T13) not counted: it rests on the Crustdata record of unresolved V008
- test T01 produced no evidence for H6
- test T02 produced no evidence for H6
- test T03 produced no evidence for H6
- test T05 produced no evidence for H6
- test T09 produced no evidence for H6

### 5.7 H4: kickback — **UNSUBSTANTIATED**

| | |
| --- | --- |
| Verdict | **Unsubstantiated** (decided by the coded gate; model proposed Unsubstantiated) |
| Confidence | 0.40 |
| Subjects | S004 |
| Objects | V017 |
| Amount at issue | INR 21,73,588.25 |
| Origin | insider tip |

**Allegation tested:** V017 pays S004 to keep fast-approved, rising-volume business while its billed volume outgrows its real capacity (kickback).

**Rationale**

- V017's spend went from 0 before 2025-07-19 to 21,73,588.25 from 2025-07-19. [[E50]](#e50)

**Supporting evidence:** [E50](#e50)

**Counter-evidence**

- None found.

**Data gaps**

- test T01 produced no evidence for H4
- test T05 produced no evidence for H4
- test T13 produced no evidence for H4

## 6. Data quality notes

- ledger.csv: UTF-8 byte-order mark removed.
- ledger.csv: Windows (CRLF) line endings.
- ledger.csv: column 'Amt ' had surrounding whitespace; trimmed.
- ledger.csv: columns mapped to the contract: 'Txn Date' -> date, 'Payee' -> vendor_name_raw, 'Invoice No' -> invoice_no, 'Amt' -> amount, 'Approved By' -> approver_name_raw, 'Created By' -> created_by, 'Posted At' -> posted_at, 'Description' -> description, 'PO Number' -> po_number, 'Beneficiary Account' -> bank_account.
- ledger.csv: 1 blank row(s) dropped (line 39).
- ledger.csv: 1 repeated header row(s) dropped (line 77).
- ledger.csv: 70 dates in a non-ISO format converted to YYYY-MM-DD [date_coerced]: L000001, L000002, L000003, L000004, L000005, L000006, L000009, L000011 and 62 more.
- ledger.csv: 30 dates with a two-digit year read as 20YY [date_two_digit_year]: L000001, L000002, L000005, L000013, L000027, L000028, L000029, L000034 and 22 more.
- ledger.csv: 55 amounts with a currency symbol (₹, Rs., INR) stripped [amount_currency_symbol]: L000001, L000003, L000007, L000008, L000010, L000013, L000014, L000015 and 47 more.
- ledger.csv: 67 amounts in lakh grouping (4,98,000) [amount_lakh_format]: L000001, L000002, L000003, L000006, L000007, L000008, L000010, L000013 and 59 more.
- ledger.csv: 14 amounts with comma grouping [amount_comma_grouping]: L000005, L000009, L000012, L000016, L000028, L000037, L000042, L000045 and 6 more.
- ledger.csv: 12 dates where day and month could swap, read day-first [date_ambiguous_dayfirst]: L000009, L000014, L000026, L000047, L000074, L000082, L000083, L000085 and 4 more.
- ledger.csv: 112 ledger rows loaded as L000001-L000112.
- vendors.csv: columns mapped to the contract: 'Vendor Code' -> vendor_id, 'Vendor Name' -> name_raw, 'Address' -> address, 'City' -> city, 'State' -> state, 'Country' -> country, 'Phone' -> phone, 'Email' -> email, 'Website' -> website, 'GSTIN' -> tax_id, 'Bank Account' -> bank_account, 'Created On' -> created_on, 'Created By' -> created_by.
- vendors.csv: V001 created_on '04-Dec-21' read as 2021-12-04 [date_coerced, date_two_digit_year].
- vendors.csv: V002 created_on '10-Mar-18' read as 2018-03-10 [date_coerced, date_two_digit_year].
- vendors.csv: V008 created_on '05-Oct-23' read as 2023-10-05 [date_coerced, date_two_digit_year].
- vendors.csv: V008 phone '020 2426 1180' normalised to '+912024261180'.
- vendors.csv: V010 created_on '21-Jan-22' read as 2022-01-21 [date_coerced, date_two_digit_year].
- vendors.csv: V013 created_on '08-Nov-18' read as 2018-11-08 [date_coerced, date_two_digit_year].
- vendors.csv: V017 created_on '06-Oct-25' read as 2025-10-06 [date_coerced, date_two_digit_year].
- vendors.csv: V017 phone '022 4971 3302' normalised to '+912249713302'.
- vendors.csv: 10 vendors loaded.
- staff.csv: columns mapped to the contract: 'Emp ID' -> staff_id, 'Full Name' -> name_raw, 'Designation' -> title, 'Department' -> department, 'Address' -> address, 'Mobile' -> phone, 'Email' -> email, 'Bank A/c' -> bank_account, 'Date of Joining' -> joined_on, 'Approval Limit' -> approval_limit, 'LinkedIn' -> linkedin_url.
- staff.csv: S001 joined_on '25/11/2021' read as 2021-11-25 [date_coerced].
- staff.csv: S001 approval_limit '25,00,000' read as 2500000 [amount_lakh_format].
- staff.csv: S001 phone '9850022994' normalised to '+919850022994'.
- staff.csv: S002 approval_limit '10,00,000' read as 1000000 [amount_lakh_format].
- staff.csv: S002 phone '9850071329' normalised to '+919850071329'.
- staff.csv: S003 name 'M.A.D.' normalised to 'anil deshpande'.
- staff.csv: S003 joined_on '14-Sep-17' read as 2017-09-14 [date_coerced, date_two_digit_year].
- staff.csv: S003 approval_limit '5,00,000' read as 500000 [amount_lakh_format].
- staff.csv: S003 phone '9850027080' normalised to '+919850027080'.
- staff.csv: S004 approval_limit '5,00,000' read as 500000 [amount_lakh_format].
- staff.csv: S004 phone '9850057740' normalised to '+919850057740'.
- staff.csv: S005 joined_on '22/04/2022' read as 2022-04-22 [date_coerced].
- staff.csv: S005 phone '9850097319' normalised to '+919850097319'.
- staff.csv: S006 joined_on '26/04/2020' read as 2020-04-26 [date_coerced].
- staff.csv: S006 phone '9850070039' normalised to '+919850070039'.
- staff.csv: S007 approval_limit '5,00,000' read as 500000 [amount_lakh_format].
- staff.csv: S007 phone '9850073894' normalised to '+919850073894'.
- staff.csv: S008 joined_on '23-Aug-17' read as 2017-08-23 [date_coerced, date_two_digit_year].
- staff.csv: S008 approval_limit '5,00,000' read as 500000 [amount_lakh_format].
- staff.csv: S008 phone '9850064490' normalised to '+919850064490'.
- staff.csv: 8 staff loaded.

## 7. Assumptions and thresholds

| Threshold | Value | Rationale | Source |
| --- | --- | --- | --- |
| `gate_support_min_strength` | 0.6 |  |  |
| `gate_refute_min_strength` | 0.7 |  |  |
| `gate_min_supporting_evidence` | 2 |  |  |
| `gate_min_test_families` | 2 (graph paths corroborate but do not count) |  |  |
| `gate_unresolved_entity` | evidence from its Crustdata record (T13, T15, T17) does not count |  |  |
| `new_vendor_days` | 90 days days | Vendor created or founded within this many days of its first invoice (T03). | https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf |
| `threshold_band_pct` | 5 % under limit % under limit | Invoices in this band just under the approver's limit look sized to avoid review (T05). | https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud |
| `band_ratio_min` | 2.0 x population x population | A vendor's in-band share must exceed the population's by this factor to support (T05). | https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud |
| `split_window_days` | 14 days days | Invoices each under the limit whose sum crosses it within this window are splits (T05). | https://www.journalofaccountancy.com/issues/2002/jul/billingschemespart1shellcompaniesthatdontdeliver/ |
| `round_unit_inr` | 1000 INR INR | An amount divisible by this is round (ends in 000) (T06). | https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf |
| `round_ratio_min` | 2.0 x population x population | A vendor's round-amount share must exceed the population's by this factor (T06). | https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf |
| `pattern_min_invoices` | 3 invoices invoices | Vendor-level pattern tests (T04-T07, T09) need at least this many invoices. | https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes |
| `pattern_min_hits` | 2 invoices invoices | A vendor-level pattern (band, round, off-hours) needs at least this many hits (T05, T06, T09). | https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes |
| `band_majority_share` | 0.5 share of invoices share of invoices | Above this share of a vendor's invoices in the band, T05 rates the pattern stronger. | https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud |
| `velocity_min_vendors` | 3 vendors vendors | Share and growth z-scores need at least this many paid vendors (T12). | https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf |
| `benford_full_z_mult` | 2.0 x benford_z x benford_z | A spike reaches the Benford strength cap at this multiple of benford_z (T08). | https://www.journalofaccountancy.com/issues/1998/nov/audit-nov-1998/ |
| `duplicate_window_days` | 30 days days | Same vendor and amount within this window is a possible duplicate payment (T04). | https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud |
| `sequential_min_invoices` | 5 invoices invoices | T07 needs this many numbered invoices: three in a row from a small supplier is normal. | https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes |
| `sequential_step_max` | 1.5 invoice numbers per invoice invoice numbers per invoice | Mean step between a vendor's invoice numbers at or below this: we are its only customer (T07). | https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes |
| `sequential_spread_min` | 25.0 invoice numbers per invoice invoice numbers per invoice | Mean step at or above this: the vendor bills many customers (T07 refutes). | https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes |
| `fuzzy_identifier_min` | 92 RapidFuzz score RapidFuzz score | Address and person-name matches at or above this score count as the same (T01, T15, T17). | https://www.cityoftulsa.org/media/2452/2015-vendortoemployeereport.pdf |
| `address_min_tokens` | 4 tokens tokens | Both addresses need this many tokens before a fuzzy match counts, so a bare city name never matches a full address (T01). | https://www.cityoftulsa.org/media/2452/2015-vendortoemployeereport.pdf |
| `lookalike_name_min` | 90 RapidFuzz score RapidFuzz score | Vendor names this close under different vendor ids are look-alikes (T14). | https://pages.caseiq.com/rs/219-YZJ-775/images/16-ways-to-identify-fictitious-vendors-version-2.pdf?version=0 |
| `coworking_markers` | ['regus', 'wework', 'awfis', '91springboard', 'virtual office', 'business centre', 'business center'] address terms address terms | An address containing one of these is a coworking address: shared by unrelated tenants, so an address match there is neutral unless phone, bank or tax id also match (T01), and it is not a thin-footprint signal by itself (T02). | https://www.fincen.gov/system/files/2026-05/FinCEN-Alert-IRGC.pdf |
| `personal_email_providers` | ['gmail', 'yahoo', 'ymail', 'hotmail', 'outlook', 'rediffmail', 'protonmail'] mail providers (first domain label) mail providers (first domain label) | A vendor using a personal mailbox has a thin footprint (T02). | https://www.osa.state.mn.us/audit-resources/audit-guidance/avoiding-pitfalls-articles/phantom-vendors |
| `shell_headcount_max` | 2 employees employees | Crustdata headcount at or below this is consistent with a shell (T13). | https://www.fincen.gov/system/files/2026-05/FinCEN-Alert-IRGC.pdf |
| `established_headcount_min` | 50 employees employees | Crustdata headcount at or above this, with a website, refutes a shell (T13). | https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf |
| `volume_per_head_max_inr` | 5000000 INR billed per employee INR billed per employee | Billed volume per Crustdata employee above this exceeds the vendor's capacity (T13). | https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf |
| `career_gap_days` | 365 days days | Employment at the vendor ending within this many days before the first payment counts as a career link (T15). | https://acfeinsights.squarespace.com/acfe-insights/2022/12/22/case-study-the-employee-and-vendor-nexus |
| `velocity_z` | 2.0 z-score z-score | Vendor spend share or growth this many standard deviations above other vendors (T12). | https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf |
| `velocity_sd_floor` | 0.25 x mean share; absolute on the -1..1 growth index x mean share; absolute on the -1..1 growth index | z-scores use at least this standard deviation, so near-equal vendors never look like outliers (T12). | https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf |
| `velocity_normal_z` | 1.0 z-score z-score | Share and growth both below this: spend pattern is normal (T12 refutes). | https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf |
| `benford_min_n` | 1000 rows rows | Benford first-two-digit test runs only on a population at least this large (T08). | https://core.ac.uk/download/67751317.pdf |
| `benford_z` | 1.96 z-score z-score | A first-two-digit bucket this far above Benford's expectation is a spike (T08). | https://www.journalofaccountancy.com/issues/1998/nov/audit-nov-1998/ |
| `off_hours` | (22, 6) hours (start, end) hours (start, end) | Postings between these local hours, on weekends or on national holidays are off-hours (T09). | https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf |
| `off_hours_ratio_min` | 2.0 x population x population | A vendor's off-hours share must exceed the population's by this factor (T09). | https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf |
| `holidays_mm_dd` | ['01-26', '08-15', '10-02'] dates dates | Indian national holidays treated as off-hours (T09). | https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf |
| `dormant_days` | 365 days days | A payment after this many idle days is a reactivated dormant vendor (T10). | https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf |
| `identify_accept` | 0.85 confidence confidence | Crustdata resolutions at or above this confidence are trusted enough to refute (T15). | https://docs.crustdata.com/company-docs/identify/introduction.md |
| `graph_max_len` | 3 edges edges | Longest staff-to-vendor path through shared attributes or Crustdata ids (T16). | https://arxiv.org/abs/2512.19491 |
| `quote_max_rows` | 25 rows rows | Longest list of ledger rows quoted in one exhibit; the payload keeps every row. | https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud |

## 8. Metrics

| Metric | Value |
| --- | --- |
| Crustdata calls | 41 |
| Crustdata cache hits | 41 |
| Crustdata credits used | 0.0 |
| Model calls | 9 |
| Model tokens in | 18333 |
| Model tokens out | 9373 |
| Rule tests run | 19 |
| Audit log records | 162 |
| Wall time (s) | 58.29 |
| Model tokens read from prompt cache | 4269 |

## 9. Exhibits

Also in `exhibits.md`; `evidence.json` holds the same objects as data.

### E1

| field | value |
| --- | --- |
| Test | T04 duplicate_invoices |
| Direction | refutes |
| Strength | 0.70 |
| Hypotheses | H7 |
| Subjects / objects | S001, V001 |
| Source | ledger_rows: L000001, L000010, L000017, L000025, L000029, L000038, L000039, L000048, L000057, L000063, L000068, L000076, L000080, L000092, L000100, L000110 |
| Payload sha256 | `65b6e9ea3aaf1e6e941dfbacda7b2e0cc3780864e9e27846a41d7e1b36b7ebc1` |
| Log record | `90e32cae-03f7-48e6-a64e-57337d3989fe` |

None of vendor V001's 16 invoices repeats an invoice number or an amount within 30 days.

```text
V001: 0 duplicates in 16 invoices: L000001 2024-04-26 TATA STEEL LTD 22,18,776 inv TSL/31574 approver S001 posted 2024-04-26 16:41; L000010 2024-06-27 Tata Steel Limited 12,25,048 inv TSL/31841 approver S001 posted 2024-06-27 13:05; L000017 2024-08-15 Tata Steel Limited 14,85,768 inv TSL/32055 approver S001 posted 2024-08-15 16:50; L000025 2024-11-05 Tata Steel Limited 20,36,837 inv TSL/32215 approver S001 posted 2024-11-05 15:20; L000029 2024-12-24 Tata Steel Ltd. 15,47,252 inv TSL/32460 approver S001 posted 2024-12-24 15:35; L000038 2025-03-03 Tata Steel Limited 18,25,427 inv TSL/32600 approver S001 posted 2025-03-03 14:12; L000039 2025-04-07 Tata Steel Ltd. 14,79,471.25 inv TSL/32744 approver S001 posted 2025-04-07 10:50; L000048 2025-06-20 Tata Steel Limited 15,32,987 inv TSL/33083 approver S001 posted 2025-06-20 16:20; L000057 2025-08-06 Tata Steel Limited 17,69,114 inv TSL/33437 approver S001 posted 2025-08-06 11:41; L000063 2025-10-13 Tata Steel Ltd. 16,87,582 inv TSL/33609 approver S001 posted 2025-10-13 09:50; L000068 2025-12-25 TATA STEEL LTD 21,60,381.25 inv TSL/33992 approver S001 posted 2025-12-25 16:20; L000076 2026-02-11 Tata Steel Limited 12,50,459.50 inv TSL/34178 approver S001 posted 2026-02-11 12:20; L000080 2026-03-24 Tata Steel Limited 14,92,707 inv TSL/34457 approver S001 posted 2026-03-24 15:35; L000092 2026-06-08 Tata Steel Limited 16,94,867 inv TSL/34624 approver S001 posted 2026-06-08 14:35; L000100 2026-08-07 TATA STEEL LTD 15,79,984 inv TSL/34991 approver S001 posted 2026-08-07 10:20; L000110 2026-09-30 Tata Steel Limited 20,49,845 inv TSL/35143 approver S001 posted 2026-09-30 17:05
```


### E20

| field | value |
| --- | --- |
| Test | T05 threshold_structuring |
| Direction | refutes |
| Strength | 0.70 |
| Hypotheses | H3 |
| Subjects / objects | S004, V017 |
| Source | ledger_rows: L000077, L000083, L000088, L000093, L000097, L000101, L000103, L000112 |
| Payload sha256 | `9857ec6af5fe4d85e4a56a5eaf099f7de667446c9aa554205007cbf497277249` |
| Log record | `c8c59304-a8d0-4675-8039-95014574f6e9` |

Vendor V017's invoices sit just under the approver's limit no more often than the population (0.0% vs 0.0%), with no splits.

```text
V017: 0/8 in band vs population 0.0%: L000077 2026-03-10 DocRack 1,15,972 inv DR/2026/585 approver S004 posted 2026-03-10 14:41; L000083 2026-04-09 DOCRACK 1,55,505.25 inv DR/2026/840 approver S004 posted 2026-04-09 15:12; L000088 2026-05-12 Docrak 2,00,801 inv DR/2026/974 approver S004 posted 2026-05-12 15:41; L000093 2026-06-09 DocRack 2,51,218 inv DR/2026/1059 approver S004 posted 2026-06-09 09:12; L000097 2026-07-13 DOCRACK 2,96,359 inv DR/2026/1276 approver S004 posted 2026-07-13 09:50; L000101 2026-08-12 Docrak 3,41,733 inv DR/2026/1472 approver S004 posted 2026-08-12 13:05; L000103 2026-09-14 DocRack 3,85,178 inv DR/2026/1561 approver S004 posted 2026-09-14 16:20; L000112 2026-10-12 DOCRACK 4,26,822 inv DR/2026/1747 approver S004 posted 2026-10-12 09:20
```


### E30

| field | value |
| --- | --- |
| Test | T06 round_amounts |
| Direction | refutes |
| Strength | 0.70 |
| Hypotheses | H2 |
| Subjects / objects | S004, V017 |
| Source | ledger_rows: L000077, L000083, L000088, L000093, L000097, L000101, L000103, L000112 |
| Payload sha256 | `ff9e433aa164d39fc0994222fc232a7f158083f647082335d323a73461c172db` |
| Log record | `19aed4cd-662a-40c6-b49f-dbdbfc262899` |

Vendor V017's share of round amounts is no higher than the population's (0.0% vs 0.0%).

```text
V017: 0/8 round vs population 0.0%: L000077 2026-03-10 DocRack 1,15,972 inv DR/2026/585 approver S004 posted 2026-03-10 14:41; L000083 2026-04-09 DOCRACK 1,55,505.25 inv DR/2026/840 approver S004 posted 2026-04-09 15:12; L000088 2026-05-12 Docrak 2,00,801 inv DR/2026/974 approver S004 posted 2026-05-12 15:41; L000093 2026-06-09 DocRack 2,51,218 inv DR/2026/1059 approver S004 posted 2026-06-09 09:12; L000097 2026-07-13 DOCRACK 2,96,359 inv DR/2026/1276 approver S004 posted 2026-07-13 09:50; L000101 2026-08-12 Docrak 3,41,733 inv DR/2026/1472 approver S004 posted 2026-08-12 13:05; L000103 2026-09-14 DocRack 3,85,178 inv DR/2026/1561 approver S004 posted 2026-09-14 16:20; L000112 2026-10-12 DOCRACK 4,26,822 inv DR/2026/1747 approver S004 posted 2026-10-12 09:20
```


### E40

| field | value |
| --- | --- |
| Test | T07 sequential_invoice_numbers |
| Direction | refutes |
| Strength | 0.50 |
| Hypotheses | H2 |
| Subjects / objects | S004, V017 |
| Source | ledger_rows: L000077, L000083, L000088, L000093, L000097, L000101, L000103, L000112 |
| Payload sha256 | `b6064667aa0716729de5df8c908dd7e36b1572739b13a3744c5c44dcb7dbd007` |
| Log record | `39c73ca3-db03-47ef-8a6e-c8ca5f791056` |

Vendor V017's invoice numbers advance by 166 on average between our invoices, consistent with a vendor billing many customers.

```text
V017: 8 invoice numbers 585..1747, mean step 166.0: L000077 2026-03-10 DocRack 1,15,972 inv DR/2026/585 approver S004 posted 2026-03-10 14:41; L000083 2026-04-09 DOCRACK 1,55,505.25 inv DR/2026/840 approver S004 posted 2026-04-09 15:12; L000088 2026-05-12 Docrak 2,00,801 inv DR/2026/974 approver S004 posted 2026-05-12 15:41; L000093 2026-06-09 DocRack 2,51,218 inv DR/2026/1059 approver S004 posted 2026-06-09 09:12; L000097 2026-07-13 DOCRACK 2,96,359 inv DR/2026/1276 approver S004 posted 2026-07-13 09:50; L000101 2026-08-12 Docrak 3,41,733 inv DR/2026/1472 approver S004 posted 2026-08-12 13:05; L000103 2026-09-14 DocRack 3,85,178 inv DR/2026/1561 approver S004 posted 2026-09-14 16:20; L000112 2026-10-12 DOCRACK 4,26,822 inv DR/2026/1747 approver S004 posted 2026-10-12 09:20
```


### E50

| field | value |
| --- | --- |
| Test | T12 velocity_and_share |
| Direction | supports |
| Strength | 0.60 |
| Hypotheses | H1, H4 |
| Subjects / objects | V017 |
| Source | ledger_rows: L000077, L000083, L000088, L000093, L000097, L000101, L000103, L000112 |
| Payload sha256 | `b590785dcba3cf6859893aa8b59c4fb1d78989be5fb83413192d1924c65fd06f` |
| Log record | `8d7b89ec-2d6f-4b97-bf5b-1fe361ce5812` |

Vendor V017's growth in spend is 2.9 standard deviations above the other 9 vendors.

```text
V017: spend 21,73,588.25 = 3.6% of 6,00,18,462.50 (share z -0.5); before 2025-07-19 0, from 2025-07-19 21,73,588.25 (growth z 2.9); L000077 2026-03-10 DocRack 1,15,972 inv DR/2026/585 approver S004 posted 2026-03-10 14:41; L000083 2026-04-09 DOCRACK 1,55,505.25 inv DR/2026/840 approver S004 posted 2026-04-09 15:12; L000088 2026-05-12 Docrak 2,00,801 inv DR/2026/974 approver S004 posted 2026-05-12 15:41; L000093 2026-06-09 DocRack 2,51,218 inv DR/2026/1059 approver S004 posted 2026-06-09 09:12; L000097 2026-07-13 DOCRACK 2,96,359 inv DR/2026/1276 approver S004 posted 2026-07-13 09:50; L000101 2026-08-12 Docrak 3,41,733 inv DR/2026/1472 approver S004 posted 2026-08-12 13:05; L000103 2026-09-14 DocRack 3,85,178 inv DR/2026/1561 approver S004 posted 2026-09-14 16:20; L000112 2026-10-12 DOCRACK 4,26,822 inv DR/2026/1747 approver S004 posted 2026-10-12 09:20
```


### E56

| field | value |
| --- | --- |
| Test | T13 existence_and_capacity |
| Direction | supports |
| Strength | 0.50 |
| Hypotheses | H6 |
| Subjects / objects | V008 |
| Source | vendor_master: vendor:V008 |
| Payload sha256 | `5c4575edd28465384ad9dab35a79ef5ab2a3558d19f247c3f93cb75b77c9726f` |
| Log record | `9cd69038-f0f9-4c40-b6ff-a00b024d07ca` |

Vendor V008 has no matching Crustdata company record (resolution unresolved); its existence could not be confirmed.

```text
vendor master V008 "Zentravik Industrial Supplies Pvt Ltd": Crustdata resolution unresolved, candidates considered 25
```


### E60

| field | value |
| --- | --- |
| Test | T13 existence_and_capacity |
| Direction | supports |
| Strength | 0.50 |
| Hypotheses | H2, H5 |
| Subjects / objects | V017 |
| Source | crustdata_company: crustdata:company:71095782@2026-10-30T00:23:30Z |
| Record updated_at | 2026-10-30T00:23:30Z |
| Payload sha256 | `3a946d97b41206419c28dd103408b20f46bf94fbd4cbc4a2e4279d3d463b3190` |
| Log record | `9cd69038-f0f9-4c40-b6ff-a00b024d07ca` |

Crustdata's record for vendor V017 shows headcount total 2 with website https://docrack.ai/.

```text
crustdata:company:71095782@2026-10-30T00:23:30Z headcount_total 2; website https://docrack.ai/
```


### E81

| field | value |
| --- | --- |
| Test | T15 career_overlap |
| Direction | supports |
| Strength | 0.90 |
| Hypotheses | H1, H5 |
| Subjects / objects | S004, V017 |
| Source | crustdata_person: crustdata:person:177265563@2026-10-26T16:58:10.076880Z, crustdata:company:71095782@2026-10-30T00:23:30Z |
| Record updated_at | 2026-10-26T16:58:10.076880Z |
| Payload sha256 | `84f012a2aeaa3dd232c7bbbcd8d07294842e098985bd178be54ea431e44ba1b8` |
| Log record | `ce39b037-cf66-4355-b7ba-d9cb9e64c736` |

Staff member S004's Crustdata career history includes vendor V017 (DocRack, 2026-03-01 to present), overlapping the payment period.

```text
crustdata:person:177265563@2026-10-26T16:58:10.076880Z employment[0]: DocRack, Co-Founder, 2026-03-01 to present; first payment 2026-03-10 (L000077); last payment 2026-10-12 (L000112)
```


### E94

| field | value |
| --- | --- |
| Test | T17 founders_match |
| Direction | supports |
| Strength | 0.90 |
| Hypotheses | H1, H2, H5 |
| Subjects / objects | S004, V017 |
| Source | crustdata_company: crustdata:company:71095782@2026-10-30T00:23:30Z |
| Record updated_at | 2026-10-30T00:23:30Z |
| Payload sha256 | `2bb599384a2276189d295514934f950a432c47e3dacf5cab989704c02fd9b889` |
| Log record | `0f4535ce-5fa9-40e9-a0cc-bb1a9eda2a75` |

Vendor V017's Co-Founder T.C. has the same LinkedIn profile as staff member S004.

```text
crustdata:company:71095782@2026-10-30T00:23:30Z person "T.C.", Co-Founder, https://www.linkedin.com/in/T.C.-5424a9252; staff S004 "T.C." linkedin.com/in/T.C.-5424a9252 (name score 100)
```


### E95

| field | value |
| --- | --- |
| Test | T16 graph_path |
| Direction | supports |
| Strength | 0.75 |
| Hypotheses | H1, H2, H5 |
| Subjects / objects | S004, V017 |
| Source | graph: staff:S004, cdperson:177265563, cdco:71095782, vendor:V017 |
| Payload sha256 | `3e3481178062b31c5bc4ace2f4cc0fe2373b094a2038ed1fd848794f14d63211` |
| Log record | `a281a032-9d02-4ad0-8bd1-58fb785bbdfa` |

Staff member S004 is linked to vendor V017 in 3 steps through employment.

```text
staff:S004 -[resolution: crustdata:person:177265563@2026-10-26T16:58:10.076880Z]- cdperson:177265563 -[employment: crustdata:person:177265563@2026-10-26T16:58:10.076880Z employment[0]: DocRack, Co-Founder, 2026-03-01 to present (overlapping the payment period)]- cdco:71095782 -[resolution: crustdata:company:71095782@2026-10-30T00:23:30Z]- vendor:V017
```


