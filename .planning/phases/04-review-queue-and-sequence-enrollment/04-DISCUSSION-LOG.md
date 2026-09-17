# Phase 4: Review Queue and Sequence Enrollment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-17
**Phase:** 4-Review Queue and Sequence Enrollment
**Areas discussed:** Sequence ID resolution, Bulk template editor, Approve flow & confirmation, Queue page layout

---

## Sequence ID resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcode 3 IDs in secrets.toml | Paste 3 sequence IDs once into `.streamlit/secrets.toml`, same file as APOLLO_API_KEY etc. Zero live API dependency. | ✓ |
| Look up by name via emailer_campaigns/search | App matches sequences by naming convention every run. No config, but fragile — breaks on rename. | |

**User's choice:** Hardcode 3 IDs in secrets.toml.
**Notes:** User initially asked what this decision was even for. Clarified that Apollo's `add_contact_ids` endpoint requires `{sequence_id}` as a URL path parameter — there's no way to enroll into "a sequence" without specifying which one. Without any resolution mechanism, Approve All would create Apollo contacts but be unable to complete enrollment. User then confirmed the hardcode approach, correcting an initial assumption that secrets.toml storage was "temporary" — it's the same permanent config file already used for the other 3 keys.

---

## Bulk template editor

| Option | Description | Selected |
|--------|-------------|----------|
| New Review Queue page | Editor lives on Phase 4's new page, above the drafts list. | ✓ |
| Existing Discovery page's Email Drafts section | Keep it where Phase 3 renders per-contact drafts. | |

**User's choice:** New Review Queue page.
**Notes:** This whole area originated from a todo captured during Phase 3's checkpoint ("Add bulk template editor to Email Drafts page"). During this discussion the user asked where the idea was actually scoped — confirmed via full ROADMAP.md/REQUIREMENTS.md read that it existed nowhere (not Phase 5/Analytics, not REVIEW-01 which is per-contact editing, no backlog entry). User chose to fold it into Phase 4 rather than leave it an orphaned todo or make a formal backlog item.

| Option | Description | Selected |
|--------|-------------|----------|
| Re-assemble all queued drafts immediately | Editing re-runs assemble_email() for every visible contact with the new template. | ✓ |
| Only affects future drafts | Old drafts keep stale template text, no indicator. | |

**User's choice:** Re-assemble all queued drafts immediately.

| Option | Description | Selected |
|--------|-------------|----------|
| Persist permanently | Edited template becomes the new default for that path, survives restarts. | ✓ |
| Reset every run (session-only) | Edits only apply to the current batch. | |

**User's choice:** Persist permanently. Requires new DB-backed template override storage, seeded from `personalization/templates.py`'s `PATH_TEMPLATES` on first read.

| Option | Description | Selected |
|--------|-------------|----------|
| Validate on save, block bad saves | Check merge fields present/correct before allowing save. | ✓ |
| Save anything, no validation | Broken templates can ship silently. | |

**User's choice:** Validate on save, block bad saves.

---

## Approve flow & confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Check the response body per contact | Only Apollo-confirmed IDs marked Enrolled; rest Skipped with reason. | ✓ |
| 200 status code is enough | Mark everyone Enrolled if the HTTP call returns 200. | |

**User's choice:** Check the response body per contact.

| Option | Description | Selected |
|--------|-------------|----------|
| Enroll what succeeds, show per-contact results after | Batch proceeds; per-contact outcomes shown afterward. | ✓ |
| Stop the whole batch on first failure | Halt everyone if one contact fails. | |

**User's choice:** Enroll what succeeds, show per-contact results after.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, confirm dialog with count | "Enroll N contacts into the [Path] sequence?" before firing. | ✓ |
| No, button fires immediately | Matches Discovery page's immediate-fire pattern. | |

**User's choice:** Yes, confirm dialog with count.

---

## Queue page layout

| Option | Description | Selected |
|--------|-------------|----------|
| Table + expander per row | Reuses Phase 3's Discovery page pattern. | ✓ |
| Card list | New pattern, more visual, no expander needed. | |

**User's choice:** Table + expander per row.

| Option | Description | Selected |
|--------|-------------|----------|
| One path at a time, via a selector | Matches template editor 1:1. | ✓ |
| All paths mixed in one list | Single list across all paths, needs separate template-editor path selector. | |

**User's choice:** One path at a time, via a selector.

| Option | Description | Selected |
|--------|-------------|----------|
| Stays visible with an Enrolled badge | Row remains with green badge, drops out on next reload naturally. | ✓ |
| Disappears from the queue immediately | Enrolled rows vanish right away. | |

**User's choice:** Stays visible with an Enrolled badge.

---

## Claude's Discretion

- Secrets.toml key naming convention for the 3 sequence IDs (SCREAMING_SNAKE_CASE, matching existing keys) — surfaced but not contentious, no separate question needed.

## Deferred Ideas

None — the one scope addition (bulk template editor) was deliberately folded into this phase's decisions rather than deferred; see the Folded Todos section in 04-CONTEXT.md.
