---
phase: 02-contact-discovery
plan: 02
subsystem: api
tags: [apollo, requests, retry-backoff, tdd, python]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: apollo/client.py typed-tuple client contract (check_apollo_health, get_credit_balance)
provides:
  - search_people (DISC-03, 0-credit Apollo contact search)
  - bulk_match_people (DISC-03, 1-credit/match Apollo enrichment)
  - enrich_candidates (batching wrapper, <=10 details/call, fail-fast)
  - _post_with_retry (first codebase 429 exponential-backoff retry helper)
affects: [02-03-discovery-page, 02-04-dedup-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Typed-tuple never-raise Apollo client extension (extends Phase 1's check_apollo_health shape)"
    - "Shared _post_with_retry helper for 429 exponential backoff (max 3 attempts)"
    - "Redundant-field hedge in bulk_match details[] (id + first_name/organization_name/domain, never last_name)"

key-files:
  created: []
  modified:
    - apollo/client.py
    - tests/test_apollo_client.py

key-decisions:
  - "_post_with_retry tracks last_resp separately from network exceptions so a 429-then-network-exception sequence still surfaces the last real 429 response rather than falsely reporting a network failure"
  - "_domain_from_org duplicated locally in apollo/client.py rather than imported from db/prospects.py, per plan instruction, to avoid a same-wave cross-import race with Plan 02-01"
  - "last_name_obfuscated from search results is never passed as last_name in bulk_match details — it is not a usable real surname"

patterns-established:
  - "Pattern 1 (typed-tuple, never-raise): all new Apollo functions follow check_apollo_health's exact shape"
  - "Pattern 3 (batching): _chunk(items, 10) generator + fail-fast on first batch error (D-06)"

requirements-completed: [DISC-03]

# Metrics
duration: 15min
completed: 2026-07-25
---

# Phase 02 Plan 02: Apollo search_people + bulk_match_people + enrich_candidates Summary

**Extended apollo/client.py with search_people (0-credit search), bulk_match_people (1-credit enrichment), and enrich_candidates (<=10-per-call batching), plus the codebase's first 429 exponential-backoff retry helper (_post_with_retry) — all RED-first with mocked-requests tests.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-25T02:47:13Z
- **Tasks:** 3 (RED tests, search_people/_post_with_retry, bulk_match_people/enrich_candidates)
- **Files modified:** 2 (apollo/client.py, tests/test_apollo_client.py)

## Accomplishments
- `search_people` and `bulk_match_people` added to `apollo/client.py`, matching the existing typed-tuple, never-raise, defensive-`.get()` client contract exactly
- `_post_with_retry` implements the CLAUDE.md-mandated 429 exponential backoff (max 3 attempts) — the first retry logic anywhere in the codebase
- `enrich_candidates` batches an arbitrary candidate list into <=10-detail `bulk_match_people` calls, passing redundant `id`+`first_name`+`organization_name`+`domain` fields per the Pitfall 3 hedge, and fails fast on the first batch error (D-06)
- Full test suite green: 9 tests total (5 in `test_apollo_client.py`, including the 4 new RED→GREEN tests, plus 4 unaffected Phase 1 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests for search_people, bulk_match_people, enrich_candidates** - `52cae79` (test)
2. **Task 2: Implement search_people + _post_with_retry** - `263c7b1` (feat)
3. **Task 3: Implement bulk_match_people + enrich_candidates batching** - `47a1de9` (feat)

_TDD gate sequence verified: `test(...)` RED commit (52cae79) precedes both `feat(...)` GREEN commits (263c7b1, 47a1de9)._

## Files Created/Modified
- `apollo/client.py` - added `_post_with_retry`, `search_people`, `bulk_match_people`, `_chunk`, `_domain_from_org`, `enrich_candidates`
- `tests/test_apollo_client.py` - added `test_search_people_error_codes`, `test_search_people_never_raises_on_network`, `test_bulk_match_people_error_codes`, `test_bulk_match_people_batches_of_ten`

## Decisions Made
- `_post_with_retry` returns the last real HTTP response it received even if a later retry attempt raises a network exception, rather than collapsing that case to `None` — this avoids mischaracterizing "got rate-limited twice, then a transient network blip" as a pure network failure when a 429 banner is more accurate.
- `_domain_from_org` is duplicated locally in `apollo/client.py` (not imported from `db/prospects.py`) exactly as the plan specified, since Plan 02-01 creates that module in the same wave and a cross-import would race.
- Confirmed via grep gate that `last_name_obfuscated` (search-result field) is never passed as `last_name` in `bulk_match`'s `details[]` — omitted entirely per the plan's explicit instruction.

## Deviations from Plan

None - plan executed exactly as written. One self-correction during implementation: an initial docstring comment for `enrich_candidates` mentioned "reveal_phone_number" in prose (documenting what NOT to do), which would have failed the plan's own acceptance-criteria grep gate (`grep -n "reveal_phone_number" apollo/client.py` must return nothing). Reworded the docstring before committing so the literal string never appears in the file while preserving the same guidance. This was caught and fixed before commit, so it produced no extra commit or deviation entry beyond this note.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. These functions are exercised entirely via mocked `requests` in this plan; Plan 02-03's human-verify checkpoint is where a live Apollo call first occurs.

## Next Phase Readiness
- `search_people`, `bulk_match_people`, and `enrich_candidates` are ready for `pages/discovery_page.py` (Plan 02-03) to compose into the Find → Enrich session-state flow
- Field-name assumptions (`people`, `matches`, `organization.website_url`, etc.) remain MEDIUM confidence per 02-RESEARCH.md and are gated behind Plan 02-03's human-verify checkpoint against a live Apollo account
- No blockers

---
*Phase: 02-contact-discovery*
*Completed: 2026-07-25*

## Self-Check: PASSED

- FOUND: apollo/client.py
- FOUND: tests/test_apollo_client.py
- FOUND: .planning/phases/02-contact-discovery/02-02-SUMMARY.md
- FOUND commit: 52cae79 (test: RED tests)
- FOUND commit: 263c7b1 (feat: search_people + _post_with_retry)
- FOUND commit: 47a1de9 (feat: bulk_match_people + enrich_candidates)
- FOUND commit: 1d6a2f9 (docs: SUMMARY.md)
