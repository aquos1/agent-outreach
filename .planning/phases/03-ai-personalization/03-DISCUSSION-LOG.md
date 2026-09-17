# Phase 3: AI Personalization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-17
**Phase:** 3-ai-personalization
**Areas discussed:** Generation trigger & draft visibility, Opening line style & fallback, Email template content per path, Claude API failure handling

---

## Generation trigger & draft visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Automatic, chained | Drafts generate immediately after enrichment succeeds, same page | ✓ |
| Separate 'Generate Drafts' button | Mirrors two-stage gate pattern from Phase 2 | |

| Option | Description | Selected |
|--------|-------------|----------|
| Extend Discovery page | Add expandable 'View draft' per row to existing results table | ✓ |
| New dedicated Drafts page | Separate nav entry listing all enriched contacts + drafts | |

| Option | Description | Selected |
|--------|-------------|----------|
| Single combined preview | Full email as it would be sent, one block | ✓ |
| Split view | Opening line separate from template body | |

| Option | Description | Selected |
|--------|-------------|----------|
| Persist immediately | status='drafted' written right after generation | ✓ |
| Session state only | Hold in st.session_state, defer DB write to Phase 4 | |

**User's choice:** All Claude-recommended options.
**Notes:** Haiku cost is negligible per CLAUDE.md, so no spend-gate reason to mirror Apollo's two-stage pattern.

---

## Opening line style & fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Warm but professional | Friendly, conversational, not stiff or overly casual | ✓ |
| Formal/corporate | Straightforward, businesslike | |
| Casual/direct | Short, punchy, low-formality | |

| Option | Description | Selected |
|--------|-------------|----------|
| Title + company only | Simplest, lowest hallucination risk | ✓ |
| Title + company + industry/seniority when available | Richer, more variation | |

| Option | Description | Selected |
|--------|-------------|----------|
| Missing/placeholder title only | Company guaranteed by enrichment; title is the only realistic gap | ✓ (final) |
| Any missing field at all | Stricter — falls back even if only industry/seniority missing | (initial pick, reversed) |

**User's choice:** Warm but professional / title+company only / any-missing-field (initially) then reconciled to title-only.
**Notes:** User initially picked "any missing field" for fallback trigger, which contradicted the title+company-only field-usage decision (industry/seniority are never used, so their absence can't matter). Claude flagged the contradiction; user then picked the consistent option (title-only trigger).

| Option | Description | Selected |
|--------|-------------|----------|
| 1 sentence, ~20-30 words | Matches ~50-60 output token budget | ✓ |
| 1-2 sentences, up to ~50 words | More detail, ~2x token cost | |

---

## Email template content per path

**Source of templates:**
- Productthon: user pasted existing copy directly (the "Product Games" sponsorship email).
- Client Sourcing: user pasted existing copy directly (services/consulting pitch) — initially the user pasted duplicate productthon text for this path by mistake; Claude flagged the mismatch (client sourcing = consulting engagements per PROJECT.md, not event sponsorship) and the user then supplied the correct client-sourcing copy.
- Club Sponsorship: no existing email copy existed. User pointed to `tmp/Product Space UW — Sponsorship Prospectus.docx` (org stats, sponsorship tiers, benefits) as source material; Claude drafted the email body from that content, mirroring the productthon email's structure, and the user approved it as-is.

**`{opening_line}` placement:** Standalone line immediately after "Hello [First Name]!" and before the intro paragraph, in all three templates — user confirmed "looks good."

**Client Sourcing subject line:** User's paste had a malformed "Subject: Body:" artifact with no actual subject text. User said "just pick some subject" — Claude chose `Partner with Product Space UW on Your Next Product Initiative`.

**Attachments question:** User asked whether email attachments (PDF sponsorship package/deck) are possible, and separately raised that attaching PDFs on a first-touch cold email can hurt deliverability/trigger spam filters.
- Claude confirmed technically: no attachment support anywhere in `apollo.MD`/`spec.MD`/`CLAUDE.md` — this app only enrolls contacts into pre-built Apollo sequences via API, never composes per-email content/attachments.
- Claude confirmed the deliverability point independently as a known cold-email best practice (avoid raw attachments on first touch; use a hosted link instead).
- Resolution: both facts point the same direction — replaced "I've attached..." with a hosted-link reference (`[SPONSORSHIP_LINK]` placeholder) in the Productthon and Club Sponsorship templates. User confirmed they don't have a real link yet; noted as a manual pre-send setup step (D-11), not a Phase 3 build blocker.

**Mid-discussion requirements change:** User asked why Phase 4's review queue was "bulk approve only" and proposed per-contact checkboxes with both "Approve Selected" and "Approve All." Claude distinguished this from REVIEW-01 (v2-deferred per-contact *editing*) — checkbox-based subset approval is lighter-weight and doesn't conflict with that deferral. User confirmed: checkboxes default-checked, both buttons enroll whatever's checked, unchecked contacts stay in queue (not discarded). `REQUIREMENTS.md` QUEUE-03 updated directly to reflect this (Phase 4 concern, captured now since it surfaced here).

---

## Claude API failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Use the safe generic fallback opener | Same fallback as sparse-data case, contact stays in batch | ✓ |
| Skip the contact entirely | Left out of batch, needs separate re-run | |

| Option | Description | Selected |
|--------|-------------|----------|
| One retry, then fallback | Mirrors Apollo's lighter-weight retry pattern | ✓ |
| No retry — fallback immediately | Simpler, faster | |

| Option | Description | Selected |
|--------|-------------|----------|
| Error banner if failure rate is high | Mirrors Apollo's error-banner convention (e.g. >50%) | ✓ |
| Always silent, per-contact fallback only | No batch-level banner ever | |

**User's choice:** All Claude-recommended options.
**Notes:** None — straightforward mirror of Phase 1/2's existing Apollo error-handling conventions.

---

## Claude's Discretion

- Exact numeric failure-rate threshold for the batch-level error banner (D-16) — user did not specify a number; left to planner/implementer (suggested >50%).

## Deferred Ideas

- Real hosted link for the sponsorship package/prospectus (replacing `[SPONSORSHIP_LINK]`) — a manual user setup step before real sends, not a phase or build task.
