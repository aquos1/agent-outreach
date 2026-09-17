# Outreach Agent

## What This Is

An AI-powered outreach tool that lets non-technical student org teammates run targeted email campaigns at scale without writing code. A teammate picks one of three goals — club sponsorship, productthon sponsorship, or client sourcing — and the agent handles finding contacts via Apollo.io, personalizing emails, and sending sequences automatically.

## Core Value

Non-technical teammates can launch a full outreach campaign in minutes instead of hours, with zero manual contact-finding or email drafting required.

## Requirements

### Validated

- ✓ Teammate selects one of three outreach paths (club sponsorship, productthon sponsorship, client sourcing) — Phase 2
- ✓ Agent finds relevant contacts via Apollo.io API based on the selected path (free-text targeting, credit-aware cost estimate, deduped verified-email results) — Phase 2

### Active

- [ ] Agent generates a custom opening line per contact, with a reusable template for the body
- [ ] Agent sends email sequences via Apollo.io sequencing
- [ ] Per-campaign toggle: auto-send or queue for teammate review before sending
- [ ] Dashboard shows campaign open rates and reply rates

### Out of Scope

- Manual contact list import — agent finds contacts autonomously via Apollo
- Multi-channel outreach (LinkedIn, phone) — email only for v1
- CRM integration beyond Apollo — Apollo is the system of record

## Context

- **Organization type**: University-based student organization (consulting/product club)
- **Outreach purposes**:
  - *Club sponsorship*: Companies that sponsor the student club (recurring partners)
  - *Productthon sponsorship*: Companies that sponsor a one-time hackathon/product event
  - *Client sourcing*: Companies that hire the club for consulting engagements
- **Target overlap**: Productthon and club sponsors overlap somewhat; consulting clients are a distinct persona
- **API layer**: Apollo.io — used for contact discovery and email sequencing
- **Reference docs**: `apollo.MD` (Apollo.io API reference), `spec.MD` (product spec)

## Constraints

- **Tech**: Apollo.io API is the contact and sequencing layer — all outreach flows through Apollo
- **Users**: Non-technical teammates — UI must require zero technical knowledge to operate
- **Personalization**: AI-generated custom opening line per contact; rest of email is a template per path

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Apollo.io for both contact data and sequencing | Single API handles find + send; avoids integrating two systems | ✓ Confirmed working — Phase 2 (search + bulk_match live-verified) |
| 3 fixed paths, not freeform | Non-technical users need guardrails; paths map to known use cases | ✓ Shipped — Phase 2 |
| Per-campaign approval toggle | Some runs need human review (high-stakes), others can auto-fire | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-17 after Phase 2 (Contact Discovery)*
