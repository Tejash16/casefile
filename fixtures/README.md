# Fixtures (b1)

Small, deliberately messy inputs for every module's tests. Audited company: Halvexa Precision Components Pvt Ltd (fictional), Pune. Design and Crustdata ids in `docs/dataset-design.md`.

| file | contents |
| --- | --- |
| `tip.txt` | anonymous tip naming V023, V017, S005 and V031 |
| `ledger.csv` | 62 data rows, FY 2024-25 and 2025-26 |
| `vendors.csv` | 12 vendors (V001–V009, V017, V023, V031) |
| `staff.csv` | 8 staff (S001–S008) |
| `crustdata/company_enrich_tata_steel.json` | real `POST /company/enrich` body for id 5042 (Tata Steel), every list trimmed to 3 items. `X-Request-ID: 0312e561-7049-4d17-8b82-38c63703a2e9`, `X-Credits-Used: 2`. Note: no top-level `updated_at` in `company_data`; only nested `last_updated` fields |

## Messiness in `ledger.csv` (loaders must flag each)

- UTF-8 BOM, CRLF line endings.
- Header `Amount INR ` has a trailing space; headers use synonyms (`Supplier`, `Approved By`, `Txn Date`).
- One blank row (`,,,,,,,,,`) before data row 22; the header row repeated before data row 43.
- Dates rotate `22/04/2024`, `2024-04-30`, `16-May-24`.
- Amounts rotate `18,47,350`, `84250.00`, `₹ 7,34,210.00`.
- Vendor spellings: V023 as `Brindora Engineering Traders Pvt Ltd`, `BRINDORA ENGINEERING TRADERS PRIVATE LIMITED`, `Brindora Enginering Traders`; V017 as `Persistent Systems Limited`, `PERSISTENT SYSTEMS`, `Persistant Systems Ltd`; V001 `TATA STEEL LTD` / `Tata Steel Limited`; V003 `Sundram Fasteners Ltd.`; V008 without suffix.
- Approver spellings: `A. Deshpande` / `Anil Deshpande` (staff list has `Mr. Anil Deshpande`), `farhan qureshi`.

`vendors.csv` and `staff.csv` also mix the three date formats; approval limits are in lakh format (`5,00,000`); S003's phone is `9822041736` in staff and `+91 98220 41736` in vendors.

## Planted facts

- **V023 shell:** created 10/01/2025 by `adeshpande` (S003); address and phone equal S003's (spelled differently); first invoice 2025-01-18; 8 invoices `BET/001`–`BET/008`, round amounts 4,90,000–4,99,000 under S003's 5,00,000 limit, 4 of them posted 22:00–23:59; no website, no GSTIN; does not resolve in Crustdata.
- **V017 career overlap:** approved only by S004; spend grows from 2,18,400 to 4,68,900 from March 2025. Placeholder company (Persistent Systems) until team member A's past employer is confirmed; S004's name and LinkedIn are placeholders too.
- **V003 duplicate billing:** invoice `SFL/24-25/0457` for 3,42,180 paid on 2025-02-06 and again on 2025-02-15.
- **V031 false lead:** the tip says S005 used to work there; S005 has no approval rights and never appears on V031's rows.
- **V008 unresolved:** fictional name; must come back `unresolved`.
- **Clean:** V001, V002, V004, V005, V006, V007, V009.
