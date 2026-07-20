# Architecture Research: Outreach Agent

**Domain:** AI-powered email outreach automation (contact discovery + LLM personalization + sequenced sending)
**Researched:** 2026-07-19
**Overall confidence:** HIGH for component structure and data flow; MEDIUM for Apollo.io stats API surface (underdocumented)

---

## System Components

### Component 1: Path Selection UI

**Responsibility:** Present the three outreach paths (club sponsorship, productthon sponsorship, client sourcing) to the user. Capture per-campaign settings: auto-send vs. queue-for-review toggle, optional parameter overrides (number of contacts to find, target geography, etc.).

**Boundary:** This is purely a form/wizard. It produces a structured `CampaignConfig` object and hands it to the Campaign Orchestrator. No AI calls, no API calls here.

**Communicates with:** Campaign Orchestrator (downstream), Dashboard (sibling, reads campaign state).

---

### Component 2: Campaign Orchestrator

**Responsibility:** Sequence-coordinates the three stages of a campaign run — contact discovery, personalization, and enrollment/queuing. Owns retry logic and error handling for each stage. Writes intermediate state to the database so a failed run can be inspected or retried.

**Boundary:** Does not call Apollo or the LLM directly — it delegates to the Apollo Client and the Personalization Engine. It is the unit of work that a background job runner picks up.

**Communicates with:** Apollo Client (outbound), Personalization Engine (outbound), Campaign Store / DB (read/write), Review Queue (write when mode is "queue for review").

**Critical design decision:** This must run outside the HTTP request cycle. A campaign run touches an external API (Apollo), calls an LLM N times (once per contact), then makes another Apollo API call for enrollment — easily 30–120 seconds for even a 20-contact run. Any framework timeout (Vercel: 10s default, 60s max on paid plans) will kill it mid-flight with no partial-completion guarantee. Architecture answer: push a job descriptor to a background queue immediately on campaign start; the orchestrator runs in a persistent worker process.

---

### Component 3: Apollo Client

**Responsibility:** Thin wrapper around the Apollo.io REST API. Two sub-responsibilities:

- **Contact Discovery:** Calls `POST /api/v1/mixed_people/api_search` with path-specific filter presets (titles, seniority, industry, geography). Returns raw people records. Each path has a filter template baked into the server (not user-configurable).
- **Sequence Enrollment:** Calls `POST /api/v1/emailer_campaigns/{sequence_id}/add_contact_ids` to enroll contacts into a pre-built Apollo sequence.

**Boundary:** Handles rate limiting, retries with exponential backoff, and credential management (master API key held server-side only — never sent to the client). Does not parse or transform data beyond what the orchestrator needs.

**Key API constraint:** The people search endpoint does not return email addresses. A separate enrichment call is needed before enrollment. Enrichment adds to Apollo credit consumption — factor this into per-campaign cost estimates.

**Communicates with:** Campaign Orchestrator (caller), Apollo.io API (external).

---

### Component 4: Personalization Engine

**Responsibility:** Takes a list of contact records (name, title, company, industry) and generates one custom opening line per contact using an LLM. Assembles the full email by prepending the opening line to the path-specific template body.

**Boundary:** Stateless — given contact data in, returns personalized opening line out. Does not store anything. The orchestrator handles persistence of the output.

**Implementation:** Single LLM call per contact (not a multi-agent pipeline for v1 — the task is scoped enough that one well-engineered prompt handles it). Batch in parallel with concurrency limit to avoid rate-limit errors on the LLM provider.

**Communicates with:** Campaign Orchestrator (caller), LLM API (external — OpenAI or Anthropic).

---

### Component 5: Review Queue

**Responsibility:** When a campaign runs in "queue for review" mode, the assembled emails (contact + personalized opening + template body) are stored here with status `pending_review`. Exposes a UI for a teammate to read each draft, edit if needed, approve or reject, and trigger enrollment in bulk.

**Boundary:** This is a database table + a server-side action set (approve, reject, edit). Not a separate service — just a state machine on top of the Campaign Store.

