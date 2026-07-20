<!-- GSD:project-start source:PROJECT.md -->
## Project

**Outreach Agent**

An AI-powered outreach tool that lets non-technical student org teammates run targeted email campaigns at scale without writing code. A teammate picks one of three goals — club sponsorship, productthon sponsorship, or client sourcing — and the agent handles finding contacts via Apollo.io, personalizing emails, and sending sequences automatically.

**Core Value:** Non-technical teammates can launch a full outreach campaign in minutes instead of hours, with zero manual contact-finding or email drafting required.

### Constraints

- **Tech**: Apollo.io API is the contact and sequencing layer — all outreach flows through Apollo
- **Users**: Non-technical teammates — UI must require zero technical knowledge to operate
- **Personalization**: AI-generated custom opening line per contact; rest of email is a template per path
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Backend / Agent Runtime
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Application language | AI ecosystem is Python-native; Streamlit and the Anthropic SDK are both Python-first. 3.12 is the stable sweet spot: supported by all libraries, no rough edges of 3.13. |
| Streamlit | 1.45+ (current: 1.54 per Context7) | UI framework + app server | Single process handles both UI and backend logic — no separate API server needed. Non-technical users interact via a browser UI with no code. Free hosting on Streamlit Community Cloud. Secrets management via `st.secrets` keeps API keys off disk and out of git. |
| requests or httpx | requests 2.32+ | Apollo REST calls | Apollo.io API is plain REST with JSON. No SDK needed. `httpx` if you want async; `requests` is simpler and fine for the synchronous pipeline the spec describes. |
| SQLite (via stdlib `sqlite3`) | built-in | Pipeline state tracking | One row per prospect, 7-column status enum (`found → selected → enriched → contact_created → drafted → approved → sequenced`). No Postgres overhead for a student org at <500 prospects/week. File lives alongside the app; Streamlit Community Cloud persists it between sessions within a deployment. |
### AI / LLM Layer
| Technology | Version/Model | Purpose | Why |
|------------|--------------|---------|-----|
| Anthropic Python SDK | `anthropic>=0.117.0` | Claude API client | Official SDK; handles auth, retries, streaming. Simple `client.messages.create()` call per contact. |
| claude-haiku-4-5-20251001 | Current Haiku generation | Personalized opening-line generation | One short email opening per contact (~50 output tokens). Haiku 4.5 costs $1.00/MTok input, $5.00/MTok output. At 50 contacts/campaign and ~500 input tokens/call, that's ~$0.025 per campaign run — negligible on a student budget. Sonnet is 3x more expensive with no quality difference for a single-sentence personalization task against structured contact data. |
- 50 contacts × 500 input tokens = 25,000 tokens = $0.025
- 50 contacts × 60 output tokens = 3,000 tokens = $0.015
- Total per campaign: ~$0.04
### Apollo.io Integration
### Frontend / UI
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Streamlit | 1.45+ | All UI components | `st.dataframe` for search results, `st.checkbox` / `st.multiselect` for human review gate, `st.text_area` for editable draft review, `st.selectbox` for outreach path selection, `st.toggle` for auto-send vs review mode. Zero JavaScript. Non-technical teammates can use it immediately. |
| Streamlit `st.secrets` | built-in | Secret injection | `st.secrets["APOLLO_API_KEY"]` and `st.secrets["ANTHROPIC_API_KEY"]` — never in code, never in git. |
- `Home / Launch Campaign` — path selection + search params + run button
- `Review Queue` — pending approvals (drafts awaiting human sign-off)
- `Campaign Dashboard` — status table from SQLite, open/reply rate display (pulled from Apollo sequence analytics endpoint)
### Hosting
| Option | Cost | Why |
|--------|------|-----|
| Streamlit Community Cloud | Free | Deploys directly from a GitHub repo. Handles containerization automatically. Secrets managed via the platform console (not in the repo). Sufficient resources for a synchronous pipeline at <500 prospects/week. App spins down after inactivity but cold start is <5 seconds. |
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
## Key API Notes (Apollo.io)
### Auth
- **Method:** Master API key, passed as `x-api-key` header on every request.
- **NOT** OAuth 2.0 — that's for partners building on behalf of third-party Apollo customers. Not needed here.
- **Get key:** Apollo Settings → Integrations → API Keys → Create New Key (select Master).
- **Store:** `.streamlit/secrets.toml` locally (gitignored). Paste into Community Cloud secrets console at deploy time.
- **Test on startup:** `GET https://api.apollo.io/api/v1/auth/health` — returns 200 if key is valid. Boot-time check surfaces misconfiguration before a user starts a campaign.
### Rate Limits
| Endpoint | Limit |
|----------|-------|
| `/mixed_people/api_search` (search) | 100 req/min, 10 burst/sec |
| `/people/bulk_match` (enrichment) | 10 req/min, 2 burst/sec |
| `/contacts` (create single) | 600 req/hour |
| `/contacts/bulk_create` (create batch) | use instead of looping single creates |
| `/emailer_campaigns/{id}/add_contact_ids` (sequence enroll) | 600 req/hour |
- `/mixed_people/api_search` — **0 credits** (free search, no email returned)
- `/people/bulk_match` — **1 credit per person** when email is found (0 if no match). Max 10 people per call. Do NOT request `reveal_phone_number` — costs 8 additional credits per person, and v1 is email-only.
- Everything else — no credit consumption.
### Key Endpoints (Pipeline Order)
### Sequences are pre-built, not API-created
### Error Codes to Handle
| Code | Meaning | Action |
|------|---------|--------|
| 401 | Invalid/missing API key | Surface "Apollo connection failed" banner. Never retry. |
| 403 | Not a master key | Check key type in Apollo settings. |
| 422 | Missing required param | Surface `response.json()["message"]` directly in the UI — don't swallow. |
| 429 | Rate limit | Exponential backoff, max 3 retries. Log and surface if all retries fail. |
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
