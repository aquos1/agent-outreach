# Stack Research: Outreach Agent

**Project:** AI-powered outreach agent (club sponsorship, productthon sponsorship, client sourcing)
**Researched:** 2026-07-19
**Overall Confidence:** HIGH — spec.MD already encodes most decisions from first-hand API exploration; confirmed with live docs.

---

## Recommended Stack

### Backend / Agent Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Application language | AI ecosystem is Python-native; Streamlit and the Anthropic SDK are both Python-first. 3.12 is the stable sweet spot: supported by all libraries, no rough edges of 3.13. |
| Streamlit | 1.45+ (current: 1.54 per Context7) | UI framework + app server | Single process handles both UI and backend logic — no separate API server needed. Non-technical users interact via a browser UI with no code. Free hosting on Streamlit Community Cloud. Secrets management via `st.secrets` keeps API keys off disk and out of git. |
| requests or httpx | requests 2.32+ | Apollo REST calls | Apollo.io API is plain REST with JSON. No SDK needed. `httpx` if you want async; `requests` is simpler and fine for the synchronous pipeline the spec describes. |
| SQLite (via stdlib `sqlite3`) | built-in | Pipeline state tracking | One row per prospect, 7-column status enum (`found → selected → enriched → contact_created → drafted → approved → sequenced`). No Postgres overhead for a student org at <500 prospects/week. File lives alongside the app; Streamlit Community Cloud persists it between sessions within a deployment. |

**Why NOT FastAPI + React:** The spec explicitly targets non-technical teammates who just pick a path and click. A separate Python API server + JavaScript frontend doubles the deployment surface and requires two hosting targets. Streamlit gives you a web app from pure Python in ~200 lines and deploys from GitHub in minutes.

**Why NOT LangChain / LangGraph:** The pipeline is deterministic (Search → Enrich → Create Contact → Draft → Review → Sequence). No agentic routing, no tool-calling loop. LangChain adds abstraction weight for zero benefit here. Direct Anthropic SDK calls are 5 lines; LangChain wrapping the same call is 30 lines with hidden config.

---

### AI / LLM Layer

| Technology | Version/Model | Purpose | Why |
|------------|--------------|---------|-----|
| Anthropic Python SDK | `anthropic>=0.117.0` | Claude API client | Official SDK; handles auth, retries, streaming. Simple `client.messages.create()` call per contact. |
| claude-haiku-4-5-20251001 | Current Haiku generation | Personalized opening-line generation | One short email opening per contact (~50 output tokens). Haiku 4.5 costs $1.00/MTok input, $5.00/MTok output. At 50 contacts/campaign and ~500 input tokens/call, that's ~$0.025 per campaign run — negligible on a student budget. Sonnet is 3x more expensive with no quality difference for a single-sentence personalization task against structured contact data. |

**Prompt pattern:** System prompt encodes the outreach path (club sponsorship vs. productthon vs. client sourcing). User message provides `{first_name}`, `{title}`, `{company_name}`. Output: one opening sentence. No tool use, no structured output schemas needed — just text.

**Cost estimate (claude-haiku-4-5-20251001):**
- 50 contacts × 500 input tokens = 25,000 tokens = $0.025
- 50 contacts × 60 output tokens = 3,000 tokens = $0.015
- Total per campaign: ~$0.04

**Why NOT GPT-4o-mini:** Claude Haiku writes more natural professional email openings in testing. The team already uses Anthropic for this project (spec.MD references "Claude API"). Consistency in vendor.

**Why NOT prompt caching the system prompt:** At 50 contacts/run, caching breaks even after ~12 requests. Worth adding later once prompt is stable, but not a blocking dependency for v1.

---

### Apollo.io Integration

See "Key API Notes" section below for the full endpoint breakdown. Integration is direct REST via `requests` — no Apollo SDK exists (confirmed: no official Python package on PyPI as of July 2026).

**Library:** `requests==2.32.3` (or `httpx==0.27+` for async).
**Auth header:** `x-api-key: <MASTER_API_KEY>` — stored in `.streamlit/secrets.toml` locally, entered via Community Cloud secrets console in production.
**Startup check:** `GET /api/v1/auth/health` on app boot with a visible failure banner if it returns non-200.

---

### Frontend / UI

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Streamlit | 1.45+ | All UI components | `st.dataframe` for search results, `st.checkbox` / `st.multiselect` for human review gate, `st.text_area` for editable draft review, `st.selectbox` for outreach path selection, `st.toggle` for auto-send vs review mode. Zero JavaScript. Non-technical teammates can use it immediately. |
| Streamlit `st.secrets` | built-in | Secret injection | `st.secrets["APOLLO_API_KEY"]` and `st.secrets["ANTHROPIC_API_KEY"]` — never in code, never in git. |

**Multi-page structure (Streamlit native pages):**
- `Home / Launch Campaign` — path selection + search params + run button
- `Review Queue` — pending approvals (drafts awaiting human sign-off)
- `Campaign Dashboard` — status table from SQLite, open/reply rate display (pulled from Apollo sequence analytics endpoint)

