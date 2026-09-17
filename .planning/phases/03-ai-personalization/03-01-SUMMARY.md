---
phase: 03-ai-personalization
plan: 01
subsystem: testing
tags: [anthropic, pytest, sqlite-migration, red-tests, streamlit-secrets]

# Dependency graph
requires:
  - phase: 02-contact-discovery
    provides: prospect table (status='enriched'), insert_enriched() write pattern, tests/conftest.py fixture conventions
provides:
  - anthropic==1.6.0 pinned and installed, importable
  - ANTHROPIC_API_KEY documented in .streamlit/secrets.toml.example and gated at boot in app.py
  - mock_anthropic_message factory fixture in tests/conftest.py
  - Full Wave 0 RED test suite: tests/test_personalization.py (6 tests), plus extensions to tests/test_prospects.py and tests/test_schema.py
affects: [03-02-personalization-generator, 03-03-schema-and-persistence, 03-04-discovery-page-integration]

# Tech tracking
tech-stack:
  added: ["anthropic==1.6.0 (transitively pulls httpx2>=2.0.0,<3, not httpx)"]
  patterns: ["Typed-tuple never-raise Anthropic client call (mirrors apollo/client.py)", "Deferred in-test-body imports for RED-collectible tests"]

key-files:
  created:
    - tests/test_personalization.py
  modified:
    - requirements.txt
    - .streamlit/secrets.toml.example
    - app.py
    - tests/conftest.py
    - tests/test_prospects.py
    - tests/test_schema.py

key-decisions:
  - "anthropic==1.6.0's error classes (APIConnectionError, APITimeoutError, RateLimitError) are typed against httpx2.Request/httpx2.Response, not httpx -- confirmed live against the installed SDK and PyPI's published requires_dist. Test fixtures import httpx2 directly instead of httpx."
  - "test_api_failure_triggers_fallback uses an internal loop over three error-constructing closures instead of @pytest.mark.parametrize, so pytest --collect-only reports exactly 6 test IDs in tests/test_personalization.py as the plan's acceptance criteria require (parametrize would have expanded to 8)."

patterns-established:
  - "Pattern 1: Fake external-SDK client objects (not real anthropic.Anthropic()) with a recorder .messages.create(**kwargs) -- mirrors this repo's requests-mocking convention from tests/test_apollo_client.py, applied to the Anthropic SDK."

requirements-completed: []  # PERS-01 is a multi-plan requirement; full completion happens across 03-02/03-03/03-04. This plan lands the RED harness only.

duration: 45min
completed: 2026-09-17
---

# Phase 3 Plan 1: Anthropic SDK Install + Wave 0 RED Test Harness Summary

**Pinned anthropic==1.6.0 with a fail-closed ANTHROPIC_API_KEY boot gate in app.py, plus the complete Wave 0 RED test suite (mock_anthropic_message fixture + 6 tests in tests/test_personalization.py + 2 extended tests) that gives every downstream Phase 3 plan a sub-10-second automated feedback signal.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-09-16T23:05:00-07:00 (approx, base commit cb802d7)
- **Completed:** 2026-09-16T23:18:49-07:00
- **Tasks:** 2
- **Files modified:** 6 modified, 1 created

## Accomplishments
- `anthropic==1.6.0` installed and pinned in `requirements.txt`, matching the exact-`==` convention already used for `streamlit`/`requests`/`dnspython`
- `app.py` fails closed with a plain-language banner (no traceback) when `ANTHROPIC_API_KEY` is absent, mirroring the existing `APOLLO_API_KEY` gate exactly
- Full Wave 0 RED harness lands: `mock_anthropic_message` fixture, 6 named tests in `tests/test_personalization.py` covering grounding, sparse-title fallback, API-failure fallback, output-cleanup, per-path template assembly, and the D-16 fallback-fraction threshold; plus `test_update_draft_writes_status_drafted` and `test_column_migration_idempotent`
- All 8 new RED tests fail for the correct reason (missing implementation: `ModuleNotFoundError`, `ImportError`, or a missing-column assertion) — never a collection error
- Zero regressions: all 10 pre-existing Phase 1/2 tests (`test_apollo_client.py`, `test_discovery_logic.py`, `test_dns_checks.py`) still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin and install the anthropic SDK, add ANTHROPIC_API_KEY to the secrets example and the app.py boot gate** - `b3ba777` (feat)
2. **Task 2: Add the mock_anthropic_message fixture and the full Wave 0 RED test suite** - `a37bff9` (test)

