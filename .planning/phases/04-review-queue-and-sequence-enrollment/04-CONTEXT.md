# Phase 4: Review Queue and Sequence Enrollment - Context

**Gathered:** 2026-09-17
**Status:** Ready for planning

<domain>
## Phase Boundary

A new Review Queue page where a teammate sees every drafted email across all three paths, can edit the shared per-path template (applying to every drafted contact on that path at once), selects/deselects individual contacts, and approves in bulk — which creates Apollo contacts and enrolls them into the correct pre-built Apollo sequence, with real per-contact confirmation (not just an HTTP 200). This phase delivers no per-contact draft editing (that's REVIEW-01, v2) and no send analytics (that's Phase 5) — its job ends at "approved contacts are verifiably enrolled in Apollo and the dedup registry is updated."

</domain>

<decisions>
## Implementation Decisions

### Sequence ID resolution
- **D-01:** The 3 Apollo sequence IDs (one per path) are hardcoded in `.streamlit/secrets.toml`, the same permanent config file already holding `APOLLO_API_KEY`, `ANTHROPIC_API_KEY`, and `SENDING_DOMAIN` — not looked up dynamically via `emailer_campaigns/search`. Rationale: zero live API dependency at enrollment time, and it won't silently break if a sequence gets renamed in Apollo.
- **D-02:** Secrets key naming: `APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP`, `APOLLO_SEQUENCE_ID_PRODUCTTHON`, `APOLLO_SEQUENCE_ID_CLIENT_SOURCING` — SCREAMING_SNAKE_CASE matching the existing secrets convention.
- **D-13 (added post-research):** `add_contact_ids` requires a `send_email_from_email_account_id` query param that nothing in the project previously resolved — 04-RESEARCH.md flagged this as a genuine gap, not a research ambiguity. Resolved the same way as D-01: hardcode a single new secret, `APOLLO_SENDING_EMAIL_ACCOUNT_ID`, looked up once in Apollo (one mailbox/domain shared across all 3 paths, matching the existing single `SENDING_DOMAIN` secret) rather than resolved live via `GET /email_accounts` at enrollment time.

### Bulk template editor (scope addition — see Folded Todos below)
- **D-03:** The template editor lives on the new Review Queue page, above the list of drafts — not on the existing Discovery page's "Email Drafts" section (that stays Phase 3's read-only preview).
- **D-04:** Saving an edited template immediately re-assembles (`assemble_email()`) every currently-queued contact on that path with the new template text + their existing AI-generated opening line. No stale previews — what the teammate sees always matches what will send.
- **D-05:** Edited templates persist permanently as the new default for that path, surviving app restarts — this requires a small new persistence layer (e.g. a `templates` table in SQLite), seeded from `personalization/templates.py`'s current `PATH_TEMPLATES` dict on first read if no override exists yet. `PATH_TEMPLATES` becomes the fallback/seed default, not necessarily the sole source of truth once a teammate has edited a path.
- **D-06:** Before an edited template can be saved, the app validates that all 3 merge fields (`{first_name}`, `{company}`, `{opening_line}`) are still present and correctly spelled. If one is missing/broken, block the save and show a clear warning — prevents a literal `{first_name}` (or a silently generic email) shipping to a real contact.

### Approve flow & confirmation
- **D-07:** "Confirmed enrolled" (success criterion 3) means checking Apollo's `add_contact_ids` response body per contact, not just the HTTP status. Only contact IDs Apollo's response confirms as enrolled are marked `Enrolled`; every other contact in the batch is marked `Skipped` with Apollo's stated reason (spec.MD §3.7 documents `sequence_active_in_other_campaigns` / `sequence_finished_in_other_campaigns` as known 422 causes to surface).
- **D-08:** Partial failure within a batch does not block the rest — the batch proceeds, and afterward each contact's actual outcome (Enrolled / Skipped + reason) is shown in the queue. Skipped contacts remain in the queue at `status='drafted'` per QUEUE-03 (not discarded), available for a later retry.
- **D-09:** Both "Approve Selected" and "Approve All" require a confirmation dialog before firing — "Enroll N contacts into the [Path] sequence?" with explicit Confirm/Cancel — since this is an irreversible action that sends real emails to real companies. This is a deliberate exception to the existing Discovery page's immediate-fire button pattern (Find Contacts / Enrich & Continue), justified by consequence and irreversibility.

### Queue page layout
- **D-10:** Reuse Phase 3's Discovery-page pattern: `st.dataframe`-style table (Name/Company/Title, checkbox column) with a collapsed "View draft" expander per row showing the full assembled email — not a card-list layout. Keeps the app visually consistent and reuses a proven pattern.
- **D-11:** The queue is scoped to one path at a time via a selector (dropdown/tabs), not all paths mixed in one list — this keeps the template editor (D-03) unambiguous: it always edits the template for whichever path's contacts are currently visible.
- **D-12:** After Approve fires, a successfully-enrolled row stays visible with a green "Enrolled" status badge in place of its checkbox — gives in-the-moment per-contact confirmation. The row naturally drops out of the queue on the next page load/rerun since it's no longer `status='drafted'`.