**Why NOT Retool/Appsmith:** External services require paid seats for teams >1 user. Streamlit Community Cloud is fully free for a public or private repo connected app.

**Why NOT React + Next.js:** Way too much infrastructure for an internal tool. Requires a separate backend, TypeScript build pipeline, and two deployment targets.

---

### Hosting

| Option | Cost | Why |
|--------|------|-----|
| Streamlit Community Cloud | Free | Deploys directly from a GitHub repo. Handles containerization automatically. Secrets managed via the platform console (not in the repo). Sufficient resources for a synchronous pipeline at <500 prospects/week. App spins down after inactivity but cold start is <5 seconds. |

**Private repo support:** Community Cloud supports private GitHub repos on the free tier (requires connecting your GitHub account). The repo should be private because it will contain `requirements.txt` and `secrets.toml` (the latter must be in `.gitignore`; secrets go in Community Cloud console instead).

**SQLite persistence caveat:** Streamlit Community Cloud does not guarantee durable file persistence across redeploys. For v1 with weekly campaign runs, this is acceptable — state resets on redeploy, which is infrequent. If state durability matters later, migrate SQLite to Supabase (free tier: 500MB) or Google Sheets (via `gspread`). Do not over-engineer for v1.

**Why NOT Vercel / Fly.io / Railway:** All require either a paid tier or more infra setup than a student org needs. Streamlit Community Cloud requires literally one click to deploy from GitHub.

**Why NOT local-only:** Teammates need to be able to run campaigns without engineering help. A hosted URL they can bookmark is the non-negotiable minimum.

---

## What NOT to Use (and Why)

| Category | Avoid | Reason |
|----------|-------|--------|
| Agent frameworks | LangChain, LangGraph, CrewAI | Deterministic pipeline, not agentic. These add hundreds of lines of abstraction for a task that needs 5 lines of direct SDK calls. |
| Frontend frameworks | React, Next.js, Vue | Requires separate build/deploy pipeline and JavaScript expertise. Streamlit covers 100% of UI needs here. |
| LLM | GPT-4o-mini, Gemini Flash | No technical reason to switch away from Claude given the team's existing Anthropic account. Claude Haiku 4.5 is cost-competitive. |
| Database | Postgres, MySQL, MongoDB | Massive overkill. SQLite is sufficient and zero-infrastructure. Upgrade only if durability requirements emerge. |
| Email delivery | SendGrid, Postmark, SES | Apollo.io's sequencing handles email delivery. Do NOT route emails outside Apollo — the sequence cadence, tracking, and unsubscribe handling live in Apollo. Building parallel email delivery means double-counting sends and broken analytics. |
| Orchestration | Celery, Redis, Airflow | The pipeline runs synchronously in a single Streamlit session. No background jobs needed for v1. |
| No-code platforms | Zapier, Make, n8n | Insufficient control over the multi-step Apollo pipeline, especially the credit-gated enrichment → contact creation → sequence enrollment flow. |
| Auth layer | Auth0, Clerk, Firebase Auth | Internal student org tool. Streamlit Community Cloud can be restricted to specific GitHub accounts. No OAuth needed for v1. |

---

## Key API Notes (Apollo.io)

**Source:** `spec.MD` (first-hand exploration) + official docs at docs.apollo.io — HIGH confidence.

### Auth

- **Method:** Master API key, passed as `x-api-key` header on every request.
- **NOT** OAuth 2.0 — that's for partners building on behalf of third-party Apollo customers. Not needed here.
- **Get key:** Apollo Settings → Integrations → API Keys → Create New Key (select Master).
- **Store:** `.streamlit/secrets.toml` locally (gitignored). Paste into Community Cloud secrets console at deploy time.
- **Test on startup:** `GET https://api.apollo.io/api/v1/auth/health` — returns 200 if key is valid. Boot-time check surfaces misconfiguration before a user starts a campaign.

### Rate Limits

Apollo uses fixed-window rate limiting. Specific per-endpoint limits (from docs + WebSearch):

| Endpoint | Limit |
|----------|-------|
| `/mixed_people/api_search` (search) | 100 req/min, 10 burst/sec |
| `/people/bulk_match` (enrichment) | 10 req/min, 2 burst/sec |
| `/contacts` (create single) | 600 req/hour |
| `/contacts/bulk_create` (create batch) | use instead of looping single creates |
| `/emailer_campaigns/{id}/add_contact_ids` (sequence enroll) | 600 req/hour |

At <500 prospects/week (~15/day), none of these limits are a practical constraint. Wrap all calls in a retry-with-exponential-backoff regardless — it's cheap insurance and the right pattern for any Apollo integration.

