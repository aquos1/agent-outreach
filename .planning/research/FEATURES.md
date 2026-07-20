# Features Research: Outreach Agent

**Domain:** AI-powered B2B email outreach automation for non-technical users
**Researched:** 2026-07-19
**Apollo.io as backend:** All contact discovery and email sequencing flows through Apollo.io API

---

## Table Stakes (Must Have)

Features that every outreach tool provides. Missing any of these and users will feel the tool is incomplete or untrustworthy before they even launch a campaign.

| Feature | Why Expected | Complexity | Apollo.io Fit |
|---------|--------------|------------|---------------|
| Guided path selection (sponsorship vs client) | Non-technical users need guardrails; a blank form is paralyzing | Low | Custom UI layer above Apollo |
| Automated contact discovery | Core promise: zero manual contact-finding | Medium | Apollo People Search API — filters by title, company size, industry, seniority |
| AI-generated custom opening line per contact | "Icebreaker" personalization is now standard in outreach tools; generic emails get 2x lower reply rates | Medium | Claude/GPT call per contact seeded with Apollo company/role data |
| Reusable email body template per outreach path | Sponsorship asks and client pitches have structurally different messages | Low | Apollo dynamic variables + sequence email body |
| Email sequence enrollment | Multi-step follow-up (e.g., Day 1 intro + Day 5 follow-up) is baseline expected behavior | Medium | Apollo Sequences API — add contacts to pre-built sequences |
| Auto-pause on reply | Tool must stop sending to contacts who reply; not doing this is unprofessional and burns relationships | Low | Apollo handles this natively within sequences |
| Campaign launch (send or queue toggle) | Some campaigns need human review before firing; some are urgent | Low | Toggle at campaign creation — routes to auto-enroll vs draft queue |
| Basic analytics: open rate + reply rate per campaign | Users need to know if their outreach is working; without this there's no feedback loop | Low | Apollo Analytics API (`/reports/sync_report`) returns open/reply rates by sequence |

---

## Differentiators (Competitive Advantage)

Features that commercial tools don't optimize for the student org use case, or that create meaningful leverage for this team specifically.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Three fixed outreach paths with pre-tuned search logic | Commercial tools make users configure ICP filters from scratch — our paths encode "who to find" for each use case (e.g., sponsorship = VP Marketing at mid-size tech cos; clients = VP Engineering or CPO at startups) | Medium | Hardcode sensible Apollo filter defaults per path; expose minimal overrides |
| AI opening line grounded in real contact context | Apollo returns company description, job title, headline — feed this to LLM for higher-quality lines vs competitors who use generic LinkedIn scrapers | Medium | Prompt engineering task; quality depends on Apollo data richness per contact |
| Pre-send review queue with inline editing | Commercial tools make review cumbersome (export to CSV, edit, re-import). An inline "approve / edit / skip" per contact before enrolling removes friction | High | Custom UI; Apollo add-to-sequence call per approved contact |
| Outreach path memory: don't re-contact companies already in Apollo sequences | Student orgs re-use contacts over years; accidentally emailing a current sponsor to solicit sponsorship is a relationship mistake | Medium | Check Apollo contact status / existing sequence enrollment before adding |
| Campaign naming and history | Multiple teammates run campaigns over time; naming + date stamps let the team audit "who contacted who when" | Low | Metadata stored locally or in Apollo sequence naming conventions |
| Per-path email templates pre-loaded and editable | Non-technical users shouldn't write sponsorship emails from scratch; opinionated defaults with light editing reduces time-to-launch from hours to minutes | Low | Store templates in app; inject into Apollo sequence step |

---

## Anti-Features (Deliberately Excluded from v1)

Things to not build. Each exclusion has a specific reason tied to scope, user capability, or complexity-to-value ratio.

| Anti-Feature | Why Exclude | What to Do Instead |
|--------------|-------------|-------------------|
| Manual contact list import | Contradicts the core value (agent finds contacts autonomously); adds CSV parsing complexity | Apollo search is the only contact source |
| LinkedIn / phone / SMS outreach | Multi-channel sequences require separate auth, deliverability management, and UX surfaces | Email-only; revisit in v2 if reply rates plateau |
| CRM sync (Salesforce, HubSpot) | Apollo is the system of record; syncing to a second CRM adds integration debt without clear benefit for a student org | Apollo contact records serve as lightweight CRM |
| A/B testing subject lines or email copy | Requires statistical significance which a small student org never achieves; creates false confidence in "winners" | Use single proven template per path; iterate manually across campaigns |
| AI auto-reply / response handling | AI drafting responses to inbound replies requires trust calibration most non-technical teams can't audit; mistakes damage real relationships | Route replies to teammate inbox manually |
| Lead scoring / intent signals | Apollo's buying intent filters and scoring are enterprise features; overkill for 3 fixed use cases | Fixed search filter presets encode all the targeting needed |
| Deliverability infrastructure management (DKIM, domain warm-up) | Apollo handles sending infrastructure; managing this in-app adds ops burden without benefit | Rely on Apollo's sending limits and deliverability defaults |
| Custom outreach path builder | Freeform path creation for non-technical users causes bad targeting and poor AI output quality | 3 fixed paths only in v1; validate before adding paths |
| Unsubscribe / compliance management | Apollo handles bounce and opt-out at the sequence level | Trust Apollo's compliance handling; add warning in UI to not circumvent it |
| Real-time notifications / Slack integration | Nice-to-have, but adds surface area for v1 | Users check the dashboard manually |

