---
phase: 04-review-queue-and-sequence-enrollment
plan: 06
subsystem: api
tags: [apollo-api, custom-fields, tdd, reconciliation]

# Dependency graph
requires:
  - phase: 04-03
    provides: apollo/client.py's create_contacts_bulk()/add_contacts_to_sequence(), review/logic.py's map_created_contacts()/build_contact_payloads()/split_enrollment_outcome()
provides:
  - apollo/client.py::_find_custom_field_id(), ensure_custom_field(), update_contact_custom_field() — the full custom-field lifecycle for delivering the AI opening line into Apollo (D-14 through D-18)
  - review/logic.py::split_contacts_by_origin() — created vs existing prospect/contact maps for the D-17 follow-up
affects: [04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Field-id prefix strip (field['id'].split('.', 1)[-1]) is mandatory and load-bearing whenever a GET /fields result is later used as a typed_custom_fields dict key — the two shapes are incompatible and Apollo silently ignores the wrong one"
    - "ensure_custom_field() mirrors db/schema.py's ensure_schema() idempotent-boot convention, but with the external Apollo API as the source of truth instead of a local flag"
    - "_find_custom_field_id/update_contact_custom_field use plain un-retried requests calls (mirroring check_apollo_health's shape) since they are first-use/single-item lookups, not bulk writes; only the field-creation POST goes through _post_with_retry"

key-files:
  created: []
  modified: [apollo/client.py, review/logic.py, tests/test_apollo_client.py, tests/test_review_logic.py]

key-decisions:
  - "Reworded one docstring sentence in _find_custom_field_id (originally named the deprecated 'GET /typed_custom_fields' endpoint literally) to avoid tripping the plan's own acceptance-criteria grep for '/typed_custom_fields' — same false-positive class 04-01/04-03's summaries flagged for st.stop()/_chunk(contacts, 100); no behavior changed"
  - "map_created_contacts() is now a two-line delegate to split_contacts_by_origin() — pure refactor, signature/return type/every 04-03 test unchanged, per the plan's explicit instruction that any required test edit would mean the refactor was wrong"

patterns-established:
  - "split_contacts_by_origin() is the layer 04-04 must call to know which newly-enrolled prospects (existing_map) still need a follow-up update_contact_custom_field() call before their opening line reaches Apollo — never re-derive this from map_created_contacts()'s merged output, which discards the origin distinction"

requirements-completed: [QUEUE-04]

# Metrics
duration: ~25min
completed: 2026-09-17
---

# Phase 04 Plan 06: Custom-Field Lifecycle for AI Opening Line Delivery Summary

**Idempotent Apollo custom-field resolve/create (`_find_custom_field_id`, `ensure_custom_field`) plus a single-contact `PATCH` follow-up (`update_contact_custom_field`), and a `review/logic.py` origin split (`split_contacts_by_origin`) that tells the approve flow which enrolled contacts still need that follow-up — the two pieces that make Phase 3's AI opening line actually reach Apollo instead of staying a review-only preview.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed (both TDD: RED then GREEN)
- **Files modified:** 4 (`apollo/client.py`, `review/logic.py`, `tests/test_apollo_client.py`, `tests/test_review_logic.py`)

## Accomplishments

- `apollo/client.py::_find_custom_field_id()` — idempotent `GET /fields?source=custom` lookup that always strips Apollo's modality prefix (`"contact.<hex>"` → raw hex) before returning an id, with a dedicated regression test (`test_find_custom_field_id_strips_modality_prefix`) pinning the exact gotcha 04-RESEARCH.md flagged as HIGH confidence
- `apollo/client.py::ensure_custom_field()` — find-or-create with a mandatory find-first check (D-18 idempotency): never calls `POST /fields` when the field already exists, and never creates on a real lookup failure (only on the `NOT_FOUND` sentinel), so a transient 401 can't produce a duplicate field
- `apollo/client.py::update_contact_custom_field()` — `PATCH /contacts/{id}` follow-up for the D-17 edge case: contacts `bulk_create` returns in `existing_contacts` are left completely unmodified, so this is the only path that delivers their opening line
- `review/logic.py::split_contacts_by_origin()` — new pure function returning `(created_map, existing_map)`, matched by lowercased email only (never list position); `map_created_contacts()` now delegates to it as a pure refactor with zero behavior change
- Full test suite: 74 passed, 0 failed (60 baseline + 9 Task 1 + 5 Task 2, with 0 modifications to any pre-existing test)

## Task Commits

Each task followed the RED/GREEN TDD cycle per its `tdd="true"` marker:

1. **Task 1 RED: failing tests for custom-field lifecycle functions** - `d010ba8` (test)
2. **Task 1 GREEN: resolve AI opening line custom field id and PATCH follow-up** - `8396bad` (feat)
3. **Task 2 RED: failing tests for split_contacts_by_origin** - `933c65b` (test)
4. **Task 2 GREEN: add split_contacts_by_origin for the D-17 follow-up** - `fe685ad` (feat)

## Files Created/Modified

- `apollo/client.py` - adds `_find_custom_field_id()`, `ensure_custom_field()`, `update_contact_custom_field()`; module docstring extended to name the D-14–D-18 field-lifecycle calls alongside the existing endpoint inventory
- `review/logic.py` - adds `split_contacts_by_origin()`; `map_created_contacts()` refactored to delegate to it
- `tests/test_apollo_client.py` - 9 new tests: the prefix-strip regression guard, NOT_FOUND/error-code branches for `_find_custom_field_id`, reuse/create/propagate-failure/empty-response branches for `ensure_custom_field`, and success/error-code coverage for `update_contact_custom_field`
- `tests/test_review_logic.py` - 5 new tests: origin separation, case-insensitive email matching, unknown-email skip, missing-array degradation, and a regression pin confirming `map_created_contacts()` still merges both origins after the refactor

## Decisions Made

- Followed the plan's reference implementations (04-RESEARCH.md "Personalization Delivery" §3) verbatim for all three `apollo/client.py` functions — signatures confirmed via `inspect.signature` against the interfaces block.
- One non-functional docstring wording adjustment (see Deviations) to avoid a literal-substring grep false positive; no code behavior changed.

## Deviations from Plan

None functional — plan executed exactly as written. One non-functional docstring wording adjustment, same class as 04-01/04-03's flagged false positives:

1. `_find_custom_field_id`'s docstring originally read `` the old `GET /typed_custom_fields` list endpoint `` — reworded to "Apollo's old list-all-custom-fields endpoint (deprecated in favor of this `source`-filtered lookup)" so the acceptance criterion `grep -v '^\s*#' apollo/client.py | grep -c "/typed_custom_fields"` (expecting 0, confirming the deprecated endpoint is never called) doesn't flag prose describing that exact endpoint by name. Verified: grep now returns 0, and all other acceptance-criteria greps (prefix-strip count ≥1, `max_length: 500` count 1, `typed_custom_fields` mention count ≥2) pass at their expected thresholds.

## Issues Encountered

- The worktree had no `.venv` (gitignored, per-checkout) — created a local `.venv` with the system `python3.13` interpreter and installed `requirements.txt`/`requirements-dev.txt` before running any tests, matching the plan's mandated `.venv/bin/python3.13` verification command.

## User Setup Required

None — no external service configuration required. This plan is backend-only (Apollo client functions and a pure reconciliation-layer addition); it produces no user-visible change on its own. 04-04 wires `ensure_custom_field()`'s returned field id and `split_contacts_by_origin()`'s `existing_map` into the Review Queue page's Approve action.

## Next Phase Readiness

- `ensure_custom_field()`, `update_contact_custom_field()`, and `split_contacts_by_origin()` are all in place for 04-04 to call directly: resolve the field id once per session, pass it as `create_contacts_bulk()`'s `opening_line_field_id`, then loop `existing_map` through `update_contact_custom_field()` for the D-17 follow-up.
- No further backend work is needed for the personalization-delivery engine itself; 04-04's job is wiring, not new Apollo calls.
- 04-05's live human-verify checkpoint should still confirm the real `GET /fields` response shape and the field-ID prefix format against this plan's CITED-but-not-live-verified assumption (04-RESEARCH.md §1) before the manual per-sequence dynamic-variable setup.

## Self-Check: PASSED

- FOUND: apollo/client.py (_find_custom_field_id, ensure_custom_field, update_contact_custom_field present)
- FOUND: review/logic.py (split_contacts_by_origin present)
- FOUND: tests/test_apollo_client.py (9 new tests)
- FOUND: tests/test_review_logic.py (5 new tests)
- FOUND commit d010ba8
- FOUND commit 8396bad
- FOUND commit 933c65b
- FOUND commit fe685ad
- Full test suite: 74 passed, 0 failed

---
*Phase: 04-review-queue-and-sequence-enrollment*
*Completed: 2026-09-17*
