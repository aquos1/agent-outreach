# Product Space — Club Sponsorship Outreach Agent
### Apollo API Integration Spec (v1)

---

## 1. Scope

v1 covers **one playbook: Club Sponsorship outreach.** Email-only (no mobile/phone enrichment). Built as a Python/Streamlit internal tool for non-technical PS members. No MCP, no agentic tool-calling — deterministic pipeline, direct REST calls.

Pipeline: **Search → Human select → Enrich → Convert to Contact → Draft (Claude) → Human approve → Add to Sequence.**

---

## 2. Auth

- **Master API key** required (most endpoints below need it — sequences, contacts, and bulk operations all 403 without one).
- Store in `st.secrets["APOLLO_API_KEY"]`, never client-side, never committed.
- Header: `x-api-key: <key>` (or `Authorization: Bearer <token>` if using OAuth — not needed for v1, that's partner-only).
- **Test endpoint on startup:** `GET /api/v1/auth/health` — call this once when the Streamlit app boots; surface a clear "Apollo connection failed" banner if it fails, rather than letting downstream calls fail cryptically.

---

## 3. Endpoints used (in pipeline order)

### 3.1 Search — `POST /api/v1/mixed_people/api_search`
- **Cost:** free, no credits consumed.
- **Purpose:** find candidate people matching club-sponsorship-relevant filters.
- **Key params for this playbook:**
  ```json
  {
    "person_titles": ["Community Manager", "Head of Partnerships", "Developer Relations", "Marketing Manager"],
    "q_organization_keyword_tags": ["developer tools", "startup", "SaaS"],
    "organization_num_employees_ranges": ["11,50", "51,200"],
    "person_locations": ["Washington, US", "Oregon, US", "California, US"],
    "per_page": 25,
    "page": 1
  }
  ```
- **Returns:** name, title, company, LinkedIn — **no email/phone.**
- **Hard limit:** 50,000 records total (100/page, 500 pages max) — irrelevant at your volume, just noting the ceiling.
- These filters are the only thing that changes per-campaign; keep them in a config dict, not hardcoded.

### 3.2 Human review gate (not an API call)
- Render search results as a table with checkboxes in Streamlit.
- **Nothing past this point runs without an explicit human selection.** This is the credit-control and quality-control checkpoint.

### 3.3 Enrich — `POST /api/v1/people/bulk_match`
- **Cost:** 1 credit per person if email is found and returned; 0 if no match. (Don't request `reveal_phone_number` — that's the +8 credit / mobile path, and out of scope for v1.)
- **Batch size:** up to 10 people per call — chunk your selected list into groups of 10.
- **Input:** pass the `id` (or name + org domain) from the search result for each person in the `details[]` array.
- **Returns:** enriched email address, synchronously.

### 3.4 Convert to Contact — `POST /api/v1/contacts`
- **Why this step matters:** only Apollo *contacts* (not raw enriched people) can be added to a sequence. This also avoids re-consuming credits if you ever touch this person again — once they're a contact, their data is permanently on your account.
- **Body:**
  ```json
  {
    "first_name": "...",
    "last_name": "...",
    "email": "...",
    "organization_name": "...",
    "title": "...",
    "label_names": ["club-sponsorship-outreach"]
  }
  ```
- Use `label_names` to tag every contact created by this playbook — makes it trivial to filter/report later, and to distinguish from producthon/client-engagement contacts once those exist.
- Set `run_dedupe: true` — dedup is **off by default**, and without it Apollo will happily create duplicate contacts for the same person across campaigns.
- **Rate limit:** 600 calls/hour on this endpoint. Irrelevant at 500/week (~15/day), just don't loop-call it without the batching step above.
- For batches, use `POST /api/v1/contacts/bulk_create` instead (up to 100 per call) — cleaner than looping single creates.

### 3.5 Draft generation (Claude API, not Apollo — see note below)

### 3.6 Human approval gate (not an API call)
- Editable text area per contact showing the drafted email. Explicit "Approve" click required before step 3.7. No auto-send, ever, for this use case.

### 3.7 Add to Sequence — `POST /api/v1/emailer_campaigns/{sequence_id}/add_contact_ids`
- **Sequence itself is pre-built in the Apollo UI** — you (or whoever owns PS's Apollo seat) create a "Club Sponsorship Outreach" sequence once, manually, with its cadence steps.
- To find the `sequence_id` programmatically: `POST /api/v1/emailer_campaigns/search`.
- **Required params:**
  - `sequence_id` (path)
  - `emailer_campaign_id` (query — same value as `sequence_id`, both required, must match)
  - `send_email_from_email_account_id` (query — which connected mailbox sends the emails)
  - `contact_ids[]` (query — the contacts from step 3.4)
- **Rate limit:** 600 calls/hour.
- **Common failure modes (422):** missing `emailer_campaign_id`, missing `send_email_from_email_account_id`, inactive mailbox, contact already active/finished in another campaign (there are `sequence_active_in_other_campaigns` / `sequence_finished_in_other_campaigns` override flags if you want to force re-enrollment).

---

## 4. Where Claude fits (not Apollo API)

Between 3.4 and 3.6: for each enriched contact, call the Claude API with a fixed prompt template + that contact's data (name, title, company) to draft a first-touch email. This is a separate API call, not part of the Apollo flow — sequenced in your Python pipeline as its own step. Output goes straight into the human-editable review step (3.6); nothing from this step touches Apollo until approved.

---

## 5. State tracking (your own DB, not Apollo)

Simple table (SQLite or Google Sheet), one row per prospect, columns:

```
name | company | apollo_person_id | apollo_contact_id | status | sequence_id | created_at
```

`status` enum: `found → selected → enriched → contact_created → drafted → approved → sequenced`

This lets PS members see pipeline state in your own UI without jumping into Apollo's dashboard.

---

## 6. Error handling

- `403` → missing/invalid master key (auth setup issue, not per-request).
- `422` → validation error, almost always a missing required param — surface the response body's `message` field directly in the Streamlit UI rather than a generic failure.
- `429` → rate limit hit; irrelevant at this volume but wrap calls in a retry-with-backoff regardless, it's cheap insurance.
- Always check `mixed_people/api_search` and `bulk_match` responses for empty/partial matches — not every search hit will enrich successfully, and not every enrichment will find an email. Surface "no email found" rows distinctly rather than silently dropping them.

---

## 7. Explicit non-goals for v1

- No mobile/phone enrichment.
- No MCP / conversational agent layer.
- No auto-send — human approval is mandatory before every sequence enrollment.
- No producthon or client-engagement playbooks yet — but the config-dict structure in 3.1 is built so those are just new filter/prompt configs, not new code paths.