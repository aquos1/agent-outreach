# Phase 3: AI Personalization - Context

**Gathered:** 2026-09-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn every enriched contact from Phase 2 into a complete, teammate-reviewable email draft: one AI-generated opening line (Claude Haiku, seeded only with verifiable Apollo fields) plus the path-specific template body, assembled into a single preview. This phase delivers no bulk-approve/send UI and no per-contact selection (that's Phase 4's Review Queue) — its job ends at "every drafted contact has a trustworthy, visible draft and `status='drafted'` in SQLite."

</domain>

<decisions>
## Implementation Decisions

### Generation trigger & draft visibility
- **D-01:** Draft generation runs automatically, chained immediately after Discovery's "Enrich & Continue" succeeds — no separate button. Rationale: Haiku cost is negligible (~$0.04/campaign per CLAUDE.md), so there's no spend-gate reason to add a second manual stage like Apollo's Find/Enrich split.
- **D-02:** Draft visibility lives on the existing Discovery page (`pages/discovery_page.py`) — extend the post-enrichment results table with an expandable "View draft" per row. No new page for Phase 3; the formal multi-contact Review Queue is Phase 4's job (QUEUE-01/02).
- **D-03:** The draft preview shows the full assembled email as a single combined block (opening line + template body together, as it would actually be sent) — not split into separate "AI part" vs "template part" sections.
- **D-04:** Generated drafts persist to SQLite immediately with `status='drafted'`, consistent with the existing `found → selected → enriched → drafted → approved → sequenced` status progression from Phase 1's schema. Not session-state-only.

