---
phase: 2
slug: contact-discovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-24
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (already installed and configured) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Quick run command** | `pytest tests/test_apollo_client.py tests/test_prospects.py tests/test_discovery_logic.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_apollo_client.py tests/test_prospects.py tests/test_discovery_logic.py -q`
- **After every plan wave:** Run `pytest -q` (full suite, includes Phase 1's existing tests to guard against regressions)
- **Before `/gsd:verify-work`:** Full suite must be green, plus the Wave 0 human-verify checkpoint (live search + live bulk_match call) completed and any field-name mismatches from the Assumptions Log resolved
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-XX-XX | TBD | 0 | PATH-01 | — | Exactly 3 path options rendered, in order | manual-only | — (visual check against UI-SPEC) | N/A — manual per project convention | ⬜ pending |
| 02-XX-XX | TBD | TBD | PATH-02 | — | Path selection changes only sequence ID/template, never search filters | unit | `pytest tests/test_discovery_logic.py::test_path_does_not_affect_filters -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | 0 | PATH-03 | — | Free text company type + role accepted as inputs | manual-only | — | N/A — manual | ⬜ pending |
| 02-XX-XX | TBD | TBD | DISC-01 | — | Free text translated into Apollo filters correctly (comma-split, no AI) | unit | `pytest tests/test_discovery_logic.py::test_to_filter_list -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | DISC-02 | — | `has_email:false` candidates excluded before enrichment | unit | `pytest tests/test_discovery_logic.py::test_has_email_prefilter -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | DISC-03 | — | Bulk enrichment retrieves emails, batches ≤10 per call | unit (mocked `requests`) | `pytest tests/test_apollo_client.py::test_bulk_match_people_batches_of_ten -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | DISC-04 | — | Cost estimate = `min(matched-and-deduped, 50)`, computed with no Apollo call | unit | `pytest tests/test_discovery_logic.py::test_cost_estimate_no_apollo_call -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | DEDUP-02 | — | Candidates already in `contacted_registry` excluded pre-enrichment | unit (uses `tmp_db_path` fixture + real `ensure_schema()`) | `pytest tests/test_prospects.py::test_dedup_filter_excludes_known_contacts -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | Error handling (429/401/403/422) | — | Client functions return correct typed-tuple + message per code | unit (mocked `requests`) | `pytest tests/test_apollo_client.py::test_search_people_error_codes tests/test_apollo_client.py::test_bulk_match_people_error_codes -x` | ❌ W0 | ⬜ pending |
| 02-XX-XX | TBD | 0 | Session-state flow (two-stage Find/Enrich) | — | Manual (no Streamlit component test harness configured) | manual-only | — | N/A — manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_discovery_logic.py` — new file: covers PATH-02, DISC-01, DISC-02, DISC-04 (pure functions, no network — filter translation, has_email pre-filter, cost estimate)
- [ ] `tests/test_prospects.py` — new file: covers DEDUP-02 (dedup query against `contacted_registry`, insert enriched rows), reuses `tmp_db_path` fixture from `tests/conftest.py`
- [ ] `tests/test_apollo_client.py` — extend existing file: add RED tests for `search_people()` and `bulk_match_people()` (success, 401/403/422/429, batching of ≤10 per call), reusing the existing `mock_requests_response` fixture
- [ ] No new fixtures needed in `conftest.py` — `tmp_db_path` and `mock_requests_response` already cover this phase's needs; a small `mock_apollo_search_response(n, has_email_count)` / `mock_apollo_bulk_match_response(n)` factory helper is a nice-to-have, not a gap
- [ ] Wave 0 human-verify checkpoint: one live `/mixed_people/api_search` call + one live `/people/bulk_match` call to confirm exact response field names (MEDIUM confidence area per RESEARCH.md)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Exactly 3 path options rendered, in order | PATH-01 | No Streamlit component test harness set up in this project | Visual check against UI-SPEC's exact copy table |
| Free text company type + role accepted as inputs | PATH-03 | UI form, no component test harness | Manual entry check in running app |
| Two-stage Find/Enrich session-state flow | (UI flow, all reqs) | No Streamlit component test harness configured | Manual click-through: Find Contacts → Enrich & Continue, confirm results persist across reruns |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
