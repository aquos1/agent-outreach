---
phase: 3
slug: ai-personalization
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-17
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (already installed and configured) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Quick run command** | `pytest tests/test_personalization.py tests/test_prospects.py tests/test_schema.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_personalization.py tests/test_prospects.py tests/test_schema.py -q`
- **After every plan wave:** Run `pytest -q` (full suite, guards against regressions in Phase 1/2 tests)
- **Before `/gsd:verify-work`:** Full suite must be green, plus a manual human-review sample of real (or realistically-mocked) generated opening lines checked against their source `title`/`company` fields — the one success criterion (no hallucination) automated tests structurally cannot verify.
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

> Task ID / Plan / Wave columns are filled in as plans are created (planner assigns concrete task numbers below); requirement-level rows are locked now from RESEARCH.md's test map.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | PERS-01 (grounding) | — | Opening line generation call only sends title+company to the model (no industry/seniority passed) | unit (mocked `client.messages.create`) | `pytest tests/test_personalization.py::test_prompt_excludes_industry_and_seniority -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (sparse fallback) | — | Missing/null/placeholder title triggers the shared fallback opener without calling the API | unit | `pytest tests/test_personalization.py::test_sparse_title_triggers_fallback -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (API-failure fallback) | — | Simulated `anthropic.APIConnectionError`/`RateLimitError`/`APITimeoutError` after SDK retry triggers the same fallback opener (D-14) | unit (mocked client raising error) | `pytest tests/test_personalization.py::test_api_failure_triggers_fallback -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (assembly) | — | `assemble_email()` produces correct subject + body per path, with `{opening_line}` inserted immediately after the greeting (D-09) | unit | `pytest tests/test_personalization.py::test_assemble_email_per_path -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (persistence) | — | `update_draft()` writes `opening_line`, `draft_source`, and `status='drafted'` correctly, using parameterized SQL | unit (uses `tmp_db_path` fixture + real `ensure_schema()`) | `pytest tests/test_prospects.py::test_update_draft_writes_status_drafted -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (schema migration) | — | `ensure_schema()` is idempotent against a pre-existing `prospect` table missing the new columns — does not raise, adds columns exactly once | unit (create table without new columns, call `ensure_schema()` twice) | `pytest tests/test_schema.py::test_column_migration_idempotent -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (batch-failure banner threshold, D-16) | — | Fallback fraction > threshold triggers banner condition; below threshold does not | unit (pure function, no Streamlit/network) | `pytest tests/test_personalization.py::test_fallback_fraction_threshold -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PERS-01 (no-hallucination guarantee) | — | N/A — cannot be asserted by an automated test against a live/mocked LLM call; probabilistic output | manual-only, human review | — (sample-review a batch of real generated openers against source title/company during execution, before marking the phase done) | N/A — inherent limitation | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_personalization.py` — new file: covers prompt construction (grounding), sparse-title fallback, API-failure fallback, template assembly, fallback-fraction threshold (pure functions + mocked `anthropic` client, no live network calls)
- [ ] `tests/test_prospects.py` — extend existing file: add `update_draft()` tests reusing the existing `tmp_db_path` fixture
- [ ] `tests/test_schema.py` — extend existing file: add the column-migration idempotency test (create a pre-migration table, call `ensure_schema()` twice, assert no error and columns present)
- [ ] `tests/conftest.py` — add a `mock_anthropic_message` factory fixture (mirrors the existing `mock_requests_response` fixture) that builds a fake SDK response object with `.content = [SimpleNamespace(type="text", text="...")]`, so tests can monkeypatch `client.messages.create` without a real API key
- [ ] Framework install: `pip install anthropic==1.6.0` and add to `requirements.txt` — required before any of the above tests can import `personalization/generator.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No hallucinated details in generated opening lines | PERS-01 (success criterion 1) | LLM output is probabilistic; no automated test can prove absence of hallucination | Sample-review a batch of real generated openers against their source `title`/`company` fields before marking the phase done |
| Full assembled email draft (opening line + template body) visible per contact before send | PERS-01 (success criterion 2) | UI flow, no Streamlit component test harness configured | Manual click-through on the Discovery page: run Enrich & Continue, expand "View draft" per row, confirm combined subject+body renders |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