**Communicates with:** Campaign Store / DB (read/write), Apollo Client (triggers enrollment when approved).

---

### Component 6: Campaign Store / Database

**Responsibility:** Persistent state for campaigns, contacts-within-campaigns, generated emails, enrollment status, and review queue state.

**Schema shape (logical):**
- `campaigns` — config, path type, mode, timestamps, status
- `campaign_contacts` — FK to campaign, Apollo contact ID, raw contact data, generated opening line, assembled email, enrollment status, review status
- `email_events` — snapshots of Apollo engagement stats (opens, replies) pulled on a schedule

**Boundary:** Postgres (or equivalent relational DB). Not a queue — the job queue is a separate concern (see below).

---

### Component 7: Dashboard

**Responsibility:** Display per-campaign open rates and reply rates. Show campaign status (running, complete, queued, failed). Show pending review queue count.

**Boundary:** Read-only view over the Campaign Store. Engagement stats are populated by a scheduled polling job, not pushed by Apollo webhooks (see Apollo Integration Points).

**Communicates with:** Campaign Store / DB (read), no direct Apollo calls.

---

### Component 8: Background Job Runner

**Responsibility:** Executes campaign orchestrator jobs asynchronously, outside the HTTP request cycle. Enables retries, avoids serverless timeouts.

**Recommended implementation for v1:** pg-boss (Postgres-backed job queue) co-located with the Next.js app and a long-running worker process. Avoids adding a separate infrastructure dependency (Redis, RabbitMQ) while still giving durable job persistence and retry semantics.

**Communicates with:** Campaign Store / DB (job table), Campaign Orchestrator (executes it).

---

## Data Flow

### Campaign Run (Auto-Send Mode)

```
User (browser)
  → [1] Selects path + toggles auto-send
  → [2] POST /api/campaigns/start
      → Server validates, writes campaign row (status: queued)
      → Enqueues job ID to Background Job Runner
      → Returns 200 immediately with campaign ID

Background Job Runner picks up job
  → [3] Campaign Orchestrator begins
      → Apollo Client: search contacts with path filter preset
          ← Returns list of people (no emails yet)
      → Apollo Client: bulk enrich people
          ← Returns full profiles with verified emails
      → Personalization Engine: LLM call per contact (parallel, rate-limited)
          ← Returns opening line per contact
      → Assembles full emails, writes to campaign_contacts (status: ready)
      → Apollo Client: enroll contact_ids in pre-built Apollo sequence
          ← Apollo confirms enrollment
      → Writes campaign (status: complete, enrolled_at: now)

Dashboard
  → [4] Polls /api/campaigns/{id} — reads campaign status from DB
  → [5] Scheduled job (e.g., every 6 hours) calls Apollo stats endpoint
          → Writes open/reply counts to email_events
  → Dashboard reads email_events to display rates
```

### Campaign Run (Queue-for-Review Mode)

Steps 1–3 are identical through email assembly. Instead of enrolling immediately:

```
Campaign Orchestrator
  → Writes assembled emails to campaign_contacts (status: pending_review)
  → Writes campaign (status: awaiting_review)

Teammate (browser)
  → Opens Review Queue UI
  → Reads pending drafts from Campaign Store
  → Edits opening line if needed (writes back to campaign_contacts)
  → Clicks "Approve All" or approves individually
  → Server action: Apollo Client enrolls approved contact_ids in sequence
  → campaign_contacts status → enrolled
```

### Stats Polling Flow

Apollo does not offer real-time push webhooks for sequence engagement events (open, reply) in their standard API. Their `/api/v1/emailer_messages/search` endpoint (Search for Outreach Emails) supports filtering by status (`opened`, `replied`, etc.) and returns per-email engagement state. The strategy:

```
Cron job (every 6 hours, or on dashboard load with cache TTL)
  → Apollo Client: GET /emailer_messages/search filtered by campaign's contact_ids
  → Parse opened/replied flags per contact
  → Upsert into email_events table
  → Dashboard reads from email_events (never hits Apollo in real time)
```

