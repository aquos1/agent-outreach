---
phase: 4
slug: review-queue-and-sequence-enrollment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-17
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (installed in `.venv`, confirmed via `.venv/bin/python3.13 -m pytest --version`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `addopts = "-q"`) |
| **Quick run command** | `.venv/bin/python3.13 -m pytest tests/test_apollo_client.py tests/test_prospects.py tests/test_schema.py -q` |
| **Full suite command** | `.venv/bin/python3.13 -m pytest -q` (use the `python3.13` interpreter explicitly — `.venv/bin/python3` resolves to a stray, unpinned Python 3.14 per RESEARCH.md Pitfall 4) |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command above.
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** Full suite must be green, plus a manual human-verify checkpoint confirming the live Apollo response shapes for `bulk_create`/`add_contact_ids` and confirming `send_email_from_email_account_id` (D-13) actually resolves to a working, active mailbox — matches this project's established convention for every new Apollo endpoint (Phase 1 §01-04, Phase 2 §02-03 live-call confirmations).
- **Max feedback latency:** ~10 seconds (full suite runtime).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-TBD | TBD | TBD | QUEUE-01 | — | Every `status='drafted'` prospect appears in the queue query before enrollment | unit | `pytest tests/test_prospects.py::test_get_drafted_by_path -x` | ❌ W0 | ⬜ pending |
| 04-TBD | TBD | TBD | QUEUE-02 | — | Queue query/display includes name, company, role, full assembled email | unit | `pytest tests/test_prospects.py::test_get_drafted_by_path -x` | ❌ W0 | ⬜ pending |
| 04-TBD | TBD | TBD | QUEUE-03 | — | Unchecked/unselected contacts remain `status='drafted'` after an Approve action on a different subset | unit | `pytest tests/test_prospects.py::test_mark_sequenced_only_affects_selected -x` | ❌ W0 | ⬜ pending |
| 04-TBD | TBD | TBD | QUEUE-04 | — | `create_contacts_bulk()` sends `run_dedupe: true`, parses `created_contacts`/`existing_contacts`; `add_contacts_to_sequence()` splits `contacts`/`skipped_contact_ids` | unit | `pytest tests/test_apollo_client.py::test_create_contacts_bulk tests/test_apollo_client.py::test_add_contacts_to_sequence -x` | ❌ W0 | ⬜ pending |
| 04-TBD | TBD | TBD | D-05/D-06 (template override) | — | Template save validates merge fields; override persists and is read back over `PATH_TEMPLATES` default | unit | `pytest tests/test_schema.py::test_template_override_roundtrip tests/test_templates.py::test_validate_template_fields -x` | ❌ W0 | ⬜ pending |
| 04-TBD | TBD | TBD | D-07/D-08 (partial-failure handling) | — | A batch with mixed enrolled/skipped contacts marks only enrolled ones `sequenced`, leaves skipped ones `drafted` | unit | `pytest tests/test_prospects.py::test_partial_enrollment_leaves_skipped_drafted -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Task/Plan/Wave columns are TBD — the planner assigns real IDs; this table is the requirement→test contract it must satisfy.*

---

## Wave 0 Requirements

- [ ] `tests/test_apollo_client.py` additions — `test_create_contacts_bulk`, `test_add_contacts_to_sequence` (mock `requests.post` per existing `mock_requests_response` fixture convention)
- [ ] `tests/test_prospects.py` additions — `test_get_drafted_by_path`, `test_mark_contact_created`, `test_mark_sequenced_only_affects_selected`, `test_partial_enrollment_leaves_skipped_drafted`
- [ ] `tests/test_schema.py` addition — `test_template_override_roundtrip` (idempotent `CREATE TABLE IF NOT EXISTS`, plus seed-fallback read)
- [ ] New `tests/test_templates.py` (or extend `tests/test_personalization.py`) — `test_validate_template_fields` for D-06
- [ ] No new framework install needed — pytest already present in `.venv`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Apollo `bulk_create`/`add_contact_ids` response shapes match RESEARCH.md's documented fields | QUEUE-04 | Response shapes were confirmed via live docs fetch + cross-search, not a live authenticated call against this team's real Apollo account — matches this project's established live-call-confirmation convention for every new Apollo endpoint | One live "Approve" on a small real batch (1-2 contacts); inspect the raw response and confirm `created_contacts`/`existing_contacts` and `contacts`/`skipped_contact_ids` fields match what the code expects |
| `send_email_from_email_account_id` (D-13) resolves to a working, active mailbox | QUEUE-04 | Requires a real Apollo account lookup and a real send — cannot be asserted by a mocked unit test | Confirm the hardcoded `APOLLO_SENDING_EMAIL_ACCOUNT_ID` secret matches an active, connected mailbox in Apollo's account settings before the first live enrollment |
| Template editor UI (save, validation warning, re-assembly of visible drafts) renders and behaves correctly | D-03–D-06 | UI flow, no Streamlit component test harness configured (same limitation as Phases 2/3) | Manual click-through: edit a template, break a merge field and confirm the save is blocked with a warning, fix it and confirm queued drafts re-render with the new text |
| Confirm-dialog gate (D-09) and Enrolled-badge display (D-12) render correctly | QUEUE-03 | UI flow, no Streamlit component test harness configured | Manual click-through: Approve Selected/All, confirm the dialog shows the correct count and path name, confirm badges appear on success rows post-enrollment |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
