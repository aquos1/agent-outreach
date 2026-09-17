# Requirements: Outreach Agent

**Defined:** 2026-07-19
**Core Value:** Non-technical teammates can launch a full outreach campaign in minutes with zero manual contact-finding or email drafting required.

## v1 Requirements

### Path Selection

- [ ] **PATH-01**: User sees exactly three outreach path options — Club Sponsorship, Productthon Sponsorship, Client Sourcing
- [ ] **PATH-02**: Selecting a path determines all downstream search filters, sequence ID, and email template (user configures nothing else about targeting)
- [ ] **PATH-03**: User enters a company type / industry and target role as free-text inputs to guide contact discovery within the selected path

### Contact Discovery

- [ ] **DISC-01**: Agent translates user's company type and role inputs into Apollo People Search filters (no raw filter UI shown to user)
- [x] **DISC-02**: Apollo search results are pre-filtered to contacts with `has_email: true` before enrichment (no credits spent on un-emailable contacts)
- [x] **DISC-03**: Agent runs Apollo bulk enrichment to retrieve verified email addresses for discovered contacts
- [ ] **DISC-04**: Credit balance is displayed to the user before any enrichment begins so they can see cost impact before committing

### Personalization

- [ ] **PERS-01**: Agent generates one AI-written personalized opening line per contact using Claude Haiku, seeded with Apollo's returned title, company, industry, and seniority fields
- [ ] **PERS-01**: Agent assembles the full email draft: AI opening line + path-specific template body

### Review Queue

- [ ] **QUEUE-01**: All generated email drafts are placed in a review queue before any email is sent
- [ ] **QUEUE-02**: User sees all drafts in the queue (contact name, company, role, full email preview)
- [ ] **QUEUE-03**: Each queued contact has a checkbox (default checked); "Approve Selected" and "Approve All" both enroll the checked contacts into the Apollo sequence for that path. Unchecked contacts remain `status='drafted'` and stay in the queue for a later run (not discarded).
- [ ] **QUEUE-04**: Sequence enrollment creates Apollo contacts (with `run_dedupe: true`) and enrolls them in the path's pre-configured Apollo sequence

### Deduplication

- [x] **DEDUP-01**: System tracks all previously contacted Apollo contact IDs and company domains in a local registry
- [ ] **DEDUP-02**: Contacts already present in the registry are excluded before enrichment (no credit waste on repeat contacts)

### Analytics

- [ ] **DASH-01**: Campaign dashboard displays open rate and reply rate per campaign (reply rate is the primary metric)
- [ ] **DASH-02**: Dashboard stats are polled from Apollo on a schedule (no real-time push — Apollo has no engagement webhooks)

## v2 Requirements

### Per-Contact Review

- **REVIEW-01**: Individual approve / edit / skip per contact in the review queue (v1 is bulk approve only)

### Send Controls

- **SEND-01**: Per-campaign auto-send toggle (v1 is always review-first)
- **SEND-02**: Configurable contact cap per campaign (v1 uses a hardcoded default of 50)

### Enrollment Confirmation

- **CONF-01**: Per-contact enrollment status after bulk approval (Enrolled / Skipped with reason / Pending)

### Advanced Targeting

- **TARGET-01**: Saved targeting presets per path (so teammates don't re-enter company type / role each time)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-channel outreach (LinkedIn, phone, SMS) | Email only for v1 — single integration reduces complexity |
| Freeform Apollo filter configuration | Non-technical users — path presets handle all filter logic |
| A/B testing of email templates | Complexity without clear v1 value; add in v2 once baseline data exists |
| Auto-reply AI | High risk of sending an unreviewed AI reply; out of scope permanently for non-technical users |
| CRM integration (Salesforce, HubSpot) | Apollo is the system of record for v1 |
| Programmatic Apollo sequence creation | Apollo API cannot create sequences; they must be pre-built in the Apollo UI |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEDUP-01 | Phase 1 — Foundation | Complete |
| PATH-01, PATH-02, PATH-03 | Phase 2 — Contact Discovery | Pending |
| DISC-01, DISC-02, DISC-03, DISC-04 | Phase 2 — Contact Discovery | Pending |
| DEDUP-02 | Phase 2 — Contact Discovery | Pending |
| PERS-01 (opening line), PERS-01 (assembly) | Phase 3 — AI Personalization | Pending |
| QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04 | Phase 4 — Review Queue and Sequence Enrollment | Pending |
| DASH-01, DASH-02 | Phase 5 — Analytics Dashboard | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16 (all mapped)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-19*
*Last updated: 2026-07-19 after roadmap creation*