**Plan metadata:** (this commit) - `docs: complete plan`

## Files Created/Modified
- `requirements.txt` - added `anthropic==1.6.0` as a fourth exact-pinned dependency
- `.streamlit/secrets.toml.example` - added `ANTHROPIC_API_KEY = "your-anthropic-api-key"` placeholder
- `app.py` - added `anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")` read + fail-closed `st.error`/`st.stop()` gate, updated module docstring
- `tests/conftest.py` - added `_FakeAnthropicMessage` class + `mock_anthropic_message` factory fixture (mirrors `_FakeResponse`/`mock_requests_response`)
- `tests/test_personalization.py` (new, 204 lines) - 6 RED tests: `test_prompt_excludes_industry_and_seniority`, `test_sparse_title_triggers_fallback`, `test_api_failure_triggers_fallback`, `test_generate_opening_line_strips_quotes_and_whitespace`, `test_assemble_email_per_path`, `test_fallback_fraction_threshold`
- `tests/test_prospects.py` - added `test_update_draft_writes_status_drafted`
- `tests/test_schema.py` - added `test_column_migration_idempotent`

## Decisions Made
- Used `httpx2` (not `httpx`) to construct `anthropic.APIConnectionError`/`APITimeoutError`/`RateLimitError` test fixtures, since the actually-installed, plan-pinned `anthropic==1.6.0` requires `httpx2>=2.0.0,<3` as a hard dependency for its error classes — confirmed against both the local install and PyPI's published `requires_dist` for that exact version. See Deviations below.
- Rewrote the API-failure test as a single function with an internal loop over three error-constructing closures instead of `@pytest.mark.parametrize`, to satisfy the plan's exact acceptance criterion of 6 collected test IDs in `tests/test_personalization.py` (parametrize would have expanded to 8 collected items, breaking the `-eq 6` check).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected httpx vs. httpx2 dependency assumption for Anthropic SDK error construction**
- **Found during:** Task 2 (writing `test_api_failure_triggers_fallback`)
- **Issue:** 03-RESEARCH.md's Pattern/task text assumed `httpx` is importable as the Anthropic SDK's HTTP dependency ("`httpx` is an `anthropic` dependency and is importable"). Live investigation showed `anthropic==1.6.0`'s actual PyPI `requires_dist` pins `httpx2>=2.0.0,<3` (published by the `pydantic` GitHub org, `github.com/pydantic/httpx2`) as a hard, non-extra dependency — not `httpx`. The SDK's `APIConnectionError`, `APITimeoutError`, and `RateLimitError` constructors are typed against `httpx2.Request`/`httpx2.Response`. Constructing them with real `httpx.Request`/`httpx.Response` objects as originally planned would have been a type mismatch (though Python's duck typing may have tolerated it at runtime, it does not match the SDK's actual documented contract for this pinned version).
- **Fix:** Imported and used `httpx2` (already transitively installed alongside `anthropic==1.6.0`, confirmed present and importable) to construct the three test error fixtures. Verified all three constructors work with `httpx2.Request`/`httpx2.Response` against the actually-installed SDK before writing the test assertions.
- **Files modified:** `tests/test_personalization.py`
- **Verification:** `python3 -m pytest tests/test_personalization.py::test_api_failure_triggers_fallback -q` fails with `ModuleNotFoundError: No module named 'personalization'` (correct RED reason, not a `TypeError` from a bad SDK error construction)
- **Committed in:** `a37bff9` (Task 2 commit)

