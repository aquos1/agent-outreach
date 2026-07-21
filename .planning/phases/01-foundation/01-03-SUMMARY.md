---
phase: 01-foundation
plan: 03
subsystem: infra
tags: [requests, dnspython, apollo, spf, dmarc, dkim, health-check]

# Dependency graph
requires:
  - phase: 01-foundation (plan 01-01)
    provides: repo scaffold, RED test harness (tests/test_apollo_client.py, tests/test_dns_checks.py, tests/conftest.py), pyproject/requirements
provides:
  - "apollo/client.py: check_apollo_health (401/403/200/network-error banner mapping) and get_credit_balance (defensive, informational-only)"
  - "mailbox/dns_checks.py: check_spf, check_dmarc, check_dkim (soft 'unknown', never hard-fail), _valid_domain input guard"
affects: [01-04 (health page consumes both modules), phase-2-discovery (Apollo client reused for search/enrichment calls)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "External connectivity checks return typed (status, message) tuples and never raise — banners over stack traces (SC-2, T-03-02)"
    - "DKIM brute-force selector scan can only confirm pass; absence degrades to 'unknown', never 'fail' (RFC 6376 has no selector enumeration)"
    - "Defensive dict.get() field lookup for unconfirmed third-party JSON schema (Apollo credit field name) so a wrong key degrades gracefully instead of crashing"

key-files:
  created: [apollo/client.py, mailbox/dns_checks.py]
  modified: []

key-decisions:
  - "Network-error banner text follows the exact locked Copywriting Contract wording ('Apollo connection failed — check your internet connection and try again.') rather than RESEARCH.md's exception-interpolated variant, since 01-UI-SPEC.md's contract is the authoritative wording source"
  - "Reworded internal docstring wording from literal 'fail' quotes to 'hard-fail status'/'hard failure' to satisfy the acceptance-criteria grep assertion of zero 'fail' string occurrences in dns_checks.py, without changing any behavior"

requirements-completed: [SC-1, SC-2]

# Metrics
duration: ~15min
completed: 2026-07-21
---

# Phase 01 Plan 03: Apollo Health + DNS Mailbox Checks Summary

**Apollo Master API key validity/credit-balance client and SPF/DMARC/DKIM DNS TXT sensing layer, both returning typed never-raising (status, banner) tuples for the health page.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-21T00:55:28Z
- **Tasks:** 2 completed
- **Files modified:** 2 created

## Accomplishments
- `apollo/client.py`: `check_apollo_health` maps 401/403/200(is_logged_in)/network-error to the exact locked banner copy from 01-UI-SPEC.md's Copywriting Contract; `get_credit_balance` defensively looks up the (unconfirmed) credit field name and never crashes on a missing/renamed key
- `mailbox/dns_checks.py`: `check_spf`/`check_dmarc` give crisp True/False via TXT-record prefix matching; `check_dkim` brute-forces `COMMON_DKIM_SELECTORS` and can only return `'pass'` or `'unknown'` — never a hard fail, per RFC 6376's lack of selector enumeration
- `_valid_domain` guard rejects empty/whitespace/spaced/scheme-prefixed/dot-less domains before any DNS query is issued (V5 input validation, T-03-03)
- RED tests (`tests/test_apollo_client.py`, `tests/test_dns_checks.py`) from Plan 01-01 now GREEN with no modifications to the test files themselves

## Task Commits

1. **Task 1: Apollo health + credit-balance client** - `703f1b1` (feat)
2. **Task 2: DNS mailbox checks (SPF/DMARC/DKIM)** - `c308e8d` (feat)

_RED tests were already committed in Plan 01-01 (`b416049 test(01-01): add RED test harness for schema, apollo client, and DNS checks`); this plan's tasks are the GREEN implementation step of that TDD cycle._

## Files Created/Modified
- `apollo/client.py` - Apollo auth/health validity gate + informational credit-balance lookup, both wrapped in try/except returning typed tuples, never logging the api_key
- `mailbox/dns_checks.py` - SPF/DMARC pass-fail and DKIM soft-unknown DNS TXT checks via `dns.resolver.resolve`, plus a `_valid_domain` pre-query guard

## Decisions Made
- Used the exact network-error banner wording from 01-UI-SPEC.md's Copywriting Contract table rather than RESEARCH.md's exception-message-interpolated variant — the UI-SPEC is the locked source of truth for user-facing copy
- Extended `_valid_domain` checks (no dot, contains space, contains `://`) beyond the plan's minimal "empty/whitespace" wording, applying the same input-guard rule to all three DNS check functions (not just as a standalone helper) so a malformed `SENDING_DOMAIN` never reaches `dns.resolver.resolve` from any entry point

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded docstring to satisfy the literal `grep -c "'fail'\|"fail"" mailbox/dns_checks.py` acceptance criterion**
- **Found during:** Task 2 acceptance-criteria verification
- **Issue:** The initial docstring for `check_dkim` read `"Never returns a hard 'fail' — see Pitfall 2."`, which contains the literal substring `'fail'`. The plan's acceptance criteria requires `grep -c "'fail'\|"fail"" mailbox/dns_checks.py` to return exactly 0, but the count was 1 (from the docstring comment, not an actual return value).
- **Fix:** Reworded the two docstring occurrences to "hard-fail status" / "hard failure" — no behavior change, only comment wording.
- **Files modified:** `mailbox/dns_checks.py`
- **Verification:** `grep -c "'fail'\|"fail"" mailbox/dns_checks.py` now returns 0; `python -m pytest tests/test_dns_checks.py -x -q` still passes after the edit.
- **Committed in:** `c308e8d` (part of Task 2 commit — edit was made before the single Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — literal grep-assertion wording mismatch, not a functional defect)
**Impact on plan:** Cosmetic docstring wording only; no behavior, test, or acceptance-criteria semantics changed beyond satisfying the exact grep the plan specified.

## Issues Encountered
- Worktree HEAD was on a stale branch tip (`983428d`) that predated the Wave 0 merge commit (`8c846f2`, which includes Plan 01-01's scaffold and RED harness). Per the mandatory worktree branch check, the working tree was clean and `git reset --hard 8c846f2ee35117eeb66b868b3f8bc5eff3e1c103` was applied before any task work began, bringing the branch to the correct base.

## User Setup Required
None for this plan — `APOLLO_API_KEY` and `SENDING_DOMAIN` are consumed at runtime by Plan 01-04's health page, not required to run this plan's unit tests (all network/DNS calls are mocked).

## Next Phase Readiness
- Both sensing-layer modules (`apollo/client.py`, `mailbox/dns_checks.py`) are ready to be imported by Plan 01-04's health page with no further changes needed to their public interfaces
- Carry-forward note for Plan 01-04: the `# WAVE-0 VERIFY:` comment in `apollo/client.py`'s `get_credit_balance` flags that the exact Apollo `usage_stats/api_usage_stats` credit-field JSON key is unconfirmed against a live account — confirm with one authenticated call before wiring the `st.metric` display
- No blockers for downstream work

---
*Phase: 01-foundation*
*Completed: 2026-07-21*
