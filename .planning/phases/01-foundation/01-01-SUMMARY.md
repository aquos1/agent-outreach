---
phase: 01-foundation
plan: 01
subsystem: testing
tags: [pytest, streamlit, sqlite, requests, dnspython, project-scaffold]

# Dependency graph
requires: []
provides:
  - Pinned dependency manifests (requirements.txt, requirements-dev.txt)
  - pytest configuration (pyproject.toml testpaths)
  - Locked Streamlit theme (.streamlit/config.toml)
  - Secrets template (.streamlit/secrets.toml.example) with gitignore protection
  - Package scaffolding (db/, apollo/, mailbox/ __init__.py markers)
  - RED test harness (tests/conftest.py fixtures + 5 failing tests) that Plans 01-02 and
    01-03 must turn green
affects: [01-02-foundation, 01-03-foundation, 01-04-foundation]

# Tech tracking
tech-stack:
  added: [streamlit==1.59.2, requests==2.34.2, dnspython==2.8.0, pytest==9.0.2]
  patterns:
    - "RED test harness: target-module imports live inside test bodies (not module top
      level) so pytest --collect-only succeeds before source modules exist"
    - "conftest.py provides tmp_db_path (temp SQLite file), mock_requests_response
      (fake requests.Response), and mock_dns_txt (monkeypatch dns.resolver.resolve)
      fixtures shared across all Wave 0+ tests"

key-files:
  created:
    - requirements.txt
    - requirements-dev.txt
    - pyproject.toml
    - .streamlit/config.toml
    - .streamlit/secrets.toml.example
    - db/__init__.py
    - apollo/__init__.py
    - mailbox/__init__.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_schema.py
    - tests/test_apollo_client.py
    - tests/test_dns_checks.py
  modified:
    - .gitignore