**2. [Rule 1 - Bug] Avoided pytest.mark.parametrize to match the exact 6-test-ID acceptance criterion**
- **Found during:** Task 2, running the plan's own automated verify command
- **Issue:** The plan's action text described `test_api_failure_triggers_fallback` as parametrized over three exception types, and the plan's acceptance criteria simultaneously require `pytest tests/test_personalization.py --collect-only -q | grep -c '::test_'` to equal exactly 6. Using `@pytest.mark.parametrize` on that one function produces 3 separate collected node IDs (`[<lambda>0]`, `[<lambda>1]`, `[<lambda>2]`), yielding 8 total collected items in the file and failing the plan's own `-eq 6` check.
- **Fix:** Rewrote the test as a single, non-parametrized function that loops internally over three error-constructing closures, asserting the fallback behavior for each in turn within one test body. This satisfies both the plan's narrative intent (three failure modes exercised) and its literal, contractual acceptance criterion (exactly 6 test IDs).
- **Files modified:** `tests/test_personalization.py`
- **Verification:** `test "$(python3 -m pytest tests/test_personalization.py --collect-only -q -v 2>/dev/null | grep -c '::test_')" -eq 6` passes
- **Committed in:** `a37bff9` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bug fixes, both Rule 1)
**Impact on plan:** Both fixes were necessary to make the RED tests collectible and correct against the actually-installed, plan-pinned `anthropic==1.6.0` SDK. No scope creep — no new functionality was added beyond what the plan specified; these were corrections to match the real SDK's contract and the plan's own literal acceptance criteria.

## Issues Encountered
- `pip install anthropic==1.6.0` initially replaced a pre-installed `anthropic==0.84.0` and pulled in `httpx2` (not `httpx`) as a new transitive dependency — this surfaced the httpx/httpx2 discrepancy documented as Deviation 1 above. No blocker: `httpx2` is a legitimate, already-installed transitive dependency of the approved `anthropic==1.6.0` package (Package Legitimacy Audit in 03-RESEARCH.md already approved `anthropic` itself), so no separate package-legitimacy checkpoint was needed for this transitive resolution.
- `pytest` is not on `PATH` directly in this environment; `python3 -m pytest` was used for all verification instead of a bare `pytest` invocation. This does not affect any committed code or test content.

## User Setup Required

**A real `ANTHROPIC_API_KEY` must be added to `.streamlit/secrets.toml` (local) or the Streamlit Community Cloud secrets console (production) before the app will boot.** `app.py` now fails closed with a plain-language banner if this key is missing — this is expected, correct behavior, not a bug. Get a key from console.anthropic.com → Settings → API Keys → Create Key.

No other external service configuration is required by this plan.

## Next Phase Readiness
- Plan 03-02 can now implement `personalization/generator.py` and `personalization/templates.py` against a fully-specified, collectible RED test suite (`tests/test_personalization.py`) — every test currently fails with `ModuleNotFoundError`, the correct Wave 0 state.
- Plan 03-03 can implement `db/prospects.py::update_draft()` and `db/schema.py`'s column migration against `test_update_draft_writes_status_drafted` (currently `ImportError`) and `test_column_migration_idempotent` (currently a missing-column `AssertionError`).
- No blockers. The one open item (D-11's `[SPONSORSHIP_LINK]` placeholder needing a real hosted link before any live send) is a manual user-setup task outside this plan's scope, already flagged in `03-CONTEXT.md`'s Deferred Ideas section for a later plan/session.

---
*Phase: 03-ai-personalization*
*Completed: 2026-09-17*

## Self-Check: PASSED

All claimed files verified present on disk (requirements.txt, .streamlit/secrets.toml.example, app.py, tests/conftest.py, tests/test_personalization.py, tests/test_prospects.py, tests/test_schema.py). Both task commits (`b3ba777`, `a37bff9`) verified present in `git log`.
