# ContextCon 03 Fraud Investigator: Research Brief

Oct 31, 2026 · @Tejash Chauhan

## The brief decoded

Your idea is the one the organisers wrote down themselves ("a fraud investigator that takes an insider tip and returns a complaint-ready case file"), so you will be judged against their own mental model of that agent: the bar is execution and verifiability, not originality. It sits in the *Trust and compliance* theme (fraud analysis, shell companies vs genuine businesses) and the tamper-evident log reaches into *Infrastructure for agents* (cryptographic execution trails), which is a second theme scored for free.

| Criterion (from the PS) | What it means for this agent | How to prove it in a 2-minute video |
| --- | --- | --- |
| End-to-end execution, zero human intervention | One command: tip + ledger in, case file out. No approval prompts, no manual step between stages | Cold start on camera, one command, no clicking until the file opens |
| Data integrity and verification | Every vendor and person resolved in Crustdata; every sentence in the file carries a citation | Click one citation: it lands on the Crustdata record ID and the ledger row ID it came from |
| Robustness and edge cases | Messy ledger (inconsistent vendor names, dates, currencies), free-text tip, a 429 and an unresolvable vendor | Feed a deliberately dirty CSV; show the log line where the agent retried a 429 and marked a vendor "unverifiable" instead of guessing |
| Demo clarity | The video is the shortlist gate; nobody runs your repo in Phase 1 | Finished case file visible by 1:30; refuted false lead and cleared clean vendor shown, not just the hit |

Seven traps in the rules and schedule:

1. Phase 1 shortlists from the video and repo alone. Budget 45 minutes for recording and re-takes; a brilliant agent with a muddled video does not reach the stage.
2. "A request it has never seen": hold out one planted case nobody on the team runs before the recording, and run it on camera from scratch.
3. Rule 4 bans contact with real people. The tip is a text file, and the agent must have no email, call or outreach tool at all. Crustdata records are real people and companies, so the allegation must be about your synthetic ledger, phrased as fact ("career history includes Vendor X, 2019 to 2022"), and names in the public video can be redacted by the agent.
4. Rule 3 requires the Crustdata key in the build. Headers: `authorization: Bearer <key>` and `x-api-version: 2025-11-01`.
5. Coding starts at 10:30 sharp. Architecture, data schemas, prompts, CLAUDE.md, the planted-case design and the demo script are all allowed before that.
6. Credits: $1,500 per builder, so $4,500 across three of you; a 429 means back off a few seconds and retry, and `/account/credits` shows the balance.
7. The real coding window is about 4 h 15 min: building begins 10:30, code freeze with video is 15:30, so recording starts by 14:45 at the latest.

## How forensic auditors investigate vendor fraud today

