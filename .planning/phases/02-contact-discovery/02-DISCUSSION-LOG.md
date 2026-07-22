# Phase 2: Contact Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-22
**Phase:** 2-contact-discovery
**Areas discussed:** Path → Apollo filter translation, Results list display, Credit cost review gate (DISC-04), Search-to-enrichment funnel

---

## Path → Apollo filter translation

| Option | Description | Selected |
|--------|-------------|----------|
| Free text only | All 3 paths use identical search logic — free text drives filters, path only changes downstream sequence/template | ✓ |
| Path adds baked-in filters | Each path also fixes an Apollo filter (company size, location) on top of free text | |
| You decide | Claude picks per-path defaults based on typical student-org target profiles | |

**User's choice:** Free text only.

| Option | Description | Selected |
|--------|-------------|----------|
| Title keyword search | User's words go directly into Apollo's `person_titles` keyword field | ✓ |
| AI-inferred seniority tag | An AI call classifies free text into Apollo's fixed seniority enum | |
| Both | Title keywords + AI-inferred seniority layered together | |

**User's choice:** Title keyword search.

| Option | Description | Selected |
|--------|-------------|----------|
| Keyword search | User's words go directly into Apollo's organization keyword-tag field | ✓ |
| Structured industry taxonomy | Map free text to Apollo's fixed industry taxonomy IDs | |

**User's choice:** Keyword search.

| Option | Description | Selected |
|--------|-------------|----------|
| Direct pass-through | User's typed words go straight into Apollo params, no extra API call | ✓ |
| AI normalization step | A cheap Claude Haiku call cleans up/expands free text before hitting Apollo | |

**User's choice:** Direct pass-through.
**Notes:** User asked Claude to investigate whether AI normalization would save money before deciding. Investigation found: Apollo search is 0 credits regardless of query quality, so normalization saves nothing on the free search call; enrichment credit spend is bounded by the 50-contact cap either way, not by query precision; the real risk without normalization is *relevance* (spending real enrichment credits on technically-valid-but-poor-fit contacts), not credit *count*. Normalization's own cost is trivial (~$0.0005–0.001/search via Haiku). Conclusion presented to user: normalization is a relevance lever, not a cost-savings lever. User chose to stick with direct pass-through and revisit later if relevance becomes a real problem in practice.

---

## Results list display

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only preview | Full batch proceeds automatically to Phase 3; per-contact removal deferred to Phase 4's bulk-approve review queue | ✓ |
| Allow row removal here too | Checkboxes to deselect bad matches before personalization runs | |

**User's choice:** Read-only preview.

| Option | Description | Selected |
|--------|-------------|----------|
| Name, Company, Title, Email | The essentials for a relevance sanity-check | ✓ |
| Add industry / company size | Same plus organization_industry and employee-count | |

**User's choice:** Name, Company, Title, Email.

| Option | Description | Selected |
|--------|-------------|----------|
| Plain message + edit search | "No new contacts found — try different search terms," free-text inputs still editable | ✓ |
| Show excluded count too | Same, plus a breakdown of found vs. already-contacted | |

**User's choice:** Plain message + edit search.

**Notes:** Table layout itself (st.dataframe vs. cards) was not re-litigated — already settled by CLAUDE.md's tech-stack doc, which explicitly specifies `st.dataframe` for search results.

---

## Credit cost review gate (DISC-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Show cost estimate only | "Up to N credits" computed locally; no balance shown; Apollo API errors surface naturally if out of credits | ✓ |
| Link out to Apollo dashboard | Same cost estimate, plus a reminder link to check balance manually in Apollo | |

**User's choice:** Show cost estimate only.
**Notes:** This question was raised because Claude flagged, before asking, that Apollo has no API endpoint for credit balance at all (confirmed via a live authenticated call during Phase 1's human-verify checkpoint this same session — `usage_stats/api_usage_stats` returns only rate-limit data, and Apollo's docs confirm balance is dashboard-only). This directly affects DISC-04's literal wording ("credit balance is displayed") — the decision reinterprets DISC-04 as a cost *estimate*, not a balance *display*.

| Option | Description | Selected |
|--------|-------------|----------|
| Search then Enrich, two buttons | 'Find Contacts' (free, shows count + cost estimate) then a separate 'Enrich & Continue' (spends credits) | ✓ |
| Single combined action | One button runs search + enrichment together with a confirm dialog in between | |

**User's choice:** Search then Enrich, two buttons.

---

## Search-to-enrichment funnel

| Option | Description | Selected |
|--------|-------------|----------|
| Count + cost only | No contact table at the pre-enrichment stage — Apollo search doesn't return real emails yet | ✓ |
| Preview table without emails | Show Name/Company/Title immediately, Email populates after enrichment | |

**User's choice:** Count + cost only.

| Option | Description | Selected |
|--------|-------------|----------|
| First 50 from Apollo | Take Apollo's own result ordering as-is when more than 50 candidates match | ✓ |
| You decide | Claude picks a tie-break heuristic if Apollo's ordering seems arbitrary | |

**User's choice:** First 50 from Apollo.

---

## Claude's Discretion

None — every discussed gray area reached an explicit user decision.

## Deferred Ideas

None raised outside phase scope. Two possibilities were explicitly considered and set aside (not full scope-creep deferrals, but noted for potential revisit):
- AI query normalization for search relevance (see Path → filter translation notes above)
- Per-contact removal at the discovery stage, rather than waiting for the Phase 4 review queue