This polling approach is the correct architecture for this scale. Apollo's webhook `poll` endpoint is for enrichment callbacks only — it is not a general-purpose event stream for sequence engagement.

---

## Apollo.io Integration Points

| Integration | Apollo Endpoint | Direction | Notes |
|---|---|---|---|
| Contact discovery | `POST /api/v1/mixed_people/api_search` | Outbound | Returns obfuscated last names; no emails |
| Contact enrichment | `POST /api/v1/people/bulk_match` or People Enrichment | Outbound | Consumes Apollo credits; required before enrollment |
| Sequence enrollment | `POST /api/v1/emailer_campaigns/{id}/add_contact_ids` | Outbound | Requires master API key; no credit cost |
| Sequence search (get sequence IDs) | `POST /api/v1/emailer_campaigns/search` | Outbound | Used at setup time to map path → sequence ID |
| Email stats polling | `POST /api/v1/emailer_messages/search` | Outbound | Filter by status: opened, replied, etc. |
| Webhooks | Poll Webhook Result endpoint | — | This is for enrichment callbacks only — not usable for sequence engagement events |

**Apollo API key:** Must be a master API key for enrollment and search. Store server-side only. Never expose to browser.

**Apollo sequence setup:** Pre-build one sequence per outreach path in the Apollo UI before any code runs. The app references sequences by ID (stored in config). This avoids needing to programmatically create sequences via API.

**Credit consumption:** People enrichment costs Apollo credits per contact. The system should cap the number of contacts discovered per campaign run to control credit burn. A default cap of 25–50 contacts per run is a reasonable starting constraint.

**Stats API limitation (MEDIUM confidence):** Apollo returns all-time aggregate stats on sequences. For per-campaign open/reply rates, the correct approach is to query `emailer_messages/search` filtered to the specific contacts in that campaign run and compute rates locally. There is no API endpoint that returns "open rate for this campaign run as a percentage" directly.

---

## Suggested Build Order

Build in dependency order — each phase unblocks the next.

### Phase 1: Data layer + Apollo contact discovery
Build the Campaign Store schema and Apollo Client (contact search + enrichment only). Verify you can query Apollo, get contacts back, and persist them. This is the foundation everything else reads from.

**Why first:** All downstream components (personalization, enrollment, dashboard) depend on having contact data. Validates Apollo API access and credit model before building anything on top.

### Phase 2: Personalization Engine
Build the LLM call + prompt + output parsing. Test with contacts from Phase 1. Does not require UI — can be exercised directly in a script or test.

**Why second:** Stateless and independent. Can be built and validated in isolation before wiring into the orchestrator.

### Phase 3: Campaign Orchestrator + Background Job Runner
Wire Phase 1 and Phase 2 together into an orchestrated pipeline. Add the job queue. Build sequence enrollment call to Apollo. Run end-to-end: path config → contacts → opening lines → enrollment → Apollo sequence.

**Why third:** Orchestrator is the most complex piece. Having validated inputs (Phase 1) and personalization (Phase 2) separately makes this integration step lower-risk.

### Phase 4: Path Selection UI + basic Campaign status page
Build the form that produces a CampaignConfig and triggers a campaign run. Show campaign status (running / complete / failed). No review queue yet — auto-send only.

**Why fourth:** UI is the thinnest layer over a working backend. Build UI last within each functional area so you are not iterating UI while backend contracts are still changing.

### Phase 5: Review Queue (queue-for-review mode)
Add the pending_review state to the campaign run. Build the review UI (list of draft emails, edit, approve). Wire approval to enrollment.

**Why fifth:** This is additive — the auto-send path is complete before this. The review queue is strictly a UI + state machine addition on top of existing enrollment logic.

### Phase 6: Dashboard with stats polling
Build the polling cron, email_events persistence, and the dashboard UI reading open/reply rates.

**Why last:** Stats are only meaningful once campaigns are actually running and sending. Build this when there is real data to display.

---

## Architecture Decision: Simple Web App, Not Event-Driven Queue

**Verdict:** Simple Next.js web app with a Postgres-backed background job queue (pg-boss). Not a full event-driven architecture.