---

## Feature Complexity Notes

### Apollo.io API Capabilities and Constraints

**Contact Discovery (People Search API)**
- Filters available: `person_titles[]`, `person_seniorities[]`, `organization_num_employees_ranges[]`, `organization_locations[]`, `q_organization_domains_list[]`, revenue range, currently-used technologies, and more
- Returns: name, company, title, LinkedIn — but NOT email addresses; email requires a separate enrichment call
- Rate limit: 50,000 display limit per search; 100 records per page, up to 500 pages
- Credit model: search/list calls are free; enrichment calls consume credits — design to only enrich contacts actually being enrolled in campaigns

**Sequence Enrollment (Add Contacts to Sequence API)**
- Rate limit: 600 calls per hour — sufficient for student org volumes (campaigns of 20-100 contacts)
- Requirement: Contact must already exist in Apollo DB before sequence enrollment; use Bulk Create Contacts endpoint (up to 100 per request) first
- Auto-pause on reply: Built-in Apollo behavior — sequences pause when a contact replies; no custom code needed
- Sending schedule: Apollo controls timing per sequence setup; agent does not need to manage send cadence

**Analytics (Sync Report API)**
- Available metrics: emails delivered, opened, replied, interested (positive reply) by sequence
- Programmatic: `/reports/sync_report` endpoint returns aggregated sequence stats
- Open rate caveat: Apollo documentation warns that open rates are inflated by mail clients pre-fetching tracking pixels; surface reply rate as the primary trust metric

**AI Personalization (Opening Line Generation)**
- Input data available from Apollo: company description, person's job title, seniority, LinkedIn headline, company industry, employee count
- Complexity: A single LLM call per contact with a structured prompt; not agentic — no tool calls or multi-step reasoning needed at this stage
- Quality risk: Apollo's company descriptions vary in richness; some contacts will have thin data, producing generic-sounding lines; needs a fallback (use template fallback line if context is too sparse)

### Feature Dependency Map

```
Path Selection
  └── Contact Discovery (Apollo People Search)
        └── AI Opening Line Generation (LLM call per contact)
              └── Draft Review Queue (approve / edit / skip)
                    └── Sequence Enrollment (Apollo Add Contact to Sequence)
                          └── Analytics Dashboard (Apollo Sync Report API)
```

### What "Non-Technical User" Means for Each Feature

| Feature | Non-Technical Constraint |
|---------|--------------------------|
| Path selection | Must be a button/card, not a dropdown with typed parameters |
| Contact discovery | Zero filter configuration — path pre-selects all filters; user sees "we're finding contacts" |
| Opening line review | Show the line, company, and name together so user can sanity-check in 3 seconds per contact |
| Campaign launch | One button labeled clearly as "send now" or "save for review" — no configuration required |
| Analytics | Show two numbers: open rate and reply rate. No pivot tables, no CSV exports |

---

## MVP Feature Prioritization

**Build first (v1 launch):**
1. Path selection UI (3 cards: club sponsor / productthon sponsor / consulting client)
2. Contact discovery with pre-tuned Apollo filters per path
3. AI opening line generation per contact
4. Pre-send review queue (inline approve / edit / skip)
5. Sequence enrollment via Apollo API
6. Campaign analytics: open rate + reply rate

**Defer with reason:**
- Outreach path memory (don't re-contact existing): important but can be partially solved by naming convention until volume warrants automation
- Campaign naming / history: good UX hygiene; can start with timestamp-based auto-names
- Per-path template editing: start with hard-coded defaults; expose editing only after first user complaints

**Never build in v1:**
- Everything in Anti-Features above

---

## Sources

- [Apollo.io People API Search Parameters](https://docs.apollo.io/reference/people-api-search) — official API docs, confirmed filter list
- [Apollo.io Sequences Overview](https://knowledge.apollo.io/hc/en-us/articles/4409237165837-Sequences-Overview) — sequence capabilities and plan limits
- [Apollo.io Dynamic Variables](https://knowledge.apollo.io/hc/en-us/articles/4409494161677-Use-Custom-Dynamic-Variables) — personalization variable system
- [Apollo.io Sync Report API](https://docs.apollo.io/reference/sync-report) — analytics endpoint for open/reply rates
- [Apollo.io Add Contacts to Sequence API](https://docs.apollo.io/reference/add-contacts-to-sequence) — rate limits and requirements (600 calls/hr, contact must exist first)
- [AI Icebreaker/Opening Line Best Practices — Breakcold](https://www.breakcold.com/blog/cold-email-first-line-opening-lines) — max 2 sentences, casual tone, grounded in real research
- [Email Open Rate Inflation Warning — Apollo](https://www.apollo.io/insights/how-can-i-track-email-open-rates-and-reply-rates-for-my-campaigns) — open rates inflated by pixel prefetch; reply rate is more reliable
- [Cold Email UX Friction Research — Instantly.ai](https://instantly.ai/blog/easy-to-use-email-outreach-tools/) — what makes outreach tools feel overwhelming
- [Student Sponsorship Outreach Strategy — classrooms.com](https://classrooms.com/guide-to-outreaching-for-student-group-sponsorship-opportunities/) — what companies want from student club pitches