key-decisions:
  - "Extended pre-existing .gitignore (from an earlier commit) rather than overwriting it,
    adding .pytest_cache/ and an explicit db/outreach.db entry alongside the existing
    secrets/*.db rules"
  - "mailbox/ package name intentionally shadows Python's stdlib mailbox module when the
    project root is on sys.path — this was already specified in 01-01-PLAN.md's interfaces
    section and approved by gsd-plan-checker; not treated as a deviation"

patterns-established:
  - "Pattern: RED tests import target functions inside the test body, never at module top,
    so the whole suite collects cleanly during Wave 0 even though zero source modules exist
    yet. Waves 1-2 turn these green without touching test files."
  - "Pattern: all DNS/HTTP mocking goes through named conftest.py fixtures
    (mock_requests_response, mock_dns_txt) rather than ad hoc monkeypatching per test file."

requirements-completed: [DEDUP-01, SC-1, SC-2]

# Metrics
duration: 4min
completed: 2026-07-20
---

# Phase 01 Plan 01: Foundation Scaffold and RED Test Harness Summary

**Pinned Streamlit/requests/dnspython/pytest dependency manifests, locked theme, gitignored secrets template, and a 5-test RED harness (db/schema, apollo/client, mailbox/dns_checks) that collects cleanly but fails until Plans 01-02/01-03 implement the source modules.**

## Performance

- **Duration:** ~4 min (measured from first to second task commit; environment setup/context loading not included)
- **Started:** 2026-07-20T17:46 (approx, first task commit)
- **Completed:** 2026-07-20T17:48
- **Tasks:** 2/2
- **Files modified:** 14 created, 1 modified

## Accomplishments
- Dependency manifests pinned exactly per RESEARCH.md (streamlit==1.59.2, requests==2.34.2, dnspython==2.8.0, pytest==9.0.2); checkdmarc explicitly excluded per RESEARCH.md deferral
- pytest configured via `pyproject.toml` `[tool.pytest.ini_options]` with `testpaths = ["tests"]`
- Locked Streamlit theme (`.streamlit/config.toml`) matches 01-UI-SPEC.md's `[theme]` block exactly
- `.gitignore` protects secrets and DB files; `.streamlit/secrets.toml.example` committed as a safe placeholder template, real `secrets.toml` never created
- 5-test RED harness collects with `pytest --collect-only` (exit 0) and fails with `pytest -q` (exit 1, expected) — proves the test infrastructure works before any source code exists
- `tests/conftest.py` fixtures (`tmp_db_path`, `mock_requests_response`, `mock_dns_txt`) are ready for Plans 01-02/01-03 to build against

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold, dependency pins, gitignore, and theme** - `76b0ff7` (feat)
2. **Task 2: Test infrastructure and RED test files** - `b416049` (test)

**Plan metadata:** committed separately (this SUMMARY.md + REQUIREMENTS.md, in worktree mode)

## Files Created/Modified
- `requirements.txt` - Pinned runtime deps: streamlit, requests, dnspython
- `requirements-dev.txt` - Pinned pytest for test infra
- `pyproject.toml` - pytest testpaths/addopts config
- `.gitignore` - Extended with `.pytest_cache/` and `db/outreach.db` (existing secrets/*.db rules preserved)
- `.streamlit/config.toml` - Locked theme tokens from 01-UI-SPEC.md
- `.streamlit/secrets.toml.example` - Placeholder secrets template (committed; real secrets.toml is gitignored and never created)
- `db/__init__.py`, `apollo/__init__.py`, `mailbox/__init__.py` - Empty package markers for downstream plans
- `tests/__init__.py` - Empty package marker
- `tests/conftest.py` - `tmp_db_path`, `mock_requests_response`, `mock_dns_txt` fixtures (76 lines)
- `tests/test_schema.py` - `test_ensure_schema_idempotent`, `test_registry_excludes_free_domains`, `test_persistence_across_reconnect`
- `tests/test_apollo_client.py` - `test_check_apollo_health` (401/403/200+is_logged_in cases)
- `tests/test_dns_checks.py` - `test_check_spf_dmarc_dkim` (SPF/DMARC present/absent, DKIM unknown-on-miss)

## Decisions Made
- Preserved and extended the pre-existing `.gitignore` (committed earlier in project history) instead of overwriting it, to avoid dropping any prior rules while still satisfying the plan's explicit `.pytest_cache/`/`db/outreach.db` requirements.
- Confirmed via a quick interpreter check that the project's `mailbox/` package shadows Python's stdlib `mailbox` module when the project root is first on `sys.path` (as it is under `pytest`/`streamlit run` from the repo root). This naming was explicitly specified in the plan's `<interfaces>` block and already approved by gsd-plan-checker, so it was implemented as specified rather than treated as a deviation — flagging here for visibility to downstream plans.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The worktree's initial HEAD was on an unrelated/stale commit history (`983428d`, a different prior session) rather than the expected base commit (`d5150a3`, main's current HEAD at spawn time). Per the mandatory `<worktree_branch_check>` step, corrected via `git reset --hard d5150a3e0d7d318d2eca9cc11741aec7b7071854` before any file edits — working tree was clean at that point, so this was a safe, sanctioned recovery per the executor's own branch-check protocol, not a destructive-git-prohibition violation.

## User Setup Required

None - no external service configuration required. (Real `.streamlit/secrets.toml` with `APOLLO_API_KEY`/`SENDING_DOMAIN` remains developer-supplied per the plan; only the placeholder `.example` template was committed.)

## Next Phase Readiness

- Plan 01-02 can implement `db/schema.py::ensure_schema()` against the three schema tests already in place (RED → GREEN).
- Plan 01-03 can implement `apollo/client.py::check_apollo_health()`/`get_credit_balance()` and `mailbox/dns_checks.py::check_spf()`/`check_dmarc()`/`check_dkim()` against the two remaining RED tests.
- No blockers. All Wave 0 test infrastructure and scaffolding required by 01-VALIDATION.md is in place.

---
*Phase: 01-foundation*
*Completed: 2026-07-20*
