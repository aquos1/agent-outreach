---
phase: 01-foundation
plan: 02
subsystem: data-registry
tags: [sqlite, schema, dedup]
dependency-graph:
  requires: [01-01]
  provides: [DEDUP-01-schema, contacted_registry-view]
  affects: [phase-02-discovery-dedup-query]
tech-stack:
  added: []
  patterns:
    - "Idempotent SQLite bootstrap: CREATE TABLE IF NOT EXISTS + DROP VIEW IF EXISTS/CREATE VIEW pair, run via executescript() on every boot"
    - "Free-domain exclusion list seeded as a table (free_email_domains), never hardcoded inline"
key-files:
  created:
    - db/schema.py
  modified:
    - .planning/REQUIREMENTS.md
decisions:
  - "Task 1 and Task 2 committed together (single commit) rather than split: the pre-written RED test test_ensure_schema_idempotent asserts the contacted_registry view exists, so Task 1's own verify command cannot pass without Task 2's VIEW_DDL"
metrics:
  duration: "~15 minutes"
  completed: 2026-07-20
---

# Phase 01 Plan 02: SQLite Dedup Registry Schema Summary

Idempotent SQLite schema bootstrap (`db/schema.py`) delivering DEDUP-01: `prospect`, `email_events`, and `free_email_domains` tables plus the `contacted_registry` dedup view, auto-created on first launch with no manual setup and persisting across restarts.

## What Was Built

`db/schema.py` exports `ensure_schema(db_path: str = "db/outreach.db") -> None`, which:

- Creates the parent directory of `db_path` if missing (SC-3: fresh checkout needs no manual DB setup)
- Runs a static `DDL` string via `conn.executescript()` to create `prospect` (7-value status CHECK constraint, `DEFAULT 'found'`), `email_events` (FK to `prospect(id)`), and `free_email_domains` (seeded via `INSERT OR IGNORE` with gmail.com, outlook.com, yahoo.com, hotmail.com, icloud.com)
- Runs a static `VIEW_DDL` string (`DROP VIEW IF EXISTS` immediately followed by `CREATE VIEW`) to create `contacted_registry`, which exposes `dedupable_domain` — `NULL` when `company_domain` is `NULL` or matches a seeded free-email domain, otherwise the literal company domain — scoped to rows where `apollo_contact_id IS NOT NULL`
- Is idempotent: safe to call on every app boot against the same file with no `sqlite3.OperationalError`
- Uses no f-string/`%`/`+` interpolation into any SQL statement — DDL and VIEW_DDL are static constants (T-02-01 mitigation)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | Idempotent tables, free-email seed, and contacted_registry view | bf3d37a | db/schema.py |

Tasks 1 and 2 were implemented and committed together — see Deviations below.

## Verification

- `python -m pytest tests/test_schema.py -v` — all 3 tests pass (`test_ensure_schema_idempotent`, `test_registry_excludes_free_domains`, `test_persistence_across_reconnect`)
- `grep -v '^#' db/schema.py | grep -c "CREATE TABLE IF NOT EXISTS"` → 3
- `db/schema.py` contains `DROP VIEW IF EXISTS contacted_registry` immediately preceding `CREATE VIEW contacted_registry`
- No f-string/`%`/`+` SQL interpolation found in db/schema.py
- Manual check: `ensure_schema()` against a fresh nested path (`/tmp/sc3check/nested/outreach.db`) auto-creates the parent directory and the DB file, and a second call against the same path does not raise (SC-3)
- `test_persistence_across_reconnect` confirms rows written before a fresh `sqlite3.connect()` remain queryable (SC-4)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - structural] Merged Task 1 and Task 2 into a single commit**
- **Found during:** Task 1 verification
- **Issue:** The plan splits schema work into Task 1 (tables + seed) and Task 2 (contacted_registry view), each with its own commit. However, the RED test `test_ensure_schema_idempotent` (pre-written in 01-01, per plan's `<read_first>` instruction to treat it as already-RED) asserts `SELECT name FROM sqlite_master WHERE type='view' AND name='contacted_registry'` returns a row. This means Task 1's own mandated verify command (`pytest tests/test_schema.py::test_ensure_schema_idempotent ...`) cannot pass without Task 2's `VIEW_DDL` already in place.
- **Fix:** Implemented `DDL` and `VIEW_DDL` together in `db/schema.py` in one pass, then ran and verified against both tasks' acceptance criteria before making a single commit. No behavior differs from what the plan specifies — both DDL blocks are exactly as documented in `01-RESEARCH.md`'s Code Examples section (with the added parent-directory creation per the plan's Task 1 action). Only the task/commit granularity was collapsed.
- **Files modified:** db/schema.py
- **Commit:** bf3d37a

### Test File Changes

None — `tests/test_schema.py` was already fully implemented (not stubbed) when read at the start of this plan; both `test_ensure_schema_idempotent` and `test_persistence_across_reconnect` already contained complete assertions from the 01-01 RED-test-harness plan, and `test_registry_excludes_free_domains` was likewise already fully written. No edits were needed to the test file.

## Requirements Delivered

- **DEDUP-01**: prospect/email_events/free_email_domains tables and the contacted_registry dedup view are created idempotently with no manual setup. Marked complete in `.planning/REQUIREMENTS.md`.
- **SC-3** (auto-created schema, no manual setup): verified manually against a fresh nested path.
- **SC-4** (registry persists across restarts): verified via `test_persistence_across_reconnect`.

(SC-3/SC-4 are roadmap success criteria, not REQUIREMENTS.md checkbox IDs — `requirements mark-complete` reported them `not_found` there; DEDUP-01 was the only matching checkbox ID and was marked complete.)

## Known Stubs

None. `db/schema.py` is fully wired — no placeholder values, no empty stub functions.

## Self-Check: PASSED

- FOUND: db/schema.py
- FOUND: commit bf3d37a