**Rationale:**
- Event-driven (Kafka, SQS, etc.) adds significant operational overhead — separate broker, consumer management, dead-letter queues. This is a single-team student project where deployment simplicity matters.
- The volume is low: campaigns run occasionally (not thousands/second). No fan-out, no inter-service messaging required.
- The only async requirement is: "don't block the HTTP response while we call Apollo and an LLM." A simple background job queue handles this cleanly.
- pg-boss runs inside the same Postgres database already needed for the Campaign Store, so there is no new infrastructure dependency.

**What this means concretely:** The Next.js API route that starts a campaign writes a job to a pg-boss queue table and returns 200 immediately. A Node.js worker process (co-deployed, always-on) polls the queue and runs the Campaign Orchestrator. The frontend polls `/api/campaigns/{id}` to show status.

---

## Open Questions

1. **Apollo enrichment endpoint choice:** `people/bulk_match` vs. `people/enrichment` — need to validate which accepts the people IDs returned by the search endpoint and what the credit cost difference is. This affects per-campaign cost modeling.

2. **Apollo stats API completeness:** The `emailer_messages/search` endpoint returns per-email open/reply flags, but the response schema is not fully documented. Needs a live API test to confirm what fields are actually returned for opened and replied status. There may be a 50,000-record display cap that is irrelevant at this scale but should be confirmed.

3. **Apollo sequence ID config strategy:** How are the three path-to-sequence-ID mappings stored? Options: hardcoded env vars, a config table in DB, or read from Apollo at startup via sequence search API. Env vars are simplest for v1 but require a redeploy to change a sequence. A config table is more flexible. Recommend env vars for v1, config table later.

4. **LLM provider choice:** Not decided. OpenAI GPT-4o-mini and Anthropic Claude Haiku are both reasonable choices for a single-turn "write one personalized opening line" task. Cost is negligible at this volume. The choice affects the Personalization Engine implementation but nothing else. Decide at Phase 2 build time.

5. **pg-boss vs. alternative:** pg-boss is the recommended choice but assumes a long-running Node process is viable in the deployment environment. If deploying to a purely serverless platform (Vercel), a different queue backend (Vercel Cron + Upstash QStash, or Railway with a persistent worker) is needed. Deployment environment should be decided before Phase 3.

---

## Sources

- [Apollo People API Search — docs.apollo.io](https://docs.apollo.io/reference/people-api-search)
- [Apollo Find People Using Filters — docs.apollo.io](https://docs.apollo.io/docs/find-people-using-filters)
- [Apollo Add Contacts to Sequence — docs.apollo.io](https://docs.apollo.io/reference/add-contacts-to-sequence)
- [Apollo Search for Outreach Emails — docs.apollo.io](https://docs.apollo.io/reference/search-for-outreach-emails)
- [Apollo Poll Webhook Result — docs.apollo.io](https://docs.apollo.io/reference/poll-webhook-result)
- [Apollo Email Tracking Overview — knowledge.apollo.io](https://knowledge.apollo.io/hc/en-us/articles/34263074322701-Email-Tracking-Overview)
- [Apollo.io API returns all-time stats on sequences — gtmworks.ai](https://www.gtmworks.ai/blog/automated-apollo-io-email-reports)
- [Architecting Robust AI-Powered Email Automation Systems — dev.to](https://dev.to/lifeisverygood/architecting-robust-ai-powered-email-automation-systems-3e2h)
- [Multi-Agent Workflow for Email Automation — smartlead.ai](https://www.smartlead.ai/blog/multi-agent-workflow-email-automations)
- [Next.js Background Jobs & PostgreSQL: Production in 2026 — render.com](https://render.com/articles/nextjs-background-jobs-postgresql-production)
- [Human-in-the-Loop AI Agents: Implementation Patterns — buildmvpfast.com](https://www.buildmvpfast.com/blog/human-in-the-loop-ai-agents-implementation-patterns-2026)
- [Request-Driven vs Event-Driven Architecture — querio.ai](https://querio.ai/blog/request-driven-vs-event-driven-architecture)