Your agent's shape is the profession's own method. The ACFE Fraud Examiners Manual calls it the fraud theory approach: "analyzing available data", "creating a hypothesis", "testing the hypothesis", "refining and amending the hypothesis" ([ACFE FEM 2026 sample chapter](https://cms.acfe.com/-/media/files/acfe/word-documents/fem_samplechapter_planning_and_conducting_2026.pdf)). Tips detect 43% of occupational frauds, more than any other method; billing schemes are 21% of cases with a median loss of $104,000 overall and $90,000 for billing, running a median 14 months before detection; "unusually close association with a vendor" is a red flag in 17% of perpetrators ([ACFE Report to the Nations 2026](https://www.acfe-mexico.com.mx/inicio/sitepad-data/uploads/2026/07/Reporte-a-las-Naciones-2026.pdf), [acfe.com](https://www.acfe.com/report-to-the-nations)).

**The typology list.** Give the hypothesis engine a fixed menu drawn from the ACFE fraud tree rather than letting it invent categories; the research in section 4 shows constrained agents beat free-roaming ones.

| Typology (ACFE fraud tree) | How it shows in the ledger and masters | What Crustdata adds |
| --- | --- | --- |
| Shell company (billing scheme) | Vendor shares address, phone or bank with an employee; no PO or receiving; round amounts; vendor created days before first invoice | Headcount 0 to 2 or no record, no website, `year_founded` just before first payment, HQ is a residence or mail drop |
| Pass-through vendor | Employee-owned intermediary marks up a real supplier; invoices mirror a genuine vendor's | Tiny headcount; `people.founders` or decision makers match a staff name |
| Conflict of interest (purchasing scheme) | One approver steers rising spend to one vendor; sole-source awards | Approver's `experience.employment_details.past` includes the vendor, with dates overlapping or just before payments |
| Invoice kickbacks (bribery) | Vendor's share of category spend climbs; prices above peers; invoices approved unusually fast | Vendor headcount flat while invoice volume climbs |
| Non-accomplice vendor / personal purchases | Real vendor, fabricated or personal invoices routed through it | Large, established company: the vendor clears and suspicion moves to the approver |

**The standard tests.** These are the computer-assisted audit tests every forensic team runs on accounts-payable data; each is a deterministic rule you can code in minutes.

| Test | Rule | Named by |
| --- | --- | --- |
| Vendor master vs employee master | Exact and fuzzy match on address, phone, bank account, tax ID, name; also within the vendor file for duplicates | [Diligent](https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud), [City of Tulsa IA](https://www.cityoftulsa.org/media/2452/2015-vendortoemployeereport.pdf), [ACFE Insights case](https://acfeinsights.squarespace.com/acfe-insights/2022/12/22/case-study-the-employee-and-vendor-nexus) |
| Thin vendor footprint | PO box, residential or virtual-office address; missing phone, TIN, email; personal email domain | [Wells, JofA 2002](https://www.journalofaccountancy.com/issues/2002/jul/billingschemespart1shellcompaniesthatdontdeliver/), [MN State Auditor](https://www.osa.state.mn.us/audit-resources/audit-guidance/avoiding-pitfalls-articles/phantom-vendors) |
| Vendor age vs first payment | Incorporation or vendor-creation date within 90 days of first invoice; created off-hours or by a non-standard user | [Vona CFE handout](https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf) |
| Duplicate invoices | Same vendor + amount; same invoice number; Nigrini "same-same-different" (same number and amount, different vendor) | [Diligent](https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud), [IDEA scripting](https://www.ideascripting.com/Same-Same-Different-Test) |
| Threshold structuring | Amounts in the 5% band under each approval limit; split invoices whose sum crosses the limit within a short window | [Diligent](https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud), [Wells 2002](https://www.journalofaccountancy.com/issues/2002/jul/billingschemespart1shellcompaniesthatdontdeliver/) |
| Round amounts | Share of invoices ending in 000 or 00 per vendor vs population | [AZ Auditor General 18-406](https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf) |
| Sequential invoice numbers | Gap-free or narrow invoice-number range per vendor: you are their only customer | [Sequence Inc](https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes), [MN State Auditor](https://www.osa.state.mn.us/audit-resources/audit-guidance/avoiding-pitfalls-articles/phantom-vendors) |
| Benford first-two digits | Spikes just under a limit (digits "29" under $3,000); population only, never one vendor | [JofA 1998](https://www.journalofaccountancy.com/issues/1998/nov/audit-nov-1998/) |
| Off-hours postings | Weekend, holiday or night postings and approvals | [AZ Auditor General 18-406](https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf) |
| Dormant vendor reactivated / master changes | Payment after 12+ months idle; bank or address change then reversed | [Vona](https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf) |
| Segregation of duties | Same user creates the vendor and approves or posts its invoices | [Deloitte SAP red flags](https://www2.deloitte.com/content/dam/Deloitte/sg/Documents/risk/sea-risk-sap-governance-risk-compliance-red-flag-brochure.pdf) |
| Velocity and share | Spend per vendor rising faster than category; one vendor taking a disproportionate share | [Weaver](https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf) |
| Existence and capacity | No website or recent domain, no registry record, headcount inconsistent with billed volume | [Vona](https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf), [Sequence Inc](https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes) |
| Look-alike names | Same vendor under several spellings; same TIN under several vendor numbers | [Case IQ](https://pages.caseiq.com/rs/219-YZJ-775/images/16-ways-to-identify-fictitious-vendors-version-2.pdf?version=0) |

No single hit is a finding; practitioners weigh the "totality of evidence" ([Sequence Inc](https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes)). Make each allegation's verdict depend on at least two independent tests.

**Verdict labels.** A CFE "never opines on the guilt or innocence of any person" and states only facts traceable to exhibits ([ACFE Insights](https://acfeinsights.squarespace.com/acfe-insights/how-write-report-without-declaring-guilt-or-innocence)). The labels investigative bodies use are **Substantiated** (more likely than not), **Unfounded** (evidence shows it did not occur) and **Unsubstantiated** (insufficient evidence) ([LA County Fraud Hotline](https://fraud.lacounty.gov/investigative-process/)). Use these three in the case file; they are your "supported, refuted, unverifiable" in the words an audit committee already knows.

**Case-file structure.** Background and predication, executive summary, scope, approach, findings (each fact tied to an exhibit), impact, recommendations, exhibits ([CFE study guide](https://open-exam-prep.com/study-guides/cfe/investigation-reporting-testimony/writing-the-fraud-examination-report)). Reports must include exculpatory evidence and be "supported by evidence and documentation in the investigative case file" ([CIGIE Quality Standards, July 2025](https://www.ignet.gov/sites/default/files/files/Quality%20Standards%20for%20Investigations%20July-2025.pdf)). "Complaint-ready" means answering who, what, when, where, why and how, with dates and amounts per transaction, not totals, and the relationships among parties ([FinCEN SAR narrative guidance](https://www.fincen.gov/sites/default/files/shared/sarnarrcompletguidfinal_112003.pdf)). Chain of custody is "the chronological record of who obtained a piece of evidence" ([CFE guide](https://open-exam-prep.com/study-guides/cfe/investigation-planning-evidence/evidence-types-chain-of-custody-documentation)); your hash-chained log is exactly that, for an agent.

Indian context for the judges from IIT Bombay: under Companies Act 2013 s.143(12) an auditor with reason to believe fraud has occurred reports to the audit committee within 2 days, and frauds of INR 1 crore or more go to the Central Government in Form ADT-4 ([KPMG First Notes](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2023/08/firstnotes-mandatory-reporting-of-fraud-by-an-auditor.pdf)). A case file that states the amount in INR and names the ADT-4 threshold reads as domain-literate.

## What Crustdata gives the agent

Two facts shape the whole design: Company Identify is free and resolves a messy vendor name to a `crustdata_company_id` with a confidence score, and Person Enrich accepts only LinkedIn URLs, so a staff name reaches a career history through Person Search first ([Identify docs](https://docs.crustdata.com/company-docs/identify/introduction.md), [Person Enrich docs](https://docs.crustdata.com/person-docs/enrichment/introduction.md)). Base URL `https://api.crustdata.com`; every call carries `authorization: Bearer <key>`, `x-api-version: 2025-11-01` and `content-type: application/json` ([API introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md)).

| Endpoint | Input | Fields the investigation needs | Credits, rate limit |
| --- | --- | --- | --- |
| `POST /company/identify` | One of `names`, `domains`, LinkedIn URLs or IDs, up to 25 per call; `exact_match` flag | `matches[]` ranked, each with `confidence_score`, `crustdata_company_id`, `primary_domain`, `employee_count_range` | Free, 30 RPM |
| `POST /company/enrich` | Same identifiers, up to 25 per call; `fields` list (default is `basic_info` only) | `basic_info.{year_founded, website, status, employee_count_range, description}`, `headcount.{total, timeseries[date, employee_count], growth_percent}`, `locations.{headquarters, street_address, all_office_addresses}`, `funding`, `people.{founders, decision_makers}` with employment dates, `updated_at` | 2 per company, 15 RPM |
| `POST /person/search` | Filters such as `basic_profile.name` + `experience.employment_details.company_name`; `mode: "exact"` | `profiles[]` with `crustdata_person_id`, LinkedIn `profile_url`, current and past employment | 0.03 per result, +0.1 for experience, 30 RPM |
| `POST /person/enrich` | `professional_network_profile_urls` only, up to 25 | `match_status`, `confidence_score`, `experience.employment_details.current[] / past[]` each with `name, title, start_date, end_date, crustdata_company_id, company_website_domain, company_headcount_latest`, `basic_profile.last_updated` | 1 per profile, 15 RPM |
| `POST /web/search/live`, `POST /web/enrich/live` | `query`; `urls` 1 to 10 | Search results with `url, title, snippet, timestamp`; fetched page `content` | 1 per query or page, 10 RPM |
| `GET /account/credits` | none | `account.credits` | Free |

Sources: [Company Enrich](https://docs.crustdata.com/company-docs/enrichment/introduction.md), [Person Search](https://docs.crustdata.com/person-docs/search/introduction.md), [Web Search](https://docs.crustdata.com/web-docs/search/introduction.md), [Web Fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md), [pricing](https://docs.crustdata.com/general/pricing.md), [rate limits](https://docs.crustdata.com/general/rate-limits.md).

**Wiring it into Claude Code.** Commit a project `.mcp.json` with a placeholder so every session and teammate shares it; each person exports `CRUSTDATA_API_KEY` ([Crustdata MCP guide](https://docs.crustdata.com/for-agents/mcp.md), [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)):

```json
{
  "mcpServers": {
    "crustdata": {
      "type": "http",
      "url": "https://install.crustdata.com/mcp",
      "headers": { "Authorization": "Bearer ${CRUSTDATA_API_KEY}" }
    }
  }
}
```

The MCP tool list is not published on any public page; after connecting, read the resource `crustdata://catalog/tools` (and `crustdata://catalog/dry-run` for zero-credit tests). The MCP server is for your Claude Code sessions while building; the agent you ship should call the HTTP API directly, because that is what makes every response cacheable, hashable and citable.

**Gotchas that cost time.**

1. Resolve before you pay: Identify (free) first, then Enrich only matches above your confidence threshold. Do not trust `matches[0]`; the docs say to compare `primary_domain` and `employee_count_range`. Try `exact_match: true`, fall back to `false`.
2. Batch 25 identifiers per Enrich call: 60 vendors is 3 requests, not 60. Responses come back in input order.
3. Name-plus-employer for people goes through Person Search with `mode: "exact"`, then Enrich the returned `profile_url`. No enrich-by-name exists.
4. Request `fields` explicitly (`basic_info, headcount, locations, people, funding`); the default returns `basic_info` alone.
5. A 429 returns `X-RateLimit-Reset` in seconds and a `Retry-After` on batch caps; 402 means credits exhausted; every response carries `X-Credits-Used` and `X-Request-Id`, which belong in your log ([credits docs](https://docs.crustdata.com/general/credits.md)).
6. Citations: each record carries `updated_at` (and `basic_profile.last_updated` for people); profiles refresh every 1 to 30 days ([data updates](https://docs.crustdata.com/general/data-updates.md)). Cite record ID plus `updated_at`.
7. Budget: a 60-vendor, 40-person case costs roughly 120 + 50 credits, far inside $1,500 per builder; the binding constraint is 15 RPM on Enrich, so a cold run of that size takes about 4 minutes, which matters for the 2-minute video (section 7).

No Python or TypeScript SDK is published; use `httpx` with a per-endpoint rate limiter. A CLI exists (`crustdata company enrich ...`) for quick manual checks on the floor ([CLI docs](https://docs.crustdata.com/for-agents/cli.md)).

## What recent research says: borrow, skip

The research points one way: deterministic rules and statistics should do the detecting, the model should propose hypotheses, triage flags and explain, and citations must be checked mechanically because the writing step is where they break. A free-roaming ReAct agent did worse than a single LLM call on real fraud cases, so constrain the agent's action space to a fixed typology list and a typed tool set.

| Paper or tool | Finding (with numbers) | Borrow for today |
| --- | --- | --- |
| [AuditAgent, Oct 2025](https://arxiv.org/html/2510.00156v1) | Multi-expert agent over 1,570 real CSRC fraud cases; issue-level recall 28.9% vs 16.5% for a generic ReAct agent and 26.2% for a single LLM; the generic agent lost to the single LLM on every model; removing domain priors cost 5 to 6 points | A fixed list of fraud typologies as the "risk prior"; specialised steps instead of one open loop |
| [AuditCopilot, Dec 2025](https://arxiv.org/html/2512.02726v1) | LLM classifies journal entries to strict JSON with statistics and an Isolation-Forest verdict in the prompt; F1 0.94 with 12 false positives vs 0.68 (169 FPs) for Isolation Forest alone and 0.50 (942 FPs) for rules alone; removing the statistics collapsed recall to 0.07; results swing by model | Pre-compute z-scores, duplicate counts, round-amount ratios and threshold clustering, and pass them as evidence; the model's job is precision and explanation |
| [Peeters & Bizer, entity matching with LLMs](https://arxiv.org/pdf/2310.11244v3) | GPT-4 zero-shot F1 89.6 to 95.8 on product matching, more robust than fine-tuned matchers on unseen entities (+34 points); few-shot adds only +0.85; about 2 s and 0.47 cents per pair | Never run the model over all pairs: block and shortlist with RapidFuzz, then zero-shot yes / no / unsure on the top candidates; skip few-shot |
| [Splink](https://moj-analytical-services.github.io/splink/), [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | Splink links about 1M records a minute, unsupervised; overkill for a few hundred names | Normalise (lowercase, strip Ltd / Pvt / Inc / punctuation), `process.cdist` with `token_set_ratio`, accept at 95+, send 70 to 95 to the model, reject below 70; hard-match on domain when Crustdata returns one |
| [Google AI co-scientist, Nature 2026](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/) | Generate, reflect (peer-review agent), rank (Elo tournament), evolve; most compute spent verifying hypotheses against external data | Separate the proposer from the reviewer with no shared scratchpad; rank allegations by evidence strength; spend budget on verification calls |
| [Localising citation errors in multi-agent research, Aug 2026](https://arxiv.org/abs/2608.24306) | 84.7% of final-report errors originated at the orchestrator or writer; about 31% hallucinations, the rest citation mistakes | The case-file writer sees only structured evidence objects and emits a sentence-to-evidence map; render nothing without an evidence id |
| [Verify with Caution, Jan 2025](https://arxiv.org/abs/2501.14883) | Five attribution metrics disagree across 11 datasets and misrank systems | LLM-as-judge is a smoke test; a deterministic check (quoted string is literally in the hashed tool output) comes first |
| [Good-Enough Structured Generation, NeurIPS 2025](https://neurips.cc/virtual/2025/131662) | Grammar-constrained decoding covered as little as 50% of 9,558 real schemas; validate-and-retry reached about 95% | Native structured output plus Pydantic validation and at most 2 retries; `verdict` is an enum with `unsubstantiated` so abstaining is a first-class answer |
| [Verification gap in AI-scientist agents, Aug 2026](https://arxiv.org/abs/2608.05179) | Of 26 systems, 83% release code, 38% release execution traces, none has an externally validated in-loop verifier | Shipping traces and a verifier script is rare; your log is the differentiator, say so in the demo |
| [RFC 6962](https://www.rfc-editor.org/rfc/rfc6962), [draft-sharif-agent-audit-trail](https://datatracker.ietf.org/doc/html/draft-sharif-agent-audit-trail-06) | Leaf = SHA-256(0x00 ‖ entry), node = SHA-256(0x01 ‖ L ‖ R); the agent-audit draft chains records by `prev_hash` over RFC 8785 canonical JSON, with `record_phase` pre- and post-execution, and notes a bare chain cannot detect tail truncation | JSONL with `record_id, timestamp, agent_id, action_type, action_detail, outcome, prev_hash, record_phase`; Merkle root printed in the case file; a 20-line verifier |
| [OpenTelemetry GenAI conventions](https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions) | Span names `invoke_agent`, `execute_tool`; attributes `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.usage.input_tokens` | Name log fields after these; free credibility |
| [NetworkX bipartite](https://networkx.org/documentation/stable/reference/algorithms/bipartite.html), [community](https://networkx.org/documentation/stable/reference/algorithms/community.html) | Bipartite projections, `has_path`, `shortest_path`, Louvain built in | Graph of employees, vendors, addresses, phones, bank accounts, Crustdata IDs; a path of length 3 or less from approver to vendor is printable evidence |
| [GNN fraud detection review, Nov 2024](https://arxiv.org/abs/2411.05815) | Framed around million-entity graphs, heavy class imbalance, distributed training; explainability still open | Skip. A few hundred vendors have neither the labels nor the scale, and you need explainable paths |
| [ISACA on Benford's law](https://www.isaca.org/resources/isaca-journal/past-issues/2011/understanding-and-applying-benfords-law) | Needs about 1,000 records, unbounded natural data; under 500 is "unlikely suitable"; fails on capped or filtered samples | Run on the whole payment population only, report as a lead; the real signal is the count of invoices in the 5% band under each approval limit |
| [tau-bench pass^k](https://sierra.ai/blog/benchmarking-ai-agents) | GPT-4o fell from under 50% pass^1 to about 25% pass^8 on repeated runs of the same task | Run each planted case 3 times; a case counts only if solved every time; temperature 0 on grading steps |

**Second-pass findings.** Six more results, each changing one design detail:

- Reasoning models abstain less, not more: across 20 frontier models and 35,000 unanswerable questions, reasoning variants abstained 24% less than their base models, and larger thinking budgets made it worse ([AbstentionBench, Meta FAIR, arXiv 2506.09038](https://arxiv.org/pdf/2506.09038)). The `Unsubstantiated` verdict must be forced by code when a match score is below threshold or a required field is missing, never left to the model.
- Factored verification works: Chain-of-Verification, with verification questions answered independently of the draft, more than doubled precision (0.17 to 0.36) on list questions ([Dhuliawala et al., arXiv 2309.11495](https://ar5iv.labs.arxiv.org/html/2309.11495)). The critic gets the claim and its evidence objects only, never the proposer's reasoning.
- Network features beat single-row red flags: on Mexican federal procurement, adding supplier network features such as eigenvector centrality to classic red flags captured 32% more known positives ([Medina-Hernandez, Kertesz, Fazekas, arXiv 2512.19491](https://arxiv.org/abs/2512.19491)). Add a NetworkX centrality and shared-attribute term to the hypothesis prior score.
- A model reading raw transaction tables is near random (F1 0.00 on one dataset); keeping the top 10 features and retrieving similar labelled cases lifted F1 to 0.62 to 0.79, and a 5-point risk score beat a binary label ([FinFRE-RAG, arXiv 2512.13040](https://arxiv.org/pdf/2512.13040)). Pass a few fields and the rule outputs per vendor, and ask for a graded score, not yes or no.
- No validated numeric cut-offs exist for shell-company firmographics. FinCEN's May 2026 alert describes "recent incorporation with limited or no internet presence" and shared addresses in words only ([FinCEN Alert FIN-2026-Alert002](https://www.fincen.gov/system/files/2026-05/FinCEN-Alert-IRGC.pdf)). Make your thresholds (founded within N days of the first invoice, headcount of 2 or fewer) named, configurable assumptions printed in the case file and cited to that wording.
- Two Claude API facts for the writer step: the Citations API attaches `cited_text` from `search_result` or document blocks and the quoted text does not count toward output tokens, but enabling citations in the same call as `output_config.format` returns a 400 ([Citations](https://platform.claude.com/docs/en/build-with-claude/citations), [search results](https://platform.claude.com/docs/en/build-with-claude/search-results), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)). So propose and critique use structured output with `strict: true` tools, and the writer is a separate call with citations over `search_result` blocks whose `source` is the log-entry hash. Also from the same docs: prefilling the assistant turn returns a 400 on 4.6+ models, thinking is set with `effort` (`budget_tokens` is deprecated), and placing long data first with the query last improved quality by up to 30% in Anthropic's tests.

Libraries the second pass adds: `cleanco` to strip legal suffixes before RapidFuzz while keeping the raw name ([cleanco](https://pypi.org/project/cleanco/2.0.1)), `rfc8785` for JCS canonical JSON ([rfc8785](https://pypi.org/project/rfc8785/0.1.2)), and WeasyPrint for Markdown to PDF if a PDF is wanted.

**Prompting and model configuration** ([prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices), [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)):

- Use XML tags to separate content types, with consistent names: `<tip>`, `<typologies>`, `<ledger_stats>`, `<evidence id="...">`, `<instructions>`; nest documents as `<documents><document index="n"><source>...</source><document_content>...</document_content></document></documents>`.
- Ask for `<thinking>` before `<answer>` on the propose and critique steps; use structured output or a tool schema for anything another module consumes.
- Put the typology list, rule descriptions, schemas and instructions first and mark them with `cache_control`; cache reads cost 0.05x on Opus 5.5 and Sonnet 5.5, minimum 512 tokens, 5-minute lifetime refreshed on each hit. Changing tool definitions invalidates the cache, so freeze them early.
- Current model IDs from the [models overview](https://platform.claude.com/docs/en/about-claude/models/overview): `claude-opus-5-5` ($4 / $20 per MTok), `claude-sonnet-5-5` ($2 / $10), `claude-haiku-5-5` (from $0.10 / $0.50); the page says to start with Opus 5.5 for most workloads. Use Opus for propose and critique (few calls), Haiku for the entity-match yes / no / unsure (many calls).

**Skip list for five hours:** GNNs, fine-tuning, Splink, vector databases, a web UI, LangChain-style frameworks, and anything that needs training data you do not have.

## Recommended architecture for the day

Build a six-stage pipeline in Python where the model makes exactly three kinds of call (propose, match, critique), every other step is deterministic code, and one hash-chained log wraps all of it. That split is what the research rewards, it keeps six parallel coders out of each other's files, and it makes the demo's "click any sentence to its evidence" possible.

&#91;embedded content: investigation pipeline: 6 stages, Crustdata on stage 3, one log for all\]

Only stages 2, 3 and 5 call a model; stage 3 is the only one that calls Crustdata; every stage writes to the same hash-chained log, which the case file's root hash and `verify.py` close.

**Language and stack.** Python 3.12, one language for all six sessions; the data, matching and graph libraries have no TypeScript equal of the same maturity.

| Concern | Choice | Why |
| --- | --- | --- |
| Model calls | `anthropic` SDK with tool use and structured output; Opus 5.5 for propose and critique, Haiku 5.5 for match | Three call sites, typed schemas, prompt caching on the static prefix |
| Schemas | Pydantic v2: `Hypothesis`, `Entity`, `EvidenceObject`, `Finding`, `LogRecord` | The contract the six sessions code against from minute 20 |
| Ledger analytics | pandas (or DuckDB for SQL-minded teammates) | Vectorised rule tests over the whole ledger in milliseconds |
| Entity resolution | `rapidfuzz.process.cdist` + Crustdata Identify / Search | Block, score, shortlist; the model only sees the shortlist |
| Graph | NetworkX | `has_path` and `shortest_path` give printable link evidence |
| HTTP | `httpx` + a token-bucket limiter per endpoint, `tenacity` retry on 429 using `X-RateLimit-Reset` | Rate limits, not credits, are the constraint |
| Log | `hashlib.sha256` over RFC 8785 canonical JSON (`rfc8785` package or `json.dumps(sort_keys=True, separators=(',', ':'))`), JSONL, Merkle root | Verifier is 20 lines and runs on camera |
| Case file | Jinja2 to Markdown, with `[E12]` style evidence anchors and an exhibits appendix; `pandoc` to PDF if time allows | Judges read Markdown on GitHub without opening anything |
| CLI | Typer: `investigate --tip tip.txt --ledger ledger.csv --vendors vendors.csv --staff staff.csv --out case/` | One command on camera |
| Tests | pytest over `cases/*.json` planted cases | The eval harness and the demo rehearsal are the same thing |

**The six stages.**

1. **Ingest and normalise.** Parse the tip as free text; load the three CSVs with tolerant parsing (encoding sniffing, date and currency coercion, whitespace and casing normalisation, Ltd / Pvt / Inc stripping). Emit typed tables plus a data-quality note that becomes a case-file section. Every raw file is hashed into the log here.
2. **Propose hypotheses.** One Opus call. Input: the tip, the typology list (section 2), summary statistics of the ledger, the list of vendor and staff names. Output: 3 to 8 `Hypothesis` objects, each with `typology`, `subjects` (staff), `objects` (vendors), `tests_to_run`, and a prior score. The model picks from the menu; it does not invent typologies.
3. **Resolve entities.** Vendors: normalise, Identify (free, 25 per call), accept `confidence_score` above threshold, Enrich the accepted set in batches of 25 with `fields` explicit. Staff: Person Search with name plus employer in `exact` mode, then Enrich the `profile_url`. Ambiguous shortlists go to Haiku as yes / no / unsure with the candidate records in `<candidates>` tags. Anything below threshold is marked `unresolved`, which is a valid, citable state.
4. **Test with coded rules.** Each test is a pure function `(tables, graph, entities) -> list[EvidenceObject]`, where an `EvidenceObject` carries `id`, `test`, `subject`, `quote` (the literal rows or record fields), `source` (ledger row IDs or Crustdata record ID plus `updated_at`), and `hash`. The career-overlap test lines up `employment_details.past[].start_date / end_date` against payment dates; the shell-vendor test combines headcount, `year_founded`, website and address type; the threshold test counts invoices in the 5% band under each limit.
5. **Critique and rank.** A second Opus call with a fresh context: it sees each hypothesis and its evidence objects only, and returns `Substantiated`, `Unfounded` or `Unsubstantiated` with the evidence ids it relied on and the strongest counter-evidence. A verdict needs at least two independent tests; otherwise it is `Unsubstantiated` by rule, not by model.
6. **Write and verify.** The writer is a separate call that receives only findings and evidence objects, never raw tool output, passed as search\_result blocks whose source is the log-entry hash, with the Citations API on so every sentence carries cited\_text; citations cannot share a call with structured output (the API returns a 400), which is one more reason propose, critique and write are three calls. A deterministic pass rejects any sentence with no id or whose quoted text is not in the hashed source; the file is rendered only when the pass is clean. The Merkle root and the verifier command are printed on the first page.

**Algorithmic optimisations that buy accuracy and time.**

- Compute every rule signal once, vectorised, before any model call; pass statistics as evidence, not rows (AuditCopilot's ablation: removing the statistics collapsed recall to 0.07).
- Block before matching: first token or domain as the blocking key, then `cdist`; the model sees at most the top 3 candidates per name.
- Batch Identify and Enrich 25 at a time, run endpoints concurrently under their own RPM budgets, and cache every raw response on disk keyed by the request hash. The cache is also the evidence store, and it makes re-runs instant when a recording take fails.
- Rank hypotheses by prior score and test the strongest first; stop testing a hypothesis once one substantiating and one refuting test have both run.
- Benford on the full population only, as a lead; threshold-band counts are the allegation-grade signal.
- Temperature 0 on match and critique; retries capped at 2 with schema validation; `unsure` and `Unsubstantiated` are legal outputs so the model is never forced to guess.
- Cache the static prefix (instructions, typologies, schemas) with `cache_control`; it is over 512 tokens and identical across all three call sites.

**The planted dataset** (build before 10:30, it is data not code). Invent the audited company. Use real Crustdata companies as vendors: 10 to 15 names mixing large established firms, one or two tiny firms, and one name that resolves to nothing. For staff, use the team's own LinkedIn profiles where a member once interned or worked at a company you then make a vendor: the hidden link is real, consensual and verifiable live. Plant:

- Two true positives of different typologies: a career-overlap conflict of interest, and a shell vendor whose address matches a staff address and whose Crustdata record shows 1 to 2 headcount founded just before its first invoice.
- One false lead: the tip names a staff member who shares a name with someone who really worked at the vendor; the agent must disambiguate by employer and location and return `Unfounded`.
- Two clean controls: large vendors with normal invoice patterns and no graph path, returned as cleared.
- Messiness: three spellings of one vendor, mixed date formats, INR with and without commas, a blank row, a duplicated header.

Hold one extra case back for the recording. The agent's `--redact` flag replaces person names with initials in the rendered file while keeping record IDs, so the public video exposes no real individual.

**Eval harness.** Each case is a JSON file with expected verdicts per allegation. Metrics: per-allegation precision and recall, false-clear rate on planted positives, citation validity (share of sentences whose evidence id resolves and whose hash verifies), and the `Unsubstantiated` rate (above zero on false leads, near zero on controls). Run each case three times and count only cases solved every time.

## Working as six with three people

Six parallel Claude Code sessions work only if each one owns its own files, its own git worktree and a contract it codes against; Anthropic's own guidance says two sessions editing the same file "leads to overwrites" and to "break the work so each teammate owns a different set of files" ([agent teams docs](https://code.claude.com/docs/en/agent-teams)). Claude Code now has worktrees built in: `claude --worktree <name>` creates `.claude/worktrees/<name>/` on branch `worktree-<name>`, and `.worktreeinclude` copies gitignored files such as `.env` into each one ([worktrees docs](https://code.claude.com/docs/en/worktrees)).

```bash
# once, by the repo owner, before 10:30 (setup, not code)
echo ".claude/worktrees/" >> .gitignore
printf '.env\n.env.local\n' > .worktreeinclude
# each person, two terminals or two VS Code tabs (Cmd/Ctrl+Shift+Esc opens a new Claude tab)
claude --worktree ingest      # session A -> branch worktree-ingest
claude --worktree rules       # session B -> branch worktree-rules
```

**The contract comes first.** In the first 20 minutes after 10:30 one session commits `schemas.py` (the Pydantic models), `fixtures/` (a tiny ledger, vendor and staff set plus two canned Crustdata responses) and stub clients to `main`. Every other session builds against those stubs and swaps in the real thing when it lands. This is the step that turns three people into six; without it the sessions block on each other.

| Session | Owns (directories) | Builds | Done when |
| --- | --- | --- | --- |
| 1 | `schemas/`, `fixtures/`, `cli/` | Pydantic contract, Typer CLI, pipeline skeleton that calls stubs | `investigate` runs end to end on fixtures with stub stages |
| 2 | `ingest/` | Tolerant CSV and tip loaders, normalisation, data-quality notes | All 5 messy fixtures parse; unit tests green |
| 3 | `crustdata/`, `resolve/` | httpx client with rate limiter, disk cache, Identify / Enrich / Person Search, RapidFuzz shortlist, Haiku match | Vendors and staff in the fixture resolve with record IDs and `updated_at` |
| 4 | `rules/`, `graph/` | The 14 tests from section 2 as pure functions, NetworkX link finder, Benford and threshold tests | Each test returns `EvidenceObject`s on the fixture with known answers |
| 5 | `agents/` | Propose and critique prompts with XML tags, structured output, caching, retries | Fixture tip yields 3 to 8 typed hypotheses; critique returns the three labels |
| 6 | `audit/`, `report/`, `cases/` | Hash-chained log and `verify.py`, Jinja2 case file, sentence-to-evidence check, planted cases and pytest harness | `verify.py` passes; a sentence without evidence fails the build |

**Rules of the road.**

- One merge captain (session 1's human) merges to `main`; everyone else rebases on `origin/main` before each push and pushes at least every 45 minutes. Trunk-based development's own guidance is to commit to trunk several times a day in short-lived branches ([trunkbaseddevelopment.com](https://trunkbaseddevelopment.com/)).
- `CLAUDE.md` under 200 lines, committed: the run and test commands, the module ownership table above, "never edit outside your directory", the schema file as the source of truth, and the Crustdata header quirks ([memory docs](https://code.claude.com/docs/en/memory), [best practices](https://code.claude.com/docs/en/best-practices)). Use `.claude/rules/*.md` with `paths:` frontmatter for per-directory rules.
- A PostToolUse hook in `.claude/settings.json` that runs `ruff format` and the directory's tests on every edit, so a session finds its own breakage before the merge captain does ([hooks guide](https://code.claude.com/docs/en/hooks-guide)).
- Review in a fresh session: Anthropic's guidance is that a separate session reviewing a diff "won't be biased toward code it just wrote"; at 13:30 pair every session's diff with a review from another member's session ([best practices](https://code.claude.com/docs/en/best-practices)).
- Each worktree needs its own `venv` (`uv venv && uv pip install -e .` inside it) and its own port if anything serves; approvals saved with "don't ask again" apply to every worktree, so grant them once in the main checkout.
- `.mcp.json` committed with `${CRUSTDATA_API_KEY}`; each person exports the key in their shell before launching, and interactive sessions approve the project server once ([MCP docs](https://code.claude.com/docs/en/mcp)).

**Sessions talking to each other.** Claude Code v2.1.224 or later (v2.1.234 on native Windows) lets one session message another on the same machine over a local socket, with nothing to enable; Claude finds targets with `ListAgents` and sends with `SendMessage`, and you can address a session as `@rules` once it has a name ([cross-session messaging docs](https://code.claude.com/docs/en/cross-session-messaging)). The docs name your exact use case: "when sessions work the same repository in separate worktrees, Claude can tell the other sessions what landed." How to use it today:

- Name each session after its module when you launch it: `claude --worktree rules --name rules`. `/list-agents` shows what each session can reach.
- When the contract owner changes `schemas.py`, prompt it: "Tell @ingest and @rules what changed in the schema and that main is safe to rebase on." The other sessions read the message between tool calls and adjust without you re-explaining.
- Use the idle notice (v2.1.236+): "Tell me when @rules finishes" lets your second session watch your first without polling.
- Limits that matter: messages are plain text, never files; a message cannot approve a permission prompt or change configuration; sessions on different machines see each other only through Remote Control with a claude.ai sign-in, and API-key sessions cannot reach other machines. So messaging is for your own two sessions; between teammates, `git` and a group chat remain the bus, unless you set up Remote Control before 10:30.
- A session inside a container cannot reach one on the host, so run both of your sessions natively.

The agent you ship should call the `anthropic` SDK directly rather than being a `claude -p` wrapper: headless mode is documented for scripts and CI, and the Agent SDK bundles the whole Claude Code binary, which is more than a six-stage pipeline needs ([headless docs](https://code.claude.com/docs/en/headless), [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)). Note the cost line in Anthropic's own write-up: agents use about 4x the tokens of chat and multi-agent systems about 15x, so keep the model calls to the three sites in section 5 ([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)).

## Winning the demo

The two-minute video is the only thing Phase 1 judges see, so it is a product, scripted and rehearsed, and it must show all three outcomes: a hidden link found, a false lead refuted, a clean vendor cleared. A video that shows only the hit looks like a keyword search; the refutation and the clearance are what make it an investigator.

| Time | On screen | Voice-over (one sentence each) |
| --- | --- | --- |
| 0:00 to 0:15 | The tip text file and the three messy CSVs, open side by side; a highlighted inconsistent vendor spelling and a broken date | "An anonymous tip, a ledger nobody has cleaned, a vendor list and a staff list: this is what a forensic auditor starts with." |
| 0:15 to 0:25 | Terminal, cold start, one command: `investigate --tip ... --out case/` | "One command, no human in the loop from here." |
| 0:25 to 1:05 | Live log scrolling, sped up 2x where needed: hypotheses listed by typology, Identify and Enrich calls with record IDs, a 429 retried, a vendor marked unresolved, rule tests firing | "It turns the tip into hypotheses from the ACFE fraud tree, resolves every vendor and person in Crustdata's graph, and tests each one with coded rules, not opinions." |
| 1:05 to 1:35 | The rendered case file: executive summary with three verdicts; click one sentence's `[E7]` anchor to the exhibit showing the career history dates beside the payment dates; the false lead's `Unfounded` paragraph with the disambiguation; the cleared vendor | "Substantiated: the approver worked at the vendor until three months before the first payment. Unfounded: a different person with the same name. Cleared: a real company with 2,000 staff and normal invoices." |
| 1:35 to 1:50 | `python verify.py case/log.jsonl` printing the chain check and the Merkle root that matches the file's first page; then edit one log line and run again to show it fail | "Every tool call is in a hash-chained log; change one byte and verification fails." |
| 1:50 to 2:00 | Repo README with the eval table: planted cases, precision, false-clear rate, citation validity | "On planted cases it finds the hidden link, refutes the false lead and clears clean vendors, three runs out of three." |

Judges' own words: JetBrains' judging notes say to "show something working within about 90 seconds", to "mock everything you can", and that trying to do too much "guarantee\[s\] that nothing in your demo works end to end" ([JetBrains, June 2026](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/)); a judge with a year on panels calls a working live demo "the single largest score differentiator" and records a 60-second capture as insurance ([dev.to](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)); Devpost's judges say the video is often their first indicator of a project ([Devpost](https://info.devpost.com/blog/hackathon-judging-tips)). End the run with a small metrics panel: wall time, token cost, thresholds used, precision and recall on planted cases. A 2026 survey of 49 LLM fraud deployments found none reported per-decision latency, cost or calibration ([Gabani, arXiv 2607.13078](https://arxiv.org/pdf/2607.13078)), so a team that prints them stands out.

**Production notes.**

- Record on the held-out case nobody has run; that is the "request it has never seen" in the brief, said out loud.
- Keep the demo dataset small (10 vendors, 8 staff) so a cold run finishes in about 90 seconds at 15 RPM on Enrich; show the full-size eval only as a table.
- Terminal font at 18pt or larger, dark theme, no notifications; 1080p screen recording; a USB or headset microphone; one person speaks, one drives, one watches the clock.
- Record three full takes starting at 14:45; pick the best, trim, upload by 15:15. No slides, no title cards longer than two seconds.
- The README mirrors the video: the command, the architecture picture from section 5, the eval table, the verifier instructions, and the Crustdata endpoints used.

**The live final.** Finalists pitch and demonstrate live at 17:30. Run the same held-out case live, but have the disk cache from the recording ready as a fallback flag (`--offline`) in case the venue network or Crustdata's rate limits bite. The judges are Crustdata engineers and IIT Bombay professors: the engineers will ask which endpoints you used and how you handled their 429s; the professors will ask how you avoided false accusations. Both answers are already in the case file.

## Sources

All pages were opened on 31 October 2026. The hackathon brief and event page are the team's own uploads (ContextCon PS, Crustdata; ContextCon 03 About page).

**Forensic practice**

- [ACFE Fraud Examiners Manual 2026, sample chapter: Planning and Conducting a Fraud Examination](https://cms.acfe.com/-/media/files/acfe/word-documents/fem_samplechapter_planning_and_conducting_2026.pdf)
- [ACFE Report to the Nations 2026 (full PDF, ACFE Mexico mirror)](https://www.acfe-mexico.com.mx/inicio/sitepad-data/uploads/2026/07/Reporte-a-las-Naciones-2026.pdf) and [acfe.com landing page](https://www.acfe.com/report-to-the-nations); [2024 edition (Ivey mirror)](https://www.ivey.uwo.ca/media/kjljj5cy/2024-report-to-the-nations.pdf)
- [Wells, Billing schemes part 1: shell companies, Journal of Accountancy 2002](https://www.journalofaccountancy.com/issues/2002/jul/billingschemespart1shellcompaniesthatdontdeliver/)
- [Nigrini and Mittermaier, Benford's law, Journal of Accountancy 1998](https://www.journalofaccountancy.com/issues/1998/nov/audit-nov-1998/)
- [Lawrence and Wells, Basic legal concepts, Journal of Accountancy 2004](https://www.journalofaccountancy.com/issues/2004/oct/basiclegalconcepts/)
- [Diligent, Identify accounts payable fraud](https://www.diligent.com/insights/fraud/identify-accounts-payable-fraud)
- [Vona, CFE conference handout on vendor fraud analytics](https://na.eventscloud.com/file_uploads/3cb0d524fa84069d7f653991827b937c_Tuesday_4_Vona_02_Handout.pdf)
- [City of Tulsa Internal Audit, vendor-to-employee match](https://www.cityoftulsa.org/media/2452/2015-vendortoemployeereport.pdf); [Orange County Auditor-Controller CAAT report](https://ocauditor.gov/wp-content/uploads/2017/08/2941-F-CAAT-December-2009.pdf)
- [ACFE Insights, the employee and vendor nexus](https://acfeinsights.squarespace.com/acfe-insights/2022/12/22/case-study-the-employee-and-vendor-nexus); [ACFE Insights, writing a report without declaring guilt](https://acfeinsights.squarespace.com/acfe-insights/how-write-report-without-declaring-guilt-or-innocence)
- [Minnesota State Auditor, Phantom vendors](https://www.osa.state.mn.us/audit-resources/audit-guidance/avoiding-pitfalls-articles/phantom-vendors); [Arizona Auditor General report 18-406](https://www.azauditor.gov/sites/default/files/2023-11/18-406.pdf)
- [IDEA scripting, same-same-different test](https://www.ideascripting.com/Same-Same-Different-Test); [Case IQ, 16 ways to identify fictitious vendors](https://pages.caseiq.com/rs/219-YZJ-775/images/16-ways-to-identify-fictitious-vendors-version-2.pdf?version=0); [Sequence Inc, detecting billing schemes](https://www.sequenceinc.com/fraudfiles/detecting-billing-schemes)
- [Deloitte, SAP GRC red-flag brochure](https://www2.deloitte.com/content/dam/Deloitte/sg/Documents/risk/sea-risk-sap-governance-risk-compliance-red-flag-brochure.pdf); [Weaver, data monitoring for fraud detection](https://info.weaver.com/hubfs/3E.%20Leveraging%20Data%20Monitoring%20and%20Analytics%20for%20Fraud%20Detection%20%20Prevention_EL%20Edits%200907.pdf)
- [LA County Fraud Hotline, investigative process and finding labels](https://fraud.lacounty.gov/investigative-process/); [CFE study guide, writing the fraud examination report](https://open-exam-prep.com/study-guides/cfe/investigation-reporting-testimony/writing-the-fraud-examination-report); [CFE study guide, evidence and chain of custody](https://open-exam-prep.com/study-guides/cfe/investigation-planning-evidence/evidence-types-chain-of-custody-documentation)
- [CIGIE Quality Standards for Investigations, July 2025](https://www.ignet.gov/sites/default/files/files/Quality%20Standards%20for%20Investigations%20July-2025.pdf); [FinCEN SAR narrative guidance](https://www.fincen.gov/sites/default/files/shared/sarnarrcompletguidfinal_112003.pdf)
- [KPMG First Notes, mandatory reporting of fraud by auditors (Companies Act s.143(12))](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2023/08/firstnotes-mandatory-reporting-of-fraud-by-an-auditor.pdf); [ISACA Journal, Understanding and applying Benford's law](https://www.isaca.org/resources/isaca-journal/past-issues/2011/understanding-and-applying-benfords-law)

**Crustdata**

- [API introduction and headers](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md); [pricing](https://docs.crustdata.com/general/pricing.md); [rate limits](https://docs.crustdata.com/general/rate-limits.md); [credits and response headers](https://docs.crustdata.com/general/credits.md); [data updates](https://docs.crustdata.com/general/data-updates.md)
- [Company Identify](https://docs.crustdata.com/company-docs/identify/introduction.md); [Company Enrich](https://docs.crustdata.com/company-docs/enrichment/introduction.md) and [its schema](https://docs.crustdata.com/api-reference/company-apis/get-full-company-enrichment.md); [Company Search](https://docs.crustdata.com/company-docs/search/introduction.md)
- [Person Search](https://docs.crustdata.com/person-docs/search/introduction.md) and [field reference](https://docs.crustdata.com/person-docs/search/reference.md); [Person Enrich](https://docs.crustdata.com/person-docs/enrichment/introduction.md) and [its schema](https://docs.crustdata.com/api-reference/person-apis/enrich-person-profiles-from-cached-dataset.md); [Person Identify](https://docs.crustdata.com/person-docs/identify/introduction.md)
- [Job Search](https://docs.crustdata.com/job-docs/search/introduction.md); [Web Search](https://docs.crustdata.com/web-docs/search/introduction.md); [Web Fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md); [Company Watcher](https://docs.crustdata.com/watcher-docs/company/entity.md); [Account credits](https://docs.crustdata.com/api-reference/account-apis/get-account-credit-balance.md)
- [MCP guide for agents](https://docs.crustdata.com/for-agents/mcp.md); [Claude plugin](https://docs.crustdata.com/integrations/claude-plugin.md); [CLI](https://docs.crustdata.com/for-agents/cli.md)

**Research, 2022 to 2026**

- [AuditAgent (arXiv 2510.00156)](https://arxiv.org/html/2510.00156v1); [AuditCopilot (arXiv 2512.02726)](https://arxiv.org/html/2512.02726v1); [FinRobot (arXiv 2405.14767)](https://arxiv.org/abs/2405.14767v1)
- [Peeters and Bizer, Entity matching using large language models (arXiv 2310.11244)](https://arxiv.org/pdf/2310.11244v3); [Splink](https://moj-analytical-services.github.io/splink/) and [MoJ write-up](https://www.gov.uk/government/publications/joined-up-data-in-government-the-future-of-data-linking-methods/splink-mojs-open-source-library-for-probabilistic-record-linkage-at-scale); [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)
- [ReAct (arXiv 2210.03629)](https://arxiv.org/abs/2210.03629); [Reflexion (arXiv 2303.11366)](https://arxiv.org/abs/2303.11366v4); [Google AI co-scientist](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/)
- [Verification gap in AI-scientist agents (arXiv 2608.05179)](https://arxiv.org/abs/2608.05179); [Localising faithfulness and citation errors in multi-agent deep research (arXiv 2608.24306)](https://arxiv.org/abs/2608.24306); [Attributable to Identified Sources (arXiv 2112.12870)](https://arxiv.org/abs/2112.12870v2); [Verify with Caution (arXiv 2501.14883)](https://arxiv.org/abs/2501.14883); [Good-Enough Structured Generation, NeurIPS 2025](https://neurips.cc/virtual/2025/131662)
- [RFC 6962, Certificate Transparency](https://www.rfc-editor.org/rfc/rfc6962); [RFC 3161, time-stamp protocol](https://www.rfc-editor.org/rfc/rfc3161); [Sigstore Rekor explainer](https://www.chainguard.dev/supply-chain-security-101/what-is-sigstore-rekor); [draft-sharif-agent-audit-trail-06](https://datatracker.ietf.org/doc/html/draft-sharif-agent-audit-trail-06); [OpenTelemetry GenAI semantic conventions write-up](https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions)
- [NetworkX bipartite algorithms](https://networkx.org/documentation/stable/reference/algorithms/bipartite.html); [NetworkX community detection](https://networkx.org/documentation/stable/reference/algorithms/community.html); [GNN fraud detection review (arXiv 2411.05815)](https://arxiv.org/abs/2411.05815)
- [Suh and Headrick on Benford sample sizes](https://core.ac.uk/download/67751317.pdf); [tau-bench and pass^k](https://sierra.ai/blog/benchmarking-ai-agents); [Inspect AI](https://inspect.aisi.org.uk/); [DeepEval](https://www.deepeval.com/docs/getting-started); [Braintrust](https://www.braintrust.dev/docs); [LangSmith evaluation](https://docs.langchain.com/langsmith/evaluation)

**Second research pass**

- [AbstentionBench (arXiv 2506.09038)](https://arxiv.org/pdf/2506.09038); [Chain-of-Verification (arXiv 2309.11495)](https://ar5iv.labs.arxiv.org/html/2309.11495); [Red flags and network features in Mexican procurement (arXiv 2512.19491)](https://arxiv.org/abs/2512.19491); [FinFRE-RAG (arXiv 2512.13040)](https://arxiv.org/pdf/2512.13040); [Agentic fraud investigation, FIA/FAA (arXiv 2506.11635)](https://arxiv.org/abs/2506.11635); [Gabani, deployment evidence in LLM fraud work (arXiv 2607.13078)](https://arxiv.org/pdf/2607.13078); [OrgForge-IT synthetic logs (arXiv 2603.22499)](https://arxiv.org/pdf/2603.22499)
- [FinCEN Alert FIN-2026-Alert002](https://www.fincen.gov/system/files/2026-05/FinCEN-Alert-IRGC.pdf); [Tiwari, Gepp and Kumar, UK shell companies, J. Economic Criminology 2025](https://www.sciencedirect.com/science/article/pii/S2949791424000757)
- [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs); [Citations](https://platform.claude.com/docs/en/build-with-claude/citations); [Search results](https://platform.claude.com/docs/en/build-with-claude/search-results); [Reduce hallucinations](https://docs.claude.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
- [cleanco](https://pypi.org/project/cleanco/2.0.1); [rfc8785](https://pypi.org/project/rfc8785/0.1.2); [PDF generation in Python](https://www.nutrient.io/blog/top-10-ways-to-generate-pdfs-in-python/)
- [JetBrains, notes from the judging table](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/); [What judges actually score](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l); [Devpost judging tips](https://info.devpost.com/blog/hackathon-judging-tips)

**Claude Code and Claude platform**

- [Worktrees](https://code.claude.com/docs/en/worktrees); [Memory and CLAUDE.md](https://code.claude.com/docs/en/memory); [Best practices](https://code.claude.com/docs/en/best-practices); [MCP](https://code.claude.com/docs/en/mcp); [Hooks guide](https://code.claude.com/docs/en/hooks-guide); [Skills](https://code.claude.com/docs/en/skills); [Subagents](https://code.claude.com/docs/en/sub-agents); [Headless](https://code.claude.com/docs/en/headless); [CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging); [Agent teams](https://code.claude.com/docs/en/agent-teams); [Agent view](https://code.claude.com/docs/en/agent-view); [VS Code](https://code.claude.com/docs/en/vs-code)
- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview); [quickstart](https://code.claude.com/docs/en/agent-sdk/quickstart); [Python](https://code.claude.com/docs/en/agent-sdk/python); [structured outputs](https://code.claude.com/docs/en/agent-sdk/structured-outputs); [MCP in the SDK](https://code.claude.com/docs/en/agent-sdk/mcp)
- [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview); [Model IDs and versions](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions); [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices); [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching); [MCP connector](https://platform.claude.com/docs/en/agents-and-tools/mcp-connector)
- [Anthropic, Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents); [Anthropic, How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system); [Trunk-based development](https://trunkbaseddevelopment.com/)
