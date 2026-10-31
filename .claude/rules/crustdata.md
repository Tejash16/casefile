---
paths:
  - "src/casefile/crustdata/**"
  - "src/casefile/resolve/**"
---

# Crustdata rules

- Headers on every call: `authorization: Bearer $CRUSTDATA_API_KEY`, `x-api-version: 2025-11-01`, `content-type: application/json`. Base `https://api.crustdata.com`.
- Identify first (free, 25 per call), Enrich only accepted ids (2 credits, 25 per call) with explicit `fields`. Person Enrich takes LinkedIn URLs only; names go through Person Search `mode: "exact"`.
- Rate limits: enrich 15/min, identify and search 30/min, web 10/min. On 429 read `X-RateLimit-Reset` or `Retry-After`, sleep, retry with jitter, max 5.
- Cache every response to `.cache/crustdata/<sha256(request)>.json` with status, `X-Credits-Used`, `X-Request-Id`, body. `offline=True` never touches the network.
- Every call is wrapped in audit pre/post records. Every fact carries `updated_at` and `source_request_id`.
- Never accept `matches[0]` on name alone; check `confidence_score`, `primary_domain`, `employee_count_range`. Ambiguous → judge; low → `unresolved`.
- No other hosts. No outreach of any kind.