### Personalization delivery (scope addition — post-planning gap, fixed before execution)
- **D-14:** As originally planned, enrollment only added a contact to an Apollo sequence — Apollo then sends whatever static template is pre-built in that sequence's own editor, meaning Phase 3's AI-generated opening line was never actually transmitted anywhere; it was a review-only preview. Confirmed via live doc fetches against `docs.apollo.io` that Apollo supports **Custom Dynamic Variables**: a custom field created via `POST /fields` (`modality: "contact"`, `type: "string"`) auto-generates a `{{merge_tag}}` usable inside a sequence's email body in Apollo's UI. Decision: create ONE new Apollo custom field to carry just the AI-generated `opening_line` (short, ~20-30 words — well under any field length limit). The static paragraph text already in `personalization/templates.py`'s `PATH_TEMPLATES` is copied by the user into each of the 3 real Apollo sequences' email step (one-time manual setup, same category as D-11's `[SPONSORSHIP_LINK]` placeholder), using Apollo's own **native** `{{company_name}}`/`{{first_name}}` dynamic variables for those merge points (no custom field needed for those — Apollo already knows them) and the new custom field's merge tag wherever `{opening_line}` sits in the template today.
- **D-15:** Rejected alternative: pushing the entire assembled email (all paragraphs) as one large custom field, with the Apollo sequence body reduced to a single merge tag. Would keep `personalization/templates.py` as the sole source of truth with nothing duplicated into Apollo's UI, but carries unverified risk (textarea field length caps, whether multi-paragraph line breaks render correctly in a sent email) that the opening-line-only approach avoids. Not pursued.
- **D-16:** `POST /contacts/bulk_create` accepts `typed_custom_fields: {field_id: value}` per contact in the request — confirmed via live doc fetch — so the opening line rides along with the same contact-creation call `apollo/client.py`'s new `create_contacts_bulk()` (04-03) already makes. No separate API call needed for the common case (a genuinely new contact).
- **D-17:** Edge case, confirmed via live doc fetch: contacts already existing in Apollo (returned in `bulk_create`'s `existing_contacts` array — distinct from this app's own local dedup registry, e.g. a contact someone else added directly in Apollo) are returned **unmodified**; `typed_custom_fields` in the create request has no effect on them. Resolution: a follow-up `PATCH /contacts/{contact_id}` call (confirmed supports `typed_custom_fields` identically to creation) for any contact ID that comes back in `existing_contacts`, so the opening line still reaches them rather than silently shipping stale/empty personalization — consistent with D-08's "never silently drop" philosophy.
- **D-18:** Custom field creation must be idempotent (check-if-exists before create, matching this project's established `ensure_schema()` pattern) — exact current non-deprecated lookup endpoint and the field's practical length limit need confirmation from a research pass before task-writing (the `typed_custom_fields` list endpoint this session found is documented as deprecated in favor of a `fields` endpoint with a `source` filter, but the exact live shape wasn't confirmed).

### Claude's Discretion
None — all five discussed areas (Sequence ID resolution, Bulk template editor, Approve flow & confirmation, Queue page layout, Personalization delivery) reached explicit user decisions; no "you decide" items remain open.

### Folded Todos
- **"Add bulk template editor to Email Drafts page"** (`.planning/todos/pending/2026-09-17-add-bulk-template-editor-to-email-drafts-page.md`) — originally captured during Phase 3's human-verify checkpoint when the developer noticed there was no way to fix a bad template globally. Confirmed during this discussion to exist nowhere in the roadmap (not Phase 5, not REVIEW-01 — that's per-contact editing, a different capability) or backlog before being folded in. Now covered by D-03 through D-06 above. The todo file should be moved to `.planning/todos/completed/` once this CONTEXT.md is committed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Apollo API integration
- `spec.MD` §3.7 — `POST /api/v1/emailer_campaigns/{sequence_id}/add_contact_ids`; required `sequence_id` (path) + `emailer_campaign_id` (query, must match); documented 422 failure modes (`sequence_active_in_other_campaigns`, `sequence_finished_in_other_campaigns`, missing `send_email_from_email_account_id`, inactive mailbox) — directly informs D-07/D-08
- `spec.MD` §3.4–3.6 (implied, contact-creation step) — "only Apollo *contacts* (not raw enriched people) can be added to a sequence"; QUEUE-04 requires contact creation via bulk create with `run_dedupe: true` before enrollment
- `apollo.MD` — sequences reference index
- `CLAUDE.md` "Key API Notes (Apollo.io)" — `/contacts` (600 req/hour), `/contacts/bulk_create` (use instead of looping), `/emailer_campaigns/{id}/add_contact_ids` (600 req/hour) rate limits
- `https://docs.apollo.io/reference/create-a-custom-field` — `POST /fields`, `modality`/`type`/`meta.max_length` params, informs D-14/D-18
- `https://knowledge.apollo.io/hc/en-us/articles/4409494161677-Use-Custom-Dynamic-Variables` — confirms custom fields auto-generate `{{merge_tag}}` variables usable in sequence email bodies, informs D-14
- `https://docs.apollo.io/reference/bulk-create-contacts` — confirms `typed_custom_fields` per-contact support and the `existing_contacts` unmodified-on-match behavior, informs D-16/D-17
- `https://docs.apollo.io/reference/update-a-contact` — `PATCH /contacts/{contact_id}`, confirms `typed_custom_fields` support identical to creation, informs D-17's follow-up-update path

### Prior phase decisions this phase builds on
- `.planning/phases/02-contact-discovery/02-CONTEXT.md` D-10 — per-contact removal explicitly deferred from Phase 2 to "the Phase 4 bulk-approve review queue (QUEUE-03)"; this phase is where that deferred capability actually lands (as bulk checkbox selection, not per-contact edit — REVIEW-01 stays v2)
- `.planning/phases/03-ai-personalization/03-CONTEXT.md` D-02 — "the formal multi-contact Review Queue is Phase 4's job (QUEUE-01/02)" — confirms this phase is a NEW page, not an extension of Discovery's inline Email Drafts section
- `db/schema.py` — `prospect` table status enum (`found → selected → enriched → contact_created → drafted → approved → sequenced`) and the `contacted_registry` view this phase's D-04 success criterion (registry update after enrollment) must write into
- `personalization/templates.py` — `PATH_TEMPLATES` dict (current static defaults) and `assemble_email()` (pure merge function) — this phase's template editor (D-03–D-06) wraps/overrides this module's data, not its assembly logic
- `apollo/client.py` — existing `(status, message)`-tuple-never-raises pattern (used by `search_people`, `bulk_match_people`, `enrich_candidates`) must extend to the new contact-creation and sequence-enrollment client functions this phase adds

### Project scope
- `.planning/ROADMAP.md` (Phase 4 entry) — full success criteria for this phase
- `.planning/REQUIREMENTS.md` (QUEUE-01/02/03/04; v2 REVIEW-01, SEND-01, CONF-01 — confirms per-contact edit/skip and full enrollment-status detail stay out of scope for this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pages/discovery_page.py` — the table + `st.expander` per-row pattern (Name/Company/Title/Email + "View draft" expander with `st.code(full_text, language=None)`) this phase's queue page reuses per D-10
- `apollo/client.py` — `_post_with_retry`, `_chunk` (batches of ≤10) helpers already built for `bulk_match_people`; the new bulk contact-creation and sequence-enrollment functions should reuse these rather than reimplementing retry/chunking
- `db/prospects.py` — `update_draft()` establishes the pattern for advancing `prospect.status`; this phase needs equivalent `mark_contact_created()` / `mark_sequenced()` functions following the same shape

### Established Patterns
- Typed `(status, message)` tuples for every external call, never raising — must extend to the new contact-creation and sequence-enrollment client functions
- `st.secrets` for all keys/IDs, never logged — applies to the 3 new sequence-ID secrets (D-01/D-02)
- Idempotent, additive-only `ensure_schema()` migrations in `db/schema.py` — the new template-override table (D-05) must follow this same idempotent-boot pattern, not a one-off migration script

### Integration Points
- New Review Queue page registers via `app.py`'s `st.navigation`, same extension point Phase 2's Discovery page used
- Reads contacts at `status='drafted'` (written by Phase 3's `update_draft()`); on successful enrollment, advances to `status='sequenced'` and writes into `contacted_registry` (via `apollo_contact_id` + `company_domain`, per D-08/D-12 and the phase's success criterion 4)

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or exact wording given beyond the decisions above. Concrete expectations: template editor sits above a path-scoped table+expander queue, edits re-assemble visible drafts immediately, Approve All/Selected both gate behind a count-confirmation dialog, and enrolled rows get a visible "Enrolled" badge rather than disappearing instantly.

</specifics>

<deferred>
## Deferred Ideas

None new — discussion stayed within phase scope (the one scope addition, bulk template editing, was deliberately folded in per the Folded Todos entry above, not deferred).

### Reviewed Todos (not folded)
None — the only matching todo was folded in.

</deferred>

---

*Phase: 4-Review Queue and Sequence Enrollment*
*Context gathered: 2026-09-17*