### Opening line style & fallback
- **D-05:** Tone is warm-but-professional — conversational, references their role/company, not stiff corporate boilerplate and not casual/slang. Fits a student org emailing real companies.
- **D-06:** The opening line may reference **only `title` + `company`** from Apollo data — no industry/seniority, even when those fields are present. Lowest hallucination-risk surface, satisfies success criterion 1 (verifiable fields only).
- **D-07:** The generic safe-fallback opener (success criterion 3) triggers **only when `title` is missing, null, or placeholder-looking** for a contact. Company name is guaranteed present by the time a contact reaches `status='enriched'`, so title is the only field in scope of D-06 that can realistically be sparse. (Explicitly NOT triggered by missing industry/seniority — those fields are never used in the opening line per D-06, so their absence is irrelevant to fallback logic. This reconciles an initial contradiction surfaced and corrected during discussion.)
- **D-08:** Opening line length target: **1 sentence, ~20-30 words** — keeps output tokens low (matches CLAUDE.md's ~50-60 output-token budget) and reads as a natural email opener rather than a paragraph.

### Email template content per path
- **D-09:** `{opening_line}` is inserted as its own standalone line immediately after the "Hello [First Name]!" greeting, before the intro paragraph, in **all three** path templates (see `<specifics>` for exact template text per path).
- **D-10:** No email attachments are used in any template. Confirmed technically impossible via this app regardless of preference — Apollo sequences are pre-built in the Apollo UI (per CLAUDE.md/apollo.MD/spec.MD, no attachment mention anywhere) and this app only enrolls contacts into existing sequences via API; it never composes per-email content or attachments. This also aligns with cold-email deliverability best practice (raw attachments on a first-touch email increase spam-filter risk). Productthon and Club Sponsorship templates reference the sponsorship package via a hosted link instead of an attachment.
- **D-11:** Both link-referencing templates use a literal `[SPONSORSHIP_LINK]` placeholder for now. Getting a real hosted link (Google Drive/Notion/etc. for the sponsorship deck/prospectus in `tmp/`) is a **manual setup step for the user before any real send** — not a Phase 3 build blocker. Flag this in the phase SUMMARY as an unresolved user-setup item.
- **D-12:** Client Sourcing subject line: `Partner with Product Space UW on Your Next Product Initiative` (Claude's pick — user said to just choose one).
- **D-13 (Phase 4 requirement change, captured here since it surfaced during this discussion):** `REQUIREMENTS.md` QUEUE-03 was updated from "single Approve All button" to per-contact checkboxes (default checked) with both "Approve Selected" and "Approve All" enrolling whatever's checked; unchecked contacts stay `status='drafted'` for a later run rather than being discarded. This is a Phase 4 concern, not implemented in Phase 3, but recorded here for traceability since it changed the requirements doc mid-Phase-3-discussion.

### Claude API failure handling
- **D-14:** Per-contact Haiku failure (timeout, transient API error) uses the **same generic fallback opener** as the sparse-data case (D-07) — one consistent fallback path regardless of cause. The contact still gets a draft and stays in the batch; nothing is silently dropped.
- **D-15:** One retry before falling back — mirrors Apollo's own 429-backoff pattern (CLAUDE.md: exponential backoff, max 3 retries) but lighter, since Haiku failures are usually transient. Avoids over-triggering fallback on a single blip without stalling the batch on a dead API.
- **D-16:** If a high fraction of the batch fails (e.g., >50% — exact threshold left to planner/implementation, not user-specified), surface a plain-language error banner ("AI personalization is unavailable right now — drafts are using generic openers"), mirroring the existing Apollo error-banner convention (401/403/429 → banner, never a traceback). Below that threshold, per-contact fallback is silent — no banner for occasional individual failures.

### Claude's Discretion
- Exact numeric threshold for D-16's "high fraction of batch fails" banner trigger — planner/implementer picks a reasonable value (e.g., >50%) since the user did not specify one.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Apollo / sequencing constraints
- `apollo.MD` — confirms no attachment-related endpoints or fields anywhere in the Apollo API surface (source of D-10)
- `spec.MD` — original pipeline spec; no attachment handling described
- `CLAUDE.md` "Key API Notes (Apollo.io)" — sequences are pre-built in Apollo UI, app only enrolls; 429 retry pattern (source of D-15's mirrored backoff logic)

### AI / LLM layer
- `CLAUDE.md` "AI / LLM Layer" — `claude-haiku-4-5-20251001` model choice, `anthropic>=0.117.0` SDK, ~500 input / ~50-60 output token budget per contact (~$0.04/campaign) — informs D-08's length target

### Requirements
- `.planning/REQUIREMENTS.md` — PERS-01 (opening line + draft assembly, this phase's core requirement); QUEUE-03 (updated during this discussion — see D-13)

### Prior phase decisions this phase builds on
- `.planning/phases/02-contact-discovery/02-CONTEXT.md` — D-05 (Apollo has no credit-balance endpoint, cost estimate only), the two-stage Find/Enrich pattern this phase's D-01 deliberately does NOT replicate, and the `st.dataframe`/error-banner conventions this phase extends
- `.planning/phases/01-foundation/01-CONTEXT.md` — `prospect` table status enum (`found → selected → enriched → drafted → approved → sequenced`) that D-04 writes into
- `pages/discovery_page.py` — the page D-02 extends with the draft preview
- `db/prospects.py` — existing `insert_enriched`/status-write patterns to follow for the new `drafted` status write

### Template source content
- `tmp/Product Space UW — Sponsorship Prospectus.docx` — source content for the Club Sponsorship template body (org stats, sponsorship tiers, benefits) — see `<specifics>` for the assembled template text
- `tmp/Sponsorship Deck - Presentation.pdf`, `tmp/UW PS Portfolio Brochure (Spring).pdf` — the actual documents that need a hosted link per D-11 before real sends

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apollo/client.py`, `db/prospects.py` — typed `(status, message)` / defensive `.get()` patterns from Phase 2 should extend to the new Claude API client function
- `pages/discovery_page.py` — Task 1/2 of Plan 02-04 already established the session-state result pattern (`st.session_state.enrich_result`) this phase's draft data should follow (e.g., `st.session_state.draft_result`)
- `pages/health_page.py` — `st.error`/`st.warning`/`st.info` banner conventions to reuse for D-16's high-failure-rate banner

### Established Patterns
- API keys read via `st.secrets`, never logged — applies identically to `ANTHROPIC_API_KEY`
- Never call `st.stop()` on a failure — inputs/buttons stay usable (Phase 2 pattern, D-16's banner should follow the same non-blocking convention)

### Integration Points
- **New dependency:** `anthropic` package is not yet in `requirements.txt` — must be added (CLAUDE.md pins `anthropic>=0.117.0`)
- Draft generation reads contacts at `status='enriched'` (written by Phase 2's `insert_enriched`) and writes `status='drafted'` — the next status step in the existing enum, ready for Phase 4 to query

</code_context>

<specifics>
## Specific Ideas

Exact per-path email templates (finalized during this discussion). `[First Name]` and `[Company]` are Apollo-sourced merge fields; `{opening_line}` is the Claude Haiku-generated sentence; `[SPONSORSHIP_LINK]` is a placeholder per D-11.

### Productthon Sponsorship
```
Subject: Sponsorship Opportunity — UW Product Space: The Product Games (Productthon)

Hello [First Name]!

{opening_line}

I hope this email finds you well! My name is Yash Kulkarni, and I am reaching out on behalf of Product Space UW, the premier product management and tech community at the University of Washington, affiliated with the Foster School of Business.

We are currently gearing up for our annual competition, The Product Games — a one-day product-thon blending the strategy of a case competition with the implementation of a hackathon. During the event, top UW students tackle a real-world innovation challenge, research product opportunities, build MVPs using AI tools, and pitch their solutions to a panel of expert judges.

Given [Company]'s leadership in technology and innovation, we would love to feature you as an official sponsor for the event.

Here's an outline of what Product Space UW can offer you:
- Direct Recruiting Access: Access to our comprehensive resume book and exclusive networking opportunities with participants.
- Brand Visibility: Company logos featured on our website, marketing collateral, and social media channels.
- Custom Challenges & Mentorship: Opportunities to provide the official event prompt, send company judges/mentors, or participate in a fireside chat.

Here's our sponsorship package with general information and sponsorship breakdowns: [SPONSORSHIP_LINK]. Would you be open to a brief 10-minute call this week to discuss how we can tailor a package that aligns with [Company]'s recruiting and branding goals?

Thank you so much for your time and support of student innovation!

Best regards,
Yash Kulkarni
Director of Internal, Product Space at the University of Washington
```

### Club Sponsorship
```
Subject: Partner with Product Space UW — [Company] Annual Sponsorship

Hello [First Name]!

{opening_line}

I hope this email finds you well! My name is Yash Kulkarni, and I am reaching out on behalf of Product Space UW, the premier product management and tech community at the University of Washington, affiliated with the Foster School of Business, with chapters at UCLA, Stanford, UPenn, UC Berkeley, and more.

Our community includes 11 exec members, 45 core members, and 250+ students across the wider community, spanning majors like Computer Science, Informatics, Human-Centered Design & Engineering, Data Science, Engineering, Business, Economics, and Design. Throughout the year, we ship real projects with company partners, host workshops and speaker symposiums, and run recruiting events for our members.

Given [Company]'s leadership in technology and innovation, we'd love to explore an annual sponsorship partnership. Here's what Product Space UW sponsors receive:
- Recruiting Pipeline: An opt-in resume book updated each quarter, curated introductions based on your role criteria, and event RSVPs with attendee skill tags.
- Brand & Thought Leadership: Logo placement on our website, slides, and printed materials, plus speaker slots (tech talks, workshops, panels) and social/newsletter features.
- Project Delivery: A dedicated 5-7 student team (PM/design/eng mix) with a faculty or alumni advisor, weekly standups, and a final report/prototype/hand-off with a sponsor debrief.

Here's our sponsorship prospectus with our full tier breakdown: [SPONSORSHIP_LINK]. Would you be open to a brief 10-minute call this week to discuss a partnership that aligns with [Company]'s recruiting and branding goals?

Thank you so much for your time and support of student innovation!

Best regards,
Yash Kulkarni
Director of Internal, Product Space at the University of Washington
```

### Client Sourcing
```
Subject: Partner with Product Space UW on Your Next Product Initiative

Hi [First Name],

{opening_line}

Have a feature idea or internal product initiative that keeps getting pushed down the roadmap?

We are Product Space UW, a branch of the national Product Space organization that has chapters at UCLA, Stanford, UPenn, UC Berkeley, and more!

At Product Space UW, we help companies like yours move those projects forward—by pairing you with a dedicated team of product-minded students from the University of Washington. Our teams are made up of ambitious individuals from various backgrounds such as computer science, design, engineering, informatics, and finance, and they are eager to apply their skills to real-world challenges and deliver tangible impact.

The value for you:
- Fresh, diverse perspectives on your product or process
- Momentum on a project that you've been wanting to tackle
- A meaningful way to give back by mentoring the next generation of product leaders

We've worked with companies such as Amazon, Microsoft, and Refer.me on user research, competitor analysis, product documentation, prototyping, and more, and we would love to bring our experience and passion to you and your team! This could be a great way to de-risk an idea, test a new feature, or explore improvements without pulling your team off core priorities.

If this opportunity sounds interesting, please let us know and we can schedule a 15-minute call to explore whether we'd be a good fit!

Best regards,
Yash Kulkarni
Director of Internal, Product Space at the University of Washington
```

</specifics>

<deferred>
## Deferred Ideas

- **Real hosted link for the sponsorship package/prospectus** — currently a `[SPONSORSHIP_LINK]` placeholder (D-11). Not a phase — a manual user action needed before any real campaign send. Flag prominently in the Phase 3 SUMMARY's "User Setup Required" section.

</deferred>

---

*Phase: 3-AI Personalization*
*Context gathered: 2026-09-17*
