# Phase 1: Foundation - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

The app's pre-flight layer: verifying Apollo connectivity, mailbox deliverability, and a persistent local data registry. This phase delivers nothing end-user-facing beyond a health status page — no contact discovery, personalization, or sending. Every later phase depends on these checks being green and the SQLite schema existing before it can write anything.

</domain>

<decisions>
## Implementation Decisions

### Health Check Gating
- **D-01:** An invalid or missing Apollo API key hard-blocks the entire app — no other screen is usable until `auth/health` passes. Prevents downstream Apollo calls from failing cryptically mid-campaign.
- **D-02:** A failed mailbox deliverability check (SPF/DKIM/DMARC) blocks only the send/enroll step — contact discovery and draft review remain usable. Avoids losing in-progress work over a fixable DNS issue, while still preventing a campaign that can't actually deliver.
- **D-03:** A zero or low Apollo credit balance is informational only — shown clearly on the health page but never blocks. DISC-04 (cost-before-commit at discovery time) is the real spending gate; duplicating that gate here would be redundant.
- **D-04:** The health check page is the default landing screen on every app boot, not an on-demand/settings-tab view. Teammate always sees pass/fail status before touching a campaign.

### Claude's Discretion
These areas were surfaced but not discussed in depth — user chose to proceed to context rather than dig in. Use judgment, and flag the choice made in the phase SUMMARY so it's visible for review:
- **Mailbox deliverability check method:** Apollo's API does not expose SPF/DKIM/DMARC status directly (confirmed against `apollo.MD`/`spec.MD` — no such endpoint is documented). Default to a direct DNS TXT-record lookup (SPF/DMARC) and DKIM selector lookup against the configured sending domain, since that's fully automatable without extra user setup. If DKIM selector discovery proves unreliable in practice, fall back to a manual "I've configured this" self-attestation checkbox rather than a flaky automated check.
- **Dedup registry scope (DEDUP-01):** Default to excluding common free/personal email domains (gmail.com, outlook.com, yahoo.com, hotmail.com, icloud.com) from domain-level dedup — only company-owned domains get the "already contacted this company" treatment. Contact-ID-level dedup applies to everyone regardless of domain.
- **Error message design:** Default to banner text with a concrete next step (e.g., "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets") rather than a bare status word, since the audience is non-technical and needs to know what to actually do.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Apollo API integration
- `apollo.MD` — Apollo API reference index; auth model (API key vs OAuth), `auth/health` test endpoint, links to rate limits and error status codes
- `spec.MD` §2 (Auth) — master API key storage (`st.secrets["APOLLO_API_KEY"]`), `GET /api/v1/auth/health` boot-check pattern, "Apollo connection failed" banner requirement
- `spec.MD` §5 (State tracking) — baseline SQLite schema for the prospect table: `name | company | apollo_person_id | apollo_contact_id | status | sequence_id | created_at`, with `status` enum `found → selected → enriched → contact_created → drafted → approved → sequenced`
- `spec.MD` §6 (Error handling) — 403/422/429 handling patterns; surface `message` field from Apollo error responses directly rather than a generic failure

### Project scope
- `.planning/ROADMAP.md` (Phase 1 entry) — full success criteria for this phase
- `.planning/REQUIREMENTS.md` (DEDUP-01) — registry requirement text

</canonical_refs>

<code_context>
## Existing Code Insights

Greenfield — no application code exists yet (repo contains only `CLAUDE.md`, `apollo.MD`, `spec.MD`, and `.planning/`). No reusable components, established patterns, or integration points to carry forward. The `spec.MD` schema above is the closest thing to prior art and should be treated as a strong starting point, not a strict contract — it predates this phase's DEDUP-01/health-check requirements and will need an `email_events` table and a dedup-focused registry view that spec.MD doesn't fully specify.

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or exact wording were given. The one concrete expectation: the health page shows pass/fail indicators for Apollo API key validity, credit balance, and mailbox deliverability (SPF/DKIM/DMARC) — per ROADMAP.md success criterion 1.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Foundation*
*Context gathered: 2026-07-20*
