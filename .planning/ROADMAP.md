# Roadmap: Outreach Agent

## Overview

Five vertical slices that build on each other, each delivering something a teammate can actually use. Phase 1 establishes the foundation and data registry. Phase 2 gives teammates the ability to discover and preview contacts for a chosen path. Phase 3 attaches AI-personalized email drafts to those contacts. Phase 4 wires the full end-to-end pipeline with a review queue and sequence enrollment so emails actually get sent. Phase 5 closes the loop with a campaign analytics dashboard.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Verified Apollo connection, SQLite schema, and mailbox health check — nothing can run without this (completed 2026-07-22)
- [x] **Phase 2: Contact Discovery** - Teammate picks a path, enters targeting, and sees a credit-aware list of enriched contacts with duplicates excluded (completed 2026-09-17)
- [ ] **Phase 3: AI Personalization** - Teammate sees a full AI-assembled email draft per contact before any send decision is made
- [ ] **Phase 4: Review Queue and Sequence Enrollment** - Teammate reviews drafts and approves the queue to enroll contacts into Apollo sequences — emails get sent
- [ ] **Phase 5: Analytics Dashboard** - Teammate sees open rate and reply rate per campaign pulled live from Apollo

## Phase Details

### Phase 1: Foundation

**Goal**: The app boots, connects to Apollo, validates the sending mailbox, and has a persistent data registry — all pre-conditions for any outreach are confirmed green before a teammate ever touches a campaign
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: DEDUP-01
**Success Criteria** (what must be TRUE):

  1. Running the app displays a health status page showing Apollo API key validity, current credit balance, and mailbox deliverability (SPF/DKIM/DMARC) as pass/fail indicators
  2. A teammate can see a clear error message (not a stack trace) if the Apollo key is missing or invalid
  3. The SQLite database is created automatically on first launch with the full prospect and email_events schema — no manual setup required
  4. The contacted registry (prospect IDs and company domains) persists across app restarts

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Wave 0: project scaffold, dependency pins, theme/gitignore, and RED test harness
- [x] 01-02-PLAN.md — Persistent SQLite registry: prospect/email_events schema + contacted_registry dedup view (DEDUP-01)
- [x] 01-03-PLAN.md — External connectivity checks: Apollo health/credits client + SPF/DMARC/DKIM DNS checks

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-04-PLAN.md — System Health landing page + app boot wiring with D-01/D-02/D-03 gating

### Phase 2: Contact Discovery

**Goal**: A teammate can pick one of three outreach paths, enter a company type and target role, review the credit cost, and see a list of enriched contacts with verified emails — ready for personalization
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: PATH-01, PATH-02, PATH-03, DISC-01, DISC-02, DISC-03, DISC-04, DEDUP-02
**Success Criteria** (what must be TRUE):

  1. Teammate sees exactly three path options (Club Sponsorship, Productthon Sponsorship, Client Sourcing) and selecting one requires no further filter configuration
  2. Teammate enters a company type and target role as free text and the app translates these into Apollo search filters invisibly
  3. Before any enrichment credits are spent, teammate sees the remaining credit balance and the estimated cost for the current contact batch
  4. The contact list returned contains only contacts with verified email addresses, and previously contacted contacts (matched by Apollo ID or company domain) are excluded from the list

**Plans**: 4 plans
Plans:

**Wave 1**

- [x] 02-01-PLAN.md — Discovery logic + dedup: free-text→filter translation, has_email pre-filter, cost estimate, contacted_registry dedup query (PATH-02, DISC-01, DISC-02, DISC-04, DEDUP-02)
- [x] 02-02-PLAN.md — Apollo client: search_people + bulk_match_people + enrich_candidates batching + 429 backoff (DISC-03)

**Wave 2** *(blocked on Wave 1)*

- [x] 02-03-PLAN.md — Live Apollo field-name verification checkpoint + reconcile .get() lookups (DISC-02, DISC-03)

**Wave 3** *(blocked on Wave 2)*

- [x] 02-04-PLAN.md — Contact Discovery page: two-stage session-state Find→Enrich flow + nav registration (PATH-01, PATH-03)
**UI hint**: yes

### Phase 3: AI Personalization

**Goal**: Every discovered contact has a full email draft — one AI-written personalized opening line plus the path-specific template body — ready for teammate review
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: PERS-01
**Success Criteria** (what must be TRUE):

  1. Each contact in the discovered list has a distinct AI-generated opening line that references only verifiable Apollo fields (title, company, industry, seniority) — no hallucinated details
  2. The full assembled email draft (opening line + template body) is visible to the teammate per contact before any send action is taken
  3. If Apollo enrichment data is sparse for a contact, the app falls back to a safe generic opening line rather than generating a plausible fabrication

**Plans**: 4 plans
Plans:

**Wave 1**

- [x] 03-01-PLAN.md — anthropic dependency pin + ANTHROPIC_API_KEY boot gate + Wave 0 RED test harness (PERS-01)

**Wave 2** *(blocked on Wave 1)*

- [ ] 03-02-PLAN.md — personalization package: grounded Haiku opening line, shared fallback, three verbatim path templates (PERS-01)
- [ ] 03-03-PLAN.md — idempotent draft-column migration + update_draft() status='drafted' write (PERS-01)

**Wave 3** *(blocked on Wave 2)*

- [ ] 03-04-PLAN.md — Discovery page: auto-chained draft generation, progress, View draft expanders, fallback banner + human verify (PERS-01)
**UI hint**: yes

### Phase 4: Review Queue and Sequence Enrollment

**Goal**: A teammate can review the full queue of email drafts and approve them in bulk, which enrolls the contacts into the correct Apollo sequence — the campaign is live
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04
**Success Criteria** (what must be TRUE):

  1. All generated email drafts appear in a single review queue showing contact name, company, role, and full email preview before any enrollment occurs
  2. A single "Approve All" button triggers Apollo contact creation (with run_dedupe: true) and sequence enrollment for every draft in the queue
  3. After enrollment, the teammate sees per-contact status (Enrolled / Skipped with reason) — a 200 OK from Apollo alone is not treated as confirmation
  4. Enrolled contacts and their company domains are added to the deduplication registry immediately after successful enrollment

**Plans**: TBD
**UI hint**: yes

### Phase 5: Analytics Dashboard

**Goal**: A teammate can open the dashboard and see open rate and reply rate per campaign, pulled from Apollo on a polling schedule — campaign performance is visible without leaving the app
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: DASH-01, DASH-02
**Success Criteria** (what must be TRUE):

  1. Dashboard displays open rate and reply rate for each completed campaign — reply rate is the primary metric shown prominently
  2. Stats are fetched from Apollo on a 15-minute polling schedule and the dashboard shows the last-refreshed timestamp so the teammate knows how fresh the data is
  3. Teammate can distinguish between campaigns by path name and launch date

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 4/4 | Complete   | 2026-07-22 |
| 2. Contact Discovery | 3/4 | In Progress|  |
| 3. AI Personalization | 1/4 | In Progress|  |
| 4. Review Queue and Sequence Enrollment | 0/TBD | Not started | - |
| 5. Analytics Dashboard | 0/TBD | Not started | - |
