# Fixtures (b1)

Small, deliberately messy inputs for every module's tests. Audited company: Halvexa Precision Components Pvt Ltd (fictional), Pune. Design and Crustdata ids in `docs/dataset-design.md`.

| file | contents |
| --- | --- |
| `tip.txt` | anonymous tip naming V023, V017, S005 and V031 |
| `ledger.csv` | 62 data rows, FY 2024-25 and 2025-26 |
| `vendors.csv` | 12 vendors (V001–V009, V017, V023, V031) |
| `staff.csv` | 8 staff (S001–S008) |
| `crustdata/person_enrich_team.json` | real `POST /person/enrich` body (`fields: [basic_profile, experience, education]`) for S004 and S005, the two team members, used with consent. `X-Request-ID: 4a3980f6-b359-4feb-b5ca-46c7cfcb38f5`, `X-Credits-Used: 2`. No `updated_at` anywhere; without `fields`, enrich returns `basic_profile` only |
| `crustdata/company_enrich_tata_steel.json` | real `POST /company/enrich` body for id 5042 (Tata Steel), every list trimmed to 3 items. `X-Request-ID: 0312e561-7049-4d17-8b82-38c63703a2e9`, `X-Credits-Used: 2`. Note: no top-level `updated_at` in `company_data`; only nested `last_updated` fields |

## Messiness in `ledger.csv` (loaders must flag each)

- UTF-8 BOM, CRLF line endings.
- Header `Amount INR ` has a trailing space; headers use synonyms (`Supplier`, `Approved By`, `Txn Date`).
- One blank row (`,,,,,,,,,`) before data row 22; the header row repeated before data row 43.
- Dates rotate `22/04/2024`, `2024-04-30`, `16-May-24`.
- Amounts rotate `18,47,350`, `84250.00`, `₹ 7,34,210.00`.
- Vendor spellings: V023 as `Brindora Engineering Traders Pvt Ltd`, `BRINDORA ENGINEERING TRADERS PRIVATE LIMITED`, `Brindora Enginering Traders`; V017 as `DocRack`, `DOCRACK`, `Docrak`; V031 as `HCL Technologies Ltd` / `HCL TECHNOLOGIES LIMITED`; V001 `TATA STEEL LTD` / `Tata Steel Limited`; V003 `Sundram Fasteners Ltd.`; V008 without suffix.
- Approver spellings: `A. Deshpande` / `Anil Deshpande` (staff list has `Mr. Anil Deshpande`), `farhan qureshi`.

`vendors.csv` and `staff.csv` also mix the three date formats; approval limits are in lakh format (`5,00,000`); S003's phone is `9822041736` in staff and `+91 98220 41736` in vendors.

## Planted facts

- **V023 shell:** created 10/01/2025 by `adeshpande` (S003); address and phone equal S003's (spelled differently); first invoice 2025-01-18; 8 invoices `BET/001`–`BET/008`, round amounts 4,90,000–4,99,000 under S003's 5,00,000 limit, 4 of them posted 22:00–23:59; no website, no GSTIN; does not resolve in Crustdata.
- **V017 career overlap:** DocRack (Crustdata company 71095782, 2-10 staff; resolve by name, no website on purpose: docrack.ai resolves to another record, Orvyn Labs 6337171). S004 (Tejash Chauhan, LinkedIn in `staff.csv`) is Co-Founder at DocRack from 2026-03-01 per Crustdata (person 177265563). V017 created 2025-05-20 by `tchauhan`; 6 invoices approved only by S004, 2025-06-12 to 2026-03-19, growing from 2,18,400 to 4,68,900; the last one overlaps the employment and every one is within 365 days of its start.
- **V003 duplicate billing:** invoice `SFL/24-25/0457` for 3,42,180 paid on 2025-02-06 and again on 2025-02-15.
- **V031 false lead:** HCLTech (company 1910; resolve by `hcltech.com`, since the name alone gives three matches at 1.0). The tip says S005 (Kedar Sharma) used to work there. A namesake in Noida (Crustdata person 6677240) did, 2023-02 to 2025-03; our S005 (person 420958731, resolved by LinkedIn URL) never did. S005 has no approval rights and never appears on V031's rows. Known noise: S005 is also DocRack's co-founder (from 2025-06), so a graph path S005–V017 exists; S005 approves nothing.
- **V008 unresolved:** fictional name; must come back `unresolved`.
- **Clean:** V001, V002, V004, V005, V006 (Pune Metrology, 72073831), V007 (Atomic Gauges, 15339565), V009 (Fox Precision Tooling, 8697742; the last three have 2-10 staff).
