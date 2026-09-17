---
phase: 03-ai-personalization
plan: 03
subsystem: database
tags: [sqlite, migration, schema, dedup-registry]

# Dependency graph
requires:
  - phase: 03-ai-personalization (plan 01)
    provides: pinned anthropic SDK, ANTHROPIC_API_KEY boot gate, Wave 0 RED tests for schema migration (test_column_migration_idempotent) and update_draft (test_update_draft_writes_status_drafted)
provides:
  - "db/schema.py: idempotent ALTER TABLE column migration (_NEW_COLUMNS, _migrate_columns) applied on every ensure_schema() boot"
  - "db/prospects.py: update_draft() write function persisting opening_line/draft_source/first_name and advancing status to 'drafted'"
affects: [03-ai-personalization plan 04 (discovery_page.py draft-chaining), phase-04-review-enrollment (Review Queue reads opening_line/draft_source/first_name)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive-only schema migration: ALTER TABLE ADD COLUMN guarded by catching sqlite3.OperationalError and checking for 'duplicate column name' in str(e); everything else re-raised"
    - "update_draft follows insert_enriched's exact connect/try-finally shape and keys writes on apollo_person_id (the Apollo-stable id), not the internal autoincrement id"

key-files:
  created: []
  modified: [db/schema.py, db/prospects.py]

key-decisions:
  - "Migration runs unconditionally inside ensure_schema()'s existing try block (after VIEW_DDL, before commit) rather than as a separate opt-in call, so every app boot self-heals a pre-Phase-3 prospect table without a manual migration step"
  - "first_name is written to a dedicated column (not derived by splitting the name column) per RESEARCH.md Pitfall 2, so Phase 4's Review Queue has a reliable source after a fresh session"

patterns-established:
  - "Schema evolution against a populated SQLite db: CREATE TABLE IF NOT EXISTS never retrofits columns — always pair DDL additions with an ALTER TABLE migration step guarded against duplicate-column errors"

requirements-completed: [PERS-01]

# Metrics
duration: 12min
completed: 2026-09-16
---

# Phase 03 Plan 03: SQLite Draft Persistence Summary

**Idempotent ALTER TABLE migration adds opening_line/first_name/draft_source to the existing prospect table, plus a parameterized update_draft() that advances a contact to status='drafted'.**

## Performance

- **Duration:** 12 min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- `ensure_schema()` now retroactively migrates `opening_line`, `first_name`, and `draft_source` columns onto any pre-existing `prospect` table without dropping/recreating it or losing rows, and remains safe to call repeatedly on every app boot
- `db/prospects.py` gained `update_draft()`, a single parameterized UPDATE keyed on `apollo_person_id` that writes the AI-generated opening line, its source (`'ai'`/`'fallback'`), and first name, and advances the contact's status to `'drafted'`

## Task Commits

1. **Task 1: Add an idempotent column migration to ensure_schema()** - `1a0603f` (feat)
2. **Task 2: Add update_draft() to db/prospects.py** - `e8db936` (feat)

_Note: SUMMARY.md and this metadata are committed separately by the orchestrator's post-wave merge; STATE.md/ROADMAP.md are not touched by this worktree agent._

## Files Created/Modified
- `db/schema.py` - Added `_NEW_COLUMNS`, `_migrate_columns(conn)`, wired into `ensure_schema()` before `conn.commit()`; updated module docstring
- `db/prospects.py` - Added `update_draft(prospect_id, opening_line, source, first_name=None, db_path="db/outreach.db")`

## Decisions Made
- Migration step placed inside the existing `ensure_schema()` try block (not a separate function callers must remember to invoke), preserving the single-commit, connect/try/finally lifecycle already established in Phase 1/2
- `update_draft` keys its WHERE clause on `apollo_person_id`, matching what `insert_enriched` stores and what the caller's raw Apollo match dict carries as `id` — never the internal `id` primary key

## Deviations from Plan

None - plan executed exactly as written. One implementation-detail adjustment made proactively during Task 1: an early docstring wording for `_migrate_columns` included the literal phrase `"duplicate column name"` in a comment, which caused the acceptance criterion's `grep -c 'duplicate column name'` check to count 2 occurrences instead of the required 1 (the code check plus the docstring). Reworded the docstring to avoid the literal phrase while keeping the same explanation, so the grep check (which verifies the exception filter is present in executable code, not decorative text) passes at exactly 1. This is a self-caught verification-criteria fix within Task 1, not a deviation from the plan's intent.

## Issues Encountered

`db/outreach.db` is gitignored and does not exist in this fresh git worktree (it holds no rows here, unlike the plan's assumption of "11 real rows" on the primary development machine's local db file). Ran `ensure_schema()` against the real `db/outreach.db` path as instructed — it created/migrated a fresh local db with 0 pre-existing rows, so the "existing rows survived" acceptance criterion could not be exercised against real data in this isolated environment. The equivalent guarantee (a pre-existing populated `prospect` table survives migration with all rows intact) is verified by `tests/test_schema.py::test_column_migration_idempotent`, which synthesizes a pre-Phase-3 table, inserts a row, runs `ensure_schema()` twice, and asserts both the new columns exist and the row count is unchanged — this test passes. `pytest tests/test_schema.py tests/test_prospects.py -q` is green (7 passed). `tests/test_personalization.py` fails with `ModuleNotFoundError: No module named 'personalization'` — expected, since that module is owned by sibling plan 03-02 (personalization/generator.py, personalization/templates.py) executing concurrently in a separate worktree and out of scope for this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `db/schema.py` and `db/prospects.py` are ready for Plan 03-04 to chain draft generation + persistence into the Discovery page's "Enrich & Continue" handler
- Phase 4's Review Queue can query `opening_line`, `draft_source`, and `first_name` directly off `prospect` rows with `status='drafted'` once Plan 03-04 wires the caller
- No blockers

---
*Phase: 03-ai-personalization*
*Completed: 2026-09-16*
