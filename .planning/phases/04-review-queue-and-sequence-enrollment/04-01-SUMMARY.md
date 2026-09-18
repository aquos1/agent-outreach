---
phase: 04-review-queue-and-sequence-enrollment
plan: 01
subsystem: ui
tags: [streamlit, sqlite, review-queue]

# Dependency graph
requires:
  - phase: 03-ai-personalization
    provides: status='drafted' prospects with opening_line/first_name/draft_source, PATH_TEMPLATES + assemble_email()
provides:
  - Review Queue page (pages/review_queue_page.py) registered in app.py nav
  - get_drafted_by_path() query in db/prospects.py — the QUEUE-01 source query for the rest of Phase 4
  - template_override table in db/schema.py (empty this plan — populated by 04-02's template editor)
  - title/last_name columns on prospect (additive migration)
affects: [04-02, 04-03, 04-04, 04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Manual st.columns row loop (not st.dataframe) for a table that needs per-row interactive cells in a later plan"
    - "cur.description-driven dict zip for a read query, matching dedup_filter's connection lifecycle"

key-files:
  created: [pages/review_queue_page.py]
  modified: [db/schema.py, db/prospects.py, app.py, tests/test_schema.py, tests/test_prospects.py]

key-decisions:
  - "Select/Status cells in the queue row are rendered as blank st.write(\"\") placeholders this plan, with an inline comment naming 04-04 as the plan that fills them with checkbox/badge widgets"
  - "template_override table is created but left unpopulated this plan — get_template()/save_template_override() land in 04-02"

patterns-established:
  - "get_drafted_by_path() is the one query every later Phase 4 plan reads from for the queue's row set"

requirements-completed: [QUEUE-01, QUEUE-02]

# Metrics
duration: ~25min
completed: 2026-09-17
---

# Phase 04 Plan 01: Queue Data Layer + Review Queue Page Summary

**Review Queue page reading `status='drafted'` prospects via a new `get_drafted_by_path()` query, rendered as a manual `st.columns` table with per-row draft-preview expanders, plus the `title`/`last_name`/`template_override` schema additions the rest of Phase 4 depends on.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed
- **Files modified:** 6 (2 new test additions to existing files, 2 schema/data-layer files, 1 new page, 1 nav registration)

## Accomplishments
- A teammate can open "Review Queue" from the left nav, see a path selector defaulted to Club Sponsorship, and see every drafted contact for that path with Name/Company/Title and a "View draft" expander showing the full assembled email
- `db/prospects.py::get_drafted_by_path()` is now the single source query every remaining Phase 4 plan (04-02 through 04-06) will read from
- Schema carries `title`, `last_name`, and the new `template_override` table after a single idempotent boot — no further schema migrations needed anywhere else in Phase 4 (per the plan's stated intent)

## Task Commits

Each task was committed atomically (Task 1 followed the RED/GREEN TDD cycle per its `tdd="true"` marker):

1. **Task 1 RED: failing tests for queue data layer** - `ddbf2e8` (test)
2. **Task 1 GREEN: title/last_name columns, template_override table, get_drafted_by_path()** - `bee9cd1` (feat)
3. **Task 2: Review Queue page + nav registration** - `1fa3357` (feat)

## Files Created/Modified
- `db/schema.py` - Added `template_override` table (brand-new, `CREATE TABLE IF NOT EXISTS`, not in `_NEW_COLUMNS`) and `title`/`last_name` additive columns via `_NEW_COLUMNS`
- `db/prospects.py` - `insert_enriched` now persists `title`/`first_name`/`last_name`; new `get_drafted_by_path(path_slug, db_path=...)` returns plain dicts of every `status='drafted'` row for a path
- `pages/review_queue_page.py` (new) - Path selector (D-11, `index=0`), manual `st.columns` queue table (D-10), per-row `st.expander` + `assemble_email()` draft preview, neutral `st.info` empty state, never hard-stops
- `app.py` - Registered `"Review Queue"` nav entry after `"Discovery"`
- `tests/test_schema.py` - Extended idempotency assertion + added `test_template_override_roundtrip`; extended migration assertion for `title`/`last_name`
- `tests/test_prospects.py` - Added `test_insert_enriched_persists_title_and_names`, `test_get_drafted_by_path`, `test_get_drafted_by_path_empty`

## Decisions Made
- Followed the plan's explicit instruction to leave the Select and Status queue-row cells as blank `st.write("")` placeholders this plan (checkbox/badge widgets are 04-04's scope) — matches the plan's own `<action>` step 10 wording exactly, not a deviation.
- No new deviations beyond what the plan specified.

## Deviations from Plan

None — plan executed exactly as written. One environment note (not a deviation): this worktree has no local `.venv`; `.venv` lives at the main repo root (`/Users/yashpersonal/outreach-agent/.venv`, gitignored) and was invoked via absolute path (`/Users/yashpersonal/outreach-agent/.venv/bin/python3.13`) for all test/compile/smoke-test commands, per 04-RESEARCH.md Pitfall 4's guidance to always use the pinned `python3.13` interpreter (never the bare `python3` symlink).

## Issues Encountered
- A docstring sentence in `pages/review_queue_page.py` originally contained the literal substring `st.stop()` (in prose, not code), which the Task 2 acceptance-criteria grep (`grep -c "st.stop()"` expecting `0`) flagged as a false positive. Reworded the sentence to describe the same "never hard-stops" behavior without the literal substring. No functional change.

## User Setup Required

None — no external service configuration required. (A local `.streamlit/secrets.toml` with dummy values was created transiently in this worktree only, to smoke-test `streamlit run app.py`; it is gitignored and was never committed.)

## Next Phase Readiness
- `get_drafted_by_path()`, the `template_override` table, and the Review Queue page skeleton are all in place for 04-02 (template editor) to build on directly — no schema rework needed.
- The commented placeholder blocks in `pages/review_queue_page.py` (template editor section, Select/Status cells) are intentional hooks for 04-02/04-04, not stubs left unresolved by mistake.

## Self-Check: PASSED

- FOUND: pages/review_queue_page.py
- FOUND: db/prospects.py (get_drafted_by_path present)
- FOUND: db/schema.py (template_override, title, last_name present)
- FOUND commit ddbf2e8
- FOUND commit bee9cd1
- FOUND commit 1fa3357
- Full test suite: 28 passed, 0 failed

---
*Phase: 04-review-queue-and-sequence-enrollment*
*Completed: 2026-09-17*
