---
phase: 01
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-20
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (system-installed; not yet a project dependency — add to `requirements-dev.txt` in Wave 0) |
| **Config file** | none — Wave 0 installs (`pytest.ini` or `pyproject.toml [tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-XX | 01 | 0 | — | — | Wave 0 test infra installed (`requirements-dev.txt`, `pytest.ini`, `tests/conftest.py`) | setup | `pytest --collect-only` | ❌ W0 | ⬜ pending |
| 01-XX-XX | TBD | TBD | DEDUP-01 | — | `ensure_schema()` creates `prospect`, `email_events`, `free_email_domains` tables and `contacted_registry` view idempotently | unit | `pytest tests/test_schema.py::test_ensure_schema_idempotent -x` | ❌ W0 | ⬜ pending |
| 01-XX-XX | TBD | TBD | DEDUP-01 | — | `contacted_registry` view nulls `dedupable_domain` for seeded free-email domains, passes through company domains | unit | `pytest tests/test_schema.py::test_registry_excludes_free_domains -x` | ❌ W0 | ⬜ pending |
| 01-XX-XX | TBD | TBD | Success Criterion 1/2 | — | `check_apollo_health()` returns `(False, ...)` on 401/403 and `(True, ...)` on 200 with `is_logged_in: true` | unit (mocked `requests`) | `pytest tests/test_apollo_client.py::test_check_apollo_health -x` | ❌ W0 | ⬜ pending |
| 01-XX-XX | TBD | TBD | Success Criterion 1 | — | `check_spf`/`check_dmarc`/`check_dkim` correctly classify a domain with known-good records vs. no records (mocked DNS) | unit (mocked `dns.resolver`) | `pytest tests/test_dns_checks.py::test_check_spf_dmarc_dkim -x` | ❌ W0 | ⬜ pending |
| 01-XX-XX | TBD | TBD | Success Criterion 4 | — | Prospect rows written before a fresh `sqlite3.connect()` to the same file are still queryable afterward | integration | `pytest tests/test_schema.py::test_persistence_across_reconnect -x` | ❌ W0 | ⬜ pending |

*Task IDs are placeholders — the planner assigns final plan/task numbering; the checker cross-references this map against actual `<acceptance_criteria>` entries.*

---

## Wave 0 Requirements

- [ ] `requirements-dev.txt` — add `pytest` (currently only system-available, not project-pinned)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — set `testpaths = ["tests"]`
- [ ] `tests/conftest.py` — shared fixtures: temp SQLite DB path per test, `requests`/`dns.resolver` mocking helpers
- [ ] `tests/test_schema.py`, `tests/test_apollo_client.py`, `tests/test_dns_checks.py` — all net-new, no existing test infra in this greenfield repo

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health status page renders pass/fail indicators for API key, credit balance, mailbox deliverability on app boot | Success Criterion 1 | Streamlit UI rendering — no headless component-render test in scope for this phase | Run `streamlit run app.py`, confirm 3 indicators render with correct pass/fail state for a known-good and known-bad `.streamlit/secrets.toml` |
| Non-technical error banner (not a stack trace) shown for missing/invalid Apollo key | Success Criterion 2 | Visual/UX check — banner wording and absence of traceback is a human judgment call | Unset `APOLLO_API_KEY` in secrets, boot app, confirm banner text is human-readable and no traceback is visible |
| DKIM selector auto-detection degrades to "Unknown — could not auto-detect" with manual self-attestation checkbox when no common selector resolves | CONTEXT.md Claude's Discretion (DKIM) | Depends on live DNS state of a real sending domain; not deterministically mockable end-to-end | Point the app at a domain with no discoverable DKIM selector, confirm UI shows "Unknown" state plus the self-attestation checkbox rather than a hard FAIL |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