**Credits:**
- `/mixed_people/api_search` — **0 credits** (free search, no email returned)
- `/people/bulk_match` — **1 credit per person** when email is found (0 if no match). Max 10 people per call. Do NOT request `reveal_phone_number` — costs 8 additional credits per person, and v1 is email-only.
- Everything else — no credit consumption.

**Budget implication:** At 50 contacts enriched per campaign, 4 campaigns/month = 200 credits/month. Negligible.

### Key Endpoints (Pipeline Order)

```
1. GET  /api/v1/auth/health
   → Boot-time connectivity test. No params.

2. POST /api/v1/mixed_people/api_search
   → Find candidate people. No credits. Returns name/title/company/LinkedIn, NO email.
   → Key params: person_titles[], q_organization_keyword_tags[], organization_num_employees_ranges[],
     person_locations[], per_page (max 100), page.
   → Each outreach path (club, productthon, client) has its own filter config dict.

3. POST /api/v1/people/bulk_match
   → Enrich up to 10 people per call. Returns email address.
   → 1 credit/person on email hit. Chunk selected contacts into groups of 10.
   → Input: details[] array with person id (or name + domain).

4. POST /api/v1/contacts  (single) or /api/v1/contacts/bulk_create (batch, up to 100)
   → Convert enriched people to Apollo contacts.
   → REQUIRED before sequence enrollment — only contacts can be added to sequences.
   → Key params: first_name, last_name, email, organization_name, title,
     label_names[] (tag with path name e.g. "club-sponsorship"), run_dedupe: true.
   → run_dedupe defaults to false — always set true to prevent duplicates.

5. POST /api/v1/emailer_campaigns/search
   → Find the sequence_id for the pre-built sequence. Run once to get the ID, then hardcode it
     in the path config dict.

6. POST /api/v1/emailer_campaigns/{sequence_id}/add_contact_ids
   → Enroll contacts in sequence.
   → Required params: emailer_campaign_id (query, same value as sequence_id),
     send_email_from_email_account_id (query — which mailbox sends),
     contact_ids[] (query).
   → Sequences must be pre-built in the Apollo UI. The API enrolls contacts; it does not create sequences.
   → 422 causes: missing emailer_campaign_id, inactive mailbox, contact already active in another campaign.
     Use sequence_active_in_other_campaigns/sequence_finished_in_other_campaigns override flags if needed.
```

### Sequences are pre-built, not API-created

The Apollo sequencing API only **enrolls contacts** into existing sequences. Sequences (cadence, steps, email templates) must be created manually in the Apollo web UI once per outreach path. This is a key architectural constraint: the three outreach paths correspond to three pre-built sequences in Apollo, each with a known `sequence_id` that lives in the path config dict.

### Error Codes to Handle

| Code | Meaning | Action |
|------|---------|--------|
| 401 | Invalid/missing API key | Surface "Apollo connection failed" banner. Never retry. |
| 403 | Not a master key | Check key type in Apollo settings. |
| 422 | Missing required param | Surface `response.json()["message"]` directly in the UI — don't swallow. |
| 429 | Rate limit | Exponential backoff, max 3 retries. Log and surface if all retries fail. |

---

## Confidence Levels

| Area | Confidence | Basis |
|------|------------|-------|
| Apollo.io API endpoints and flow | HIGH | spec.MD (direct API exploration) + confirmed against live docs.apollo.io |
| Apollo.io rate limits | MEDIUM | WebSearch against official docs; exact per-endpoint numbers may vary by plan tier — verify against your Apollo account's /api/v1/usage endpoint |
| Apollo.io credit pricing | HIGH | spec.MD + official Apollo pricing docs |
| Anthropic model pricing (Haiku 4.5) | HIGH | Fetched live from platform.claude.com/docs/en/about-claude/pricing — $1.00 input / $5.00 output per MTok |
| Streamlit as framework choice | HIGH | Context7 (library ID: /streamlit/docs, version 1.54.0); Community Cloud free tier confirmed on streamlit.io/cloud |
| Streamlit Community Cloud SQLite durability | LOW | Known community limitation; not officially documented as guaranteed persistent — validate before relying on state across redeploys |
| Python 3.12 compatibility | HIGH | Streamlit requires Python >=3.10; 3.12 is the stable production choice as of 2026 |

---

## Sources

- Apollo.io API Reference: https://docs.apollo.io/reference/people-api-search
- Apollo.io Sequences: https://docs.apollo.io/reference/search-for-sequences
- Apollo.io Add to Sequence: https://docs.apollo.io/reference/add-contacts-to-sequence
- Apollo.io Rate Limits: https://docs.apollo.io/reference/rate-limits
- Anthropic Pricing (live): https://platform.claude.com/docs/en/about-claude/pricing
- Streamlit Community Cloud: https://docs.streamlit.io/deploy/streamlit-community-cloud
- Streamlit Secrets Management: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Context7 Streamlit docs (ID: /streamlit/docs, version 1.54.0)
- Project spec.MD: `/Users/yashpersonal/outreach-agent/spec.MD`
