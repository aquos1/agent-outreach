---
phase: 02-contact-discovery
plan: 01
subsystem: database
tags: [sqlite, discovery, dedup, tdd, pure-functions]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: db/schema.py's ensure_schema(), contacted_registry view, free_email_domains table
provides:
  - discovery/logic.py — pure free-text to Apollo-filter translation, has_email pre-filter, local cost estimate, path-independent filter builder, PATH_OPTIONS/PATH_CONFIG
  - db/prospects.py — dedup_filter() against contacted_registry, insert_enriched() writing status='enriched' rows
  - tests/test_discovery_logic.py, tests/test_prospects.py — unit coverage for PATH-02, DISC-01, DISC-02, DISC-04, DEDUP-02
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure transform module (discovery/logic.py) with no I/O, mirroring tests/test_dns_checks.py's pure-function test style"
    - "db/prospects.py connection lifecycle (connect/try/finally close) copied exactly from db/schema.py's ensure_schema()"
    - "urllib.parse.urlparse for domain extraction instead of hand-rolled regex (RESEARCH.md Don't Hand-Roll)"
    - "RED-test-before-implementation with import-inside-test-body convention, consistent with existing test files"

key-files:
  created:
    - discovery/__init__.py
    - discovery/logic.py
    - db/prospects.py
    - tests/test_discovery_logic.py
    - tests/test_prospects.py
  modified: []

key-decisions:
  - "company_domain in insert_enriched falls back to the email domain (via _domain_from_email) when organization.website_url is absent, since bulk_match response rows are not guaranteed to carry an organization sub-object"
  - "dedup_filter treats organization.website_url as optional (.get() chains) so a candidate missing an organization key never crashes, only fails to dedup by domain"

patterns-established:
  - "Pure transform functions live in discovery/logic.py, separate from db/prospects.py's CRUD layer and apollo/client.py's network layer — matches the Architectural Responsibility Map in 02-RESEARCH.md"

requirements-completed: [PATH-02, DISC-01, DISC-02, DISC-04, DEDUP-02]

# Metrics
duration: 20min
completed: 2026-07-25
---

# Phase 02 Plan 01: Discovery Logic + Dedup Backend Summary

**Pure free-text-to-Apollo-filter translation, has_email/dedup pre-filters, and local cost estimate — all network-free and RED-first unit tested, with dedup_filter/insert_enriched writing to the existing contacted_registry/prospect schema.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-25T02:25:00Z (approx, session start)
- **Completed:** 2026-07-25T02:45:45Z
- **Tasks:** 3 completed
- **Files modified:** 5 (all new)

## Accomplishments
- Implemented `discovery/logic.py`: `to_filter_list`, `build_search_filters` (path-free), `filter_has_email`, `cost_estimate`, `PATH_OPTIONS`/`PATH_CONFIG` — all pure, no network calls, matching UI-SPEC's exact 3-path labels/order.
- Implemented `db/prospects.py`: `dedup_filter` (id- and domain-level exclusion against `contacted_registry`, respecting the free-email-domain NULL rule) and `insert_enriched` (parameterized-SQL writes with `status='enriched'`).
- Full RED→GREEN TDD cycle: both new test files written first and confirmed to fail with `ModuleNotFoundError`, then implementations made both files green with no regression to the existing 5 Phase-1 tests (11/11 full suite green).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests for discovery logic and dedup** - `a6b1e6a` (test)
2. **Task 2: Implement discovery/logic.py pure transforms** - `038ba74` (feat)
3. **Task 3: Implement db/prospects.py dedup + insert** - `0bf13ba` (feat)

**Plan metadata:** (this SUMMARY commit, made by the orchestrator/worktree-agent commit step)

_Note: Task 2 and Task 3 were TDD tasks (`tdd="true"`); the RED phase for both was already established jointly in Task 1's commit, so no separate per-task RED commit was needed before their GREEN commits._

## Files Created/Modified
- `discovery/__init__.py` - Empty package marker, matches `apollo/`, `db/`, `mailbox/` convention
- `discovery/logic.py` - Pure discovery transforms: `to_filter_list`, `build_search_filters`, `filter_has_email`, `cost_estimate`, `PATH_OPTIONS`, `PATH_CONFIG`, `CONTACT_CAP`
- `db/prospects.py` - `dedup_filter` (contacted_registry query + in-memory exclusion), `insert_enriched` (parameterized prospect INSERT), private `_domain_from_url`/`_domain_from_email` helpers
- `tests/test_discovery_logic.py` - 4 unit tests covering PATH-02/DISC-01/DISC-02/DISC-04
- `tests/test_prospects.py` - 2 unit tests covering DEDUP-02 and enriched-row insert, both against a real `ensure_schema()` database

## Decisions Made
- `insert_enriched`'s `company_domain` falls back to parsing the email's domain when no `organization.website_url` is present in the match row — the plan's `<behavior>`/tests only guaranteed `name`/`organization_name`/`email` on bulk_match-shaped rows, so a URL-only derivation would have left `company_domain` NULL in the common case. This is a Rule 1 (bug-prevention) style defensive addition, not a scope change — it uses the same `.get()`-defensive style mandated throughout the plan.
- `dedup_filter` builds two Python `set`s from a single `SELECT` over `contacted_registry` rather than issuing per-candidate SQL queries, per RESEARCH.md's explicit "in-memory dedup filtering" recommendation (Alternatives Considered table) — candidate sets are capped at ≤100 per search page, so no SQL-side filtering was needed.

## Deviations from Plan

None - plan executed exactly as written. The `company_domain` email-domain fallback described above is an implementation detail within the plan's own instruction to "derive company_domain from the match's org/email defensively via `.get()`" (Task 3's `<action>` explicitly names both org *and* email as sources) — not a deviation from the plan's letter, just the concrete mechanism chosen to satisfy it.

## Issues Encountered

One inline shell-escaping snag when the initial Task 3 commit message included an apostrophe inside a `<<'EOF'` heredoc combined with double-quoted `-m` argument, which the shell mis-parsed. Resolved by rewriting the commit message without apostrophes/percent signs and re-running; no code or test changes were needed.

## User Setup Required

None - no external service configuration required. This plan introduces zero new dependencies and makes no live Apollo calls (all logic is network-free per plan design).

## Next Phase Readiness

- `discovery/logic.py` and `db/prospects.py` are ready to be composed by Plan 02-02/02-03's `pages/discovery_page.py` (the Streamlit Find/Enrich flow) and Plan 02-03's live Apollo client extensions (`apollo/client.py`'s `search_people`/`bulk_match_people`).
- The Wave 0 human-verify checkpoint for exact Apollo response field names (A1/A2 in 02-RESEARCH.md) is still open — `filter_has_email`/`dedup_filter`/`insert_enriched` all defensively use `.get()` so a field-name mismatch degrades gracefully, but the live-verify checkpoint referenced in Plan 02-03 should still run before shipping.
- Full test suite (`pytest -q`) is green at 11/11 with no regressions to Phase 1's existing tests.

---
*Phase: 02-contact-discovery*
*Completed: 2026-07-25*

## Self-Check: PASSED

All created files verified present on disk (discovery/__init__.py, discovery/logic.py,
db/prospects.py, tests/test_discovery_logic.py, tests/test_prospects.py, this SUMMARY.md).
All four commit hashes (a6b1e6a, 038ba74, 0bf13ba, 24df352) verified present in `git log`.
