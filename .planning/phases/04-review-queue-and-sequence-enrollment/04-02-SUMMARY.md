---
phase: 04-review-queue-and-sequence-enrollment
plan: 02
subsystem: ui
tags: [streamlit, sqlite, templates, review-queue]

# Dependency graph
requires:
  - phase: 04-review-queue-and-sequence-enrollment (04-01)
    provides: Review Queue page skeleton, get_drafted_by_path(), template_override table (empty)
provides:
  - db/templates_store.py — get_template()/save_template_override() over template_override with PATH_TEMPLATES seed fallback
  - validate_template_fields() + override-aware assemble_email() in personalization/templates.py
  - Template editor section on the Review Queue page (D-03 through D-06, D-14 consequence caption)
affects: [04-03, 04-04, 04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLite upsert via INSERT ... ON CONFLICT(path) DO UPDATE — the one new SQL shape in the codebase, isolated to save_template_override()"
    - "Session-state result dict pattern (template_result) used to survive an st.rerun() so a success banner still shows after the rerun that re-reads the saved override"
    - "Per-slug widget key suffix (tpl_subject_{slug}/tpl_body_{slug}) so Streamlit's key-bound widget state naturally discards unsaved edits when the path selector changes"

key-files:
  created: [db/templates_store.py, tests/test_templates.py]
  modified: [personalization/templates.py, pages/review_queue_page.py]

key-decisions:
  - "validate_template_fields signature takes (subject, body) separately (not a single combined string) matching the plan's locked interface, scanning the combined f'{subject}\\n{body}' text internally"
  - "get_template() never writes a seed row on read (lazy fallback only) — confirmed by test_get_template_falls_back_to_path_templates asserting zero rows in template_override after a read-only view"
  - "assemble_email()'s subject is now formatted with all three merge fields (first_name, company, opening_line), not just company as before — a teammate may legitimately put {first_name} or {opening_line} in a subject line; existing four-argument call sites (discovery_page.py) are unaffected since the additional kwargs default to None"

patterns-established:
  - "get_template()/save_template_override() is the one persistence path every later Phase 4 template-aware render must go through instead of reading PATH_TEMPLATES directly"

requirements-completed: [QUEUE-02]

# Metrics
duration: ~15min
completed: 2026-09-17
---

# Phase 04 Plan 02: Template Editor Summary

**Per-path shared email template editor on the Review Queue page — teammates can now fix a bad template once for a whole path, with merge-field validation blocking bad saves and every visible draft preview updating immediately.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 completed
- **Files modified:** 4 (2 new: `db/templates_store.py`, `tests/test_templates.py`; 2 extended: `personalization/templates.py`, `pages/review_queue_page.py`)

## Accomplishments
- A teammate can open Review Queue, see the current subject/body for the selected path in an editable form above the drafts list, edit it, and click "Save Template"
- Saving with a missing or unknown merge field is blocked with a plain-language warning; the teammate's edits stay in the text fields (widget state is untouched)
- Saving successfully persists the override to `template_override` (survives app restarts, `PATH_TEMPLATES` stays the seed/fallback default) and immediately re-assembles every visible draft preview below with the new template text combined with each contact's existing AI opening line — no stale previews, no page reload
- Switching the path selector discards unsaved edits from the previous path (per-slug widget keys) and loads the newly selected path's own saved/default text
- The editor states plainly that Apollo sends the sequence's own saved paragraph text and only the AI opening line travels from this app (D-14 consequence), so a teammate never assumes an edit here changes what actually sends
- Editing one path's template never touches another path's row (`test_save_template_override_is_path_scoped`)

## Task Commits

Each task was committed atomically (Task 1 followed the RED/GREEN TDD cycle per its `tdd="true"` marker):

1. **Task 1 RED: failing tests for validation, override-aware assembly, templates_store** - `aaf9264` (test)
2. **Task 1 GREEN: validate_template_fields, override-aware assemble_email, templates_store** - `63c7151` (feat)
3. **Task 2: Template editor section on the Review Queue page** - `0ca9d5c` (feat)

## Files Created/Modified
- `tests/test_templates.py` (new) - Nine behaviors: merge-field validation (all-present, missing, subject+body-combined counting, unknown-field rejection), `assemble_email` override kwargs vs. unchanged default, `get_template` seed-fallback (no write-on-read), `save_template_override` upsert round-trip + path scoping
- `personalization/templates.py` - Added `REQUIRED_FIELDS`, `validate_template_fields(subject, body)`, and extended `assemble_email()` with optional `subject_template`/`body_template` kwargs that win over `PATH_TEMPLATES` when supplied; subject now formats against all three merge fields instead of just `company`
- `db/templates_store.py` (new) - `get_template()` (lazy seed-fallback read, never writes on read) and `save_template_override()` (upsert via `ON CONFLICT(path) DO UPDATE`), following `db/prospects.py`'s connection-lifecycle convention
- `pages/review_queue_page.py` - Replaced the 04-01 placeholder block with the full template editor section (subheader, subject/body fields with per-slug keys, helper caption, D-14 consequence caption, Save Template button with pre-write validation, session-state-backed result banner); updated the per-row draft-preview `assemble_email()` call to pass the loaded override text instead of falling through to raw `PATH_TEMPLATES`; updated the module docstring to describe the new template-editor responsibilities

## Decisions Made
- Followed the plan's locked `validate_template_fields(subject, body) -> tuple[bool, str]` signature exactly (two separate string args, not one combined string), matching the interface contract in the plan frontmatter.
- Used a three-way `template_result["error"]` discriminator (`"validation"` / `"save_failed"` / `None`) rather than a boolean, to distinguish which banner style (`st.warning` vs `st.error` vs `st.success`) to render from the single session-state dict, while staying within the plan's `{"error": str | None, "message": str}` shape.
- No new deviations beyond what the plan specified.

## Deviations from Plan

None — plan executed exactly as written. One implementation-detail note (not a deviation): the D-14 consequence caption's exact required substring ("only the personalized opening line is sent from here") had to be kept within a single Python string-literal line rather than split across two adjacent literals, since the acceptance-criteria grep matches per source line, not the runtime-concatenated string. Wording is unchanged from the plan's locked copy — only the line-wrap point moved.

## Issues Encountered
None.

## User Setup Required

None — no external service configuration required. (A local `.streamlit/secrets.toml` with dummy values and a transiently-seeded `db/outreach.db` row were created for a live `streamlit run app.py` smoke test in this worktree only; both are gitignored, were never committed, and were deleted after the smoke test confirmed a 200 response with no tracebacks in the server log.)

## Next Phase Readiness
- `get_template()`/`save_template_override()` and the override-aware `assemble_email()` are the persistence/assembly path every later Phase 4 plan (04-03 through 04-06) should read templates through, rather than `PATH_TEMPLATES` directly.
- The Select/Status queue-row cell placeholders (`row_cols[0].write("")`, `row_cols[4].write("")`) remain intentional hooks for 04-04's checkbox/badge work — untouched by this plan, as expected.
- D-19's accepted tension (paragraph-text edits here don't reach what Apollo actually sends unless manually mirrored into the Apollo sequence editor) is now visible to the teammate via the D-14 consequence caption, ahead of 04-05's human-verify checkpoint.

## Self-Check: PASSED

- FOUND: db/templates_store.py
- FOUND: tests/test_templates.py
- FOUND: personalization/templates.py (validate_template_fields present)
- FOUND: pages/review_queue_page.py (template editor section present)
- FOUND commit aaf9264
- FOUND commit 63c7151
- FOUND commit 0ca9d5c
- Full test suite: 37 passed, 0 failed

---
*Phase: 04-review-queue-and-sequence-enrollment*
*Completed: 2026-09-17*
