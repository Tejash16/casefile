---
paths:
  - "src/casefile/audit/**"
  - "src/casefile/report/**"
  - "verify.py"
---

# Audit and report rules

- Log records follow `docs/contract.md` section 4 exactly. Canonical JSON via RFC 8785 (`rfc8785.dumps`); `record_hash` over the record without `record_hash`; `prev_hash` chains; Merkle root per RFC 6962 with domain-separated leaves and nodes.
- Append-only, fsync after each line. A crash must leave a verifiable prefix.
- `verify.py` at the repo root uses only the standard library and reports one clear line per failure (which seq, which check).
- The renderer never invents text. Every sentence in the executive summary and findings carries evidence ids; `report/check.py` refuses to render otherwise (exit 2).
- Redaction replaces person names with initials and keeps ids and Crustdata record ids.
