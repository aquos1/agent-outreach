# Research Summary: Outreach Agent

**Project:** Outreach Agent
**Domain:** AI-powered B2B email outreach automation for non-technical users via Apollo.io
**Researched:** 2026-07-19
**Confidence:** HIGH

---

## Recommended Stack

- **Python 3.12 + Streamlit 1.45+** — single-process app and UI; deploys free to Streamlit Community Cloud directly from GitHub; zero JavaScript; non-technical teammates can use a bookmarked URL with no engineering support
- **requests 2.32+ (or httpx)** — direct Apollo REST calls; no Apollo SDK exists on PyPI; plain HTTP is sufficient for the synchronous pipeline
- **SQLite (stdlib sqlite3)** — pipeline state tracking with a 7-state status enum per prospect; zero infrastructure; sufficient for under 500 prospects per week
- **Anthropic SDK (anthropic>=0.117.0) + claude-haiku-4-5-20251001** — one LLM call per contact for a personalized opening line; ~$0.04 per 50-contact campaign run; direct SDK calls only, no LangChain or agent frameworks
- **Streamlit Community Cloud** — free hosting; secrets managed via platform console (never in the repo); cold start under 5 seconds

---

## Table Stakes Features

Features that must be in v1 or the product fails:

1. **Guided path selection** — three cards (club sponsorship / productthon sponsorship / client sourcing), not a blank config form; non-technical users cannot diagnose a misconfigured search
2. **Automated contact discovery** — Apollo People Search with pre-tuned filters per path; zero user filter configuration; the agent finds contacts, the user does not
3. **AI-generated opening line per contact** — one personalized sentence per contact seeded with Apollo's enriched title, company, and industry data; generic emails get 2x lower reply rates
4. **Pre-send review queue** — inline approve / edit / skip per contact before enrollment; not a CSV export flow
5. **Sequence enrollment** — Apollo API call to enroll approved contacts into a pre-built Apollo sequence per path
6. **Auto-pause on reply** — native Apollo behavior; no custom code required; missing this burns relationships
7. **Per-campaign send/review toggle** — "send now" vs. "queue for review" set at campaign launch
8. **Campaign analytics** — open rate and reply rate per campaign; reply rate is the primary trust metric (open rate is inflated by pixel prefetch)

---

## Architecture in One Paragraph

The system is a deterministic linear pipeline running inside a single Streamlit session. Path Selection produces a `CampaignConfig` dict from the user's choice and toggle. The Campaign Orchestrator sequences four Apollo REST calls — People Search (free, no emails), People Bulk Match enrichment (1 credit/person, returns email), Bulk Create Contacts (`run_dedupe: true` required), and Add Contact IDs to Sequence (requires pre-built sequence in Apollo UI, referenced by hardcoded sequence_id per path) — with exponential-backoff retry on 429s and explicit error surfacing on 401/422. Between enrichment and enrollment, the Personalization Engine makes one Claude Haiku call per contact using only fields explicitly present in Apollo's response (title, company name, industry, seniority) to generate an opening line and assembles it with the path's template body. In "queue for review" mode the assembled drafts are written to SQLite with `pending_review` status and the Review Queue UI (approve / edit / skip) triggers enrollment; in "auto-send" mode enrollment fires immediately after assembly. The Dashboard reads from SQLite and polls Apollo's `emailer_messages/search` endpoint every 15 minutes for open/reply stats — Apollo has no push webhooks for sequence engagement events. The Apollo master API key is stored in `st.secrets` and never reaches the browser.

---

## Top Pitfalls to Avoid

1. **Sequence enrollment silent failures** — Apollo returns 200 OK even when contacts are skipped (unverified email, already in a sequence, DNC). After every enrollment call, poll each contact's `in_active_campaign` status and surface per-contact results (Enrolled / Skipped with reason / Pending). A bulk "N contacts added" count is insufficient and will mask zero actual sends.

2. **Credit burn without user awareness** — Search is free; email enrichment costs 1 credit per person. A non-technical user can exhaust monthly credits in one session. Show remaining credit balance before any campaign launches. Show a pre-enrichment cost estimate. Only enrich contacts with `has_email: true` — roughly 56% of search results will yield a usable email; wasting credits on the other 44% is avoidable with a single field filter.

3. **Mailbox not warmed up / deliverability collapse** — Since May 2025, Gmail/Yahoo/Microsoft enforce SPF, DKIM, and DMARC as hard requirements for bulk senders. A new mailbox sending cold volume immediately triggers spam classification. Domain reputation damage is not easily reversed. Block campaign launch without a passing mailbox health check (SPF + DKIM + DMARC + mailbox age > 14 days + warmup completed). Use a secondary outreach domain — never the primary `.edu` address.

4. **LLM hallucinations in personalized opening lines** — Apollo's enrichment data is 65-70% accurate and often stale. The LLM fills gaps with plausible-sounding fabrications. Restrict the prompt strictly to fields present in the input. Flag any proper noun in the generated line not found in the input data. Always surface generated lines in the review step — never auto-send without a human seeing at least a sample.

5. **Duplicate outreach across campaigns** — Club sponsorship and productthon sponsorship target overlapping personas. Apollo will silently skip a contact already active in the same sequence, but finished contacts and contacts enrolled in a different path's sequence are not protected. Maintain a global contacted registry (keyed on Apollo contact ID and company domain) in SQLite, checked before enrichment so credits are not wasted on contacts that will be excluded.

