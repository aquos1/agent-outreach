# Phase 2: Contact Discovery - Context

**Gathered:** 2026-07-22
**Status:** Ready for planning

<domain>
## Phase Boundary

The teammate-facing discovery flow: pick a path, enter free-text company type + target role, run a free Apollo search with dedup exclusion, review the estimated credit cost, spend credits to enrich (retrieve verified emails), and land on a read-only list of enriched contacts ready for Phase 3 personalization. This phase delivers no personalization, no sending, and no per-contact selection UI (that's Phase 3/4) — its only job is to turn "path + free text" into a clean, deduped, emailable contact batch the teammate can trust.

</domain>

<decisions>
## Implementation Decisions

### Path → Apollo filter translation
- **D-01:** All 3 paths use identical search logic — free text (company type + role) is the ONLY thing that drives Apollo search filters. Path selection changes ONLY the downstream Apollo sequence ID and email template, never the search filters themselves. No per-path baked-in filters (company size, location, etc.).
- **D-02:** Free-text "target role" maps directly to Apollo's `person_titles` keyword field (literal title-keyword search) — not an AI-inferred seniority tag.
- **D-03:** Free-text "company type / industry" maps directly to Apollo's organization keyword-tag field (literal keyword search) — not a structured industry-taxonomy lookup.
- **D-04:** Free text is passed straight through to Apollo with no AI normalization step. Rationale discussed explicitly: Apollo search is 0 credits regardless of query quality, the 50-contact cap bounds spend either way, and DISC-04's cost-preview gate already prevents blind commitment — so normalization would only be a match-*relevance* lever, not a cost-savings one. Revisit only if relevance turns out to be a real problem once the app is in use.

### Credit cost gate (DISC-04)
- **D-05 — IMPORTANT, changes DISC-04's literal wording:** Apollo has **no API endpoint that returns credit balance** (confirmed via a live authenticated call to `usage_stats/api_usage_stats` during Phase 1's checkpoint — that endpoint returns only per-endpoint rate-limit consumption; Apollo's own docs confirm balance is dashboard-only, Settings → Billing and credits). DISC-04 must be implemented as a **cost estimate**, not a balance display: "This will use up to N credits" where N = `min(matched-and-deduped candidates, 50)`, computed entirely locally with no Apollo call needed. Do not attempt to show remaining balance. If the teammate is actually out of credits, that surfaces naturally via Apollo's own API error at enrichment time, using the existing Phase 1 error-banner pattern (401/403/429 → plain-language banner, no traceback).
- **D-06:** Two distinct stages, not one combined action: (1) "Find Contacts" button — free, runs search + `has_email` pre-filter (DISC-02) + dedup exclusion (DEDUP-02), shows matched count and the cost estimate from D-05; (2) a separate "Enrich & Continue" button that actually spends credits. This is what makes DISC-04's "see cost before committing" literally true.

### Search-to-enrichment funnel
- **D-07:** At the "Find Contacts" (pre-enrichment) stage, show **count + cost estimate only** — no contact table yet. Apollo's search response doesn't include real emails (only a `has_email` indicator), so a Name/Company/Title/Email table would have to fake or omit the Email column. The real table only appears after enrichment succeeds.
- **D-08:** When more than 50 eligible (post-dedup, has-email) candidates match, take Apollo's own result order for the first 50 — no additional ranking/tie-break logic. Trust Apollo's relevance ordering.
- **D-09 (SEND-02, already locked pre-discussion):** Hardcoded cap of 50 contacts per campaign for v1 — not user-configurable.

### Results list display
- **D-10:** The post-enrichment contact list is **read-only** — the full enriched batch proceeds automatically to Phase 3 personalization. No per-contact removal/deselection in Phase 2; that capability is deferred to the Phase 4 bulk-approve review queue (QUEUE-03), consistent with REVIEW-01 being explicitly v2 scope.
- **D-11:** Table columns: Name, Company, Title, Email — the essentials for a non-technical teammate to sanity-check relevance. No industry/company-size columns (kept simple).
- **D-12:** Empty state (zero contacts after search + pre-filter + dedup): plain message — "No new contacts found — try different search terms" — with the free-text inputs still editable in place so the teammate can immediately retry. No credits were spent getting to this state (search + dedup filtering are both free), so retrying costs nothing.
- **D-13 (already settled by CLAUDE.md, not re-discussed):** Table renders via `st.dataframe`, per the project's existing tech-stack doc ("st.dataframe for search results").

### Claude's Discretion
None — all four discussed areas reached explicit user decisions; no "you decide" items remain open.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Apollo API integration
- `apollo.MD` — Apollo API reference index; search/enrichment endpoint behavior, error codes
- `spec.MD` §2–3 — search → enrichment pipeline order, `has_email` pre-filter pattern (DISC-02)
- `CLAUDE.md` "Key API Notes (Apollo.io)" — confirms `/mixed_people/api_search` is 0 credits, `/people/bulk_match` is 1 credit/person when email found, max 10 people per call, rate limits (100 req/min search, 10 req/min enrichment)

### Prior phase decisions this phase builds on
- `.planning/phases/01-foundation/01-CONTEXT.md` — D-03: Apollo credit balance is informational-only on the health page; this phase's DISC-04 cost-preview gate is "the real spending gate" per that decision
- `db/schema.py` — `prospect` table columns (`apollo_person_id`, `apollo_contact_id`, `company_domain`, `status` enum) and the `contacted_registry` view (free-email-domain exclusion already implemented) that DEDUP-02 must query against
- `.planning/phases/01-foundation/01-04-SUMMARY.md` — confirms live-verified finding that Apollo exposes no credit-balance API endpoint (source of D-05 above)

### Project scope
- `.planning/ROADMAP.md` (Phase 2 entry) — full success criteria for this phase
- `.planning/REQUIREMENTS.md` (PATH-01/02/03, DISC-01/02/03/04, DEDUP-02, and v2 SEND-02 for the locked 50-contact cap)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apollo/client.py` — existing `check_apollo_health` pattern (typed `(bool, str)` tuple, never raises, banner-over-traceback) should extend to new search/enrichment client functions in this phase for consistency
- `db/schema.py` — `contacted_registry` view already computes `dedupable_domain` (NULL for free-email domains) — DEDUP-02's exclusion query should read from this view directly rather than reimplementing free-domain logic
- `pages/health_page.py` — establishes the `st.status`/`st.error`/`st.warning` pattern for surfacing Apollo errors in plain language; the new discovery page should follow the same error-handling conventions

### Established Patterns
- Typed `(status, message)` tuples for every external call, never raising — must extend to the new search and bulk-enrichment client functions
- API keys read via `st.secrets`, never logged (T-04-02 from Phase 1's threat model) — applies identically here

### Integration Points
- New discovery page registers via `app.py`'s `st.navigation` extension point (explicitly left as a commented placeholder in Phase 1's `app.py`)
- Enriched contacts get written into the `prospect` table (`status` progresses `found` → `selected` → `enriched`) for Phase 3 to pick up

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or exact wording given beyond the decisions above. Concrete expectations: two-button flow (Find Contacts → Enrich & Continue), st.dataframe table with Name/Company/Title/Email columns, plain-language empty state with search inputs still editable.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Per-contact removal in the discovery list, and AI-driven query normalization, were both considered and explicitly deferred as future possibilities rather than new capabilities — see D-04 and D-10 above.)

</deferred>

---

*Phase: 2-Contact Discovery*
*Context gathered: 2026-07-22*