---

## Key Apollo.io Constraints

Non-obvious API facts that affect every phase:

- **Search returns no emails** — `POST /mixed_people/api_search` is free and returns names, titles, and companies but never email addresses. A separate `POST /people/bulk_match` enrichment call (max 10 per request) is required to get emails, and it costs 1 credit per person on a hit. These are two different API calls in sequence, not one.
- **Contact must exist before enrollment** — `POST /emailer_campaigns/{id}/add_contact_ids` only accepts contacts already in Apollo's contact database. The enrichment step alone is not sufficient; a `POST /contacts/bulk_create` call (with `run_dedupe: true`) must precede every enrollment call.
- **Sequences must be pre-built in the Apollo UI** — The API cannot create sequences programmatically. All three outreach paths require a manually configured sequence (cadence, email templates, follow-up steps) created in the Apollo web UI before the app can function. These sequence IDs are stored as constants in the path config.
- **Master API key required for sequence enrollment** — A scoped key returns 403 on enrollment calls. The master key grants full account access and must be stored server-side only — never in client code or frontend environment variables.
- **Enrollment is not confirmed by 200 OK** — Apollo silently skips ineligible contacts (DNC, unverified email, already in another active sequence) and still returns 200. Post-enrollment polling of contact status is required to know what actually enrolled.
- **No push webhooks for engagement events** — Apollo does not push open/reply/bounce events to external systems. Engagement data requires polling `emailer_messages/search` on a schedule. Dashboard metrics will always lag by the polling interval.
- **Rolling 24-hour sending window** — Apollo's daily send limit resets 24 hours from the first send of a sequence, not at midnight. A sequence started at 3pm uses its quota until 3pm the next day. Surface the reset time in the dashboard to prevent user confusion.
- **`run_dedupe` defaults to false** — Creating contacts without `run_dedupe: true` silently creates duplicate records for the same email address.

---

## Build Order Recommendation

Dependencies force this order — each phase unblocks the next:

1. **Pre-launch setup** — Apollo API key verification (`GET /auth/health`), SQLite schema creation, Streamlit app skeleton with `st.secrets`, mailbox SPF/DKIM/DMARC health check, three Apollo sequences pre-built in the UI. Nothing can run without this. Mailbox deliverability damage is irreversible — solve it first.

2. **Contact discovery** — Apollo People Search with per-path filter presets, `has_email` pre-filtering, bulk enrichment with credit cost estimation and hard cap (default 50 contacts), SQLite persistence of discovered contacts. All downstream phases need contact records with verified emails.

3. **AI personalization engine** — Claude Haiku integration, per-contact opening line generation with input-constrained prompt, hallucination detection (proper noun check), sparse-data fallback, full draft assembly (opening line + template body). Build and test in isolation against Phase 2 contacts before wiring into orchestration.

4. **Campaign orchestrator + sequence enrollment** — Wire Phase 2 and Phase 3 into an end-to-end pipeline: search → enrich → create contact (`run_dedupe: true`) → enroll. Add post-enrollment confirmation polling, per-contact status tracking, and exponential-backoff retry. End-to-end auto-send campaign must work completely before the UI is layered on.

5. **Path selection UI + campaign launch flow** — Streamlit pages for path selection, campaign toggle, pre-launch checklist (credit balance, deduplication warning, mailbox status), campaign status view (running / complete / failed). Build UI after backend contracts are stable.

6. **Review queue** — `pending_review` status in SQLite, review queue UI (approve / edit / skip per contact), bulk approve action, enrollment triggered from UI. Strictly additive on Phase 4 — no new Apollo calls, no new tables.

7. **Dashboard and analytics** — Background polling job (15-minute interval) for `emailer_messages/search`, `email_events` table in SQLite, open rate + reply rate display per campaign, freshness timestamp, bounce detection. Build last — requires real campaign data with real enrollment IDs to validate.

---

## Open Questions Requiring Pre-Build Answers

Decisions the team must make before coding starts:

1. **Which Apollo enrichment endpoint?** `people/bulk_match` vs. `people/enrichment` — both can return emails but accept different inputs and may have different credit costs. Confirm which accepts the person IDs returned by the search endpoint against the team's live Apollo account before writing enrichment code.

2. **What Apollo plan tier does the team have?** Rate limits and analytics endpoint availability vary by plan. Check the team's Apollo account `/api/v1/usage` endpoint and plan settings before assuming the documented rate limits apply.

3. **Is the `emailer_campaigns/{id}/stats` endpoint accessible on the team's plan?** Some Apollo analytics endpoints are gated behind higher plan tiers. If unavailable, Phase 7 must fall back entirely to per-contact `emailer_messages/search` polling. Validate before designing the analytics pipeline.

4. **Secondary outreach domain setup** — The team needs a dedicated secondary domain for cold outreach (not the `.edu` address). Has this domain been registered? Has warmup started? If not, this blocks Phase 1 and every phase after it.

5. **Sequence ID configuration strategy** — How are the three path-to-sequence-ID mappings stored? Environment variables (simplest, requires redeploy to change) vs. a config table in SQLite (more flexible). Recommend env vars for v1, but the team must agree on this before Phase 1 because it affects secrets setup.

6. **Who approves campaigns in "queue for review" mode?** The review queue UI needs to know which teammate's session can approve. For v1 with Streamlit Community Cloud, access can be restricted to specific GitHub accounts — confirm the team's access policy before building auth assumptions into the UI.

