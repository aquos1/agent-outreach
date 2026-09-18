---
phase: 4
slug: review-queue-and-sequence-enrollment
status: ready
nyquist_compliant: true
wave_0_complete: true
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
| 04-01 T1 | 04-01 | 1 | QUEUE-01, QUEUE-02 | — | `title`/`last_name` columns added; `get_drafted_by_path()` returns every `status='drafted'` prospect for a path with name/company/title/full assembled email | unit | `pytest tests/test_schema.py tests/test_prospects.py::test_get_drafted_by_path -x` | ✅ | ⬜ pending |
| 04-01 T2 | 04-01 | 1 | QUEUE-01, QUEUE-02 | — | Review Queue page renders path selector, queue rows, per-row draft expander, empty state; registered in nav | manual+unit | `python -m py_compile pages/review_queue_page.py` | ✅ | ⬜ pending |
| 04-02 T1 | 04-02 | 2 | D-05, D-06 | — | `validate_template_fields` blocks saves with missing/broken merge fields (including unknown placeholders); `template_override` store round-trips over `PATH_TEMPLATES` default | unit | `pytest tests/test_templates.py::test_validate_template_fields tests/test_schema.py::test_template_override_roundtrip -x` | ✅ | ⬜ pending |
| 04-02 T2 | 04-02 | 2 | D-03, D-04, D-19 | — | Template editor section renders on Review Queue page; save re-assembles all visible drafts immediately; D-19 warning caption present | manual+unit | `grep -c "only the personalized opening line is sent from here" pages/review_queue_page.py` | ✅ | ⬜ pending |
| 04-03 T1 | 04-03 | 2 | QUEUE-04, D-16 | — | `create_contacts_bulk()` sends `run_dedupe: true`, strips `opening_line` from top-level attrs and re-sends as `typed_custom_fields`, parses `created_contacts`/`existing_contacts`; `add_contacts_to_sequence()` splits `contacts`/`skipped_contact_ids` | unit | `pytest tests/test_apollo_client.py::test_create_contacts_bulk tests/test_apollo_client.py::test_add_contacts_to_sequence -x` | ✅ | ⬜ pending |
| 04-03 T2 | 04-03 | 2 | D-07, D-08 | — | Enrollment reconciliation logic + `mark_contact_created`/`mark_sequenced` status transitions | unit | `pytest tests/test_prospects.py::test_mark_contact_created tests/test_prospects.py::test_mark_sequenced_only_affects_selected -x` | ✅ | ⬜ pending |
| 04-06 T1 | 04-06 | 3 | D-18 | — | `_find_custom_field_id`/`ensure_custom_field` strip the modality-prefixed id (`"contact.<hex>"` → raw hex) before use as a `typed_custom_fields` key; `update_contact_custom_field()` PATCHes a single contact | unit | `pytest tests/test_apollo_client.py::test_find_custom_field_id_strips_modality_prefix -x` | ✅ | ⬜ pending |
| 04-06 T2 | 04-06 | 3 | D-17 | — | `split_contacts_by_origin()` separates `created_map`/`existing_map` without changing `map_created_contacts`' existing behavior (no 04-03 test edited) | unit | `pytest tests/test_apollo_client.py -k split_contacts_by_origin -x` | ✅ | ⬜ pending |
| 04-04 T1 | 04-04 | 4 | QUEUE-03, D-01, D-02, D-09, D-13 | — | 4 secrets plumbed; default-checked per-row selection; `st.dialog` confirm gate with count + path name; lazy `ensure_custom_field` resolution cached in session state, approve disabled on failure | manual+unit | `grep -c "ensure_custom_field" app.py` (expect 0) | ✅ | ⬜ pending |
| 04-04 T2 | 04-04 | 4 | QUEUE-03, QUEUE-04, D-07, D-08, D-12, D-17 | — | Approval handler creates contacts, enrolls, applies D-17 follow-up PATCH for `existing_map`, renders Enrolled/Skipped badges; `mark_sequenced` only called inside the Apollo-confirmed `enrolled_ids` loop, never the full submitted batch | unit | `pytest tests/test_prospects.py::test_partial_enrollment_leaves_skipped_drafted -x` | ✅ | ⬜ pending |
| 04-05 T1 | 04-05 | 5 | QUEUE-04, D-13, D-18 | — | Resolves real sequence IDs, sending mailbox ID, and custom-field state; prints raw vs. prefix-stripped field id | manual | n/a — diagnostic script, output inspected by developer | ✅ | ⬜ pending |
| 04-05 T2 | 04-05 | 5 | QUEUE-01..04, D-07, D-13, D-14, D-17, D-19, A6 | — | Live end-to-end enrollment: secrets resolve, dialog fires, per-contact outcomes correct, opening line reaches Apollo and renders in sequence preview, D-19 tradeoff explicitly accepted/rejected | checkpoint:human-verify | n/a — blocking human checkpoint | ✅ | ⬜ pending |
| 04-05 T3 | 04-05 | 5 | QUEUE-04 | — | Code reconciled against observed live payloads from T2 | unit | `pytest -q` (full suite) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. File Exists column reflects the file existing in the plan (all 6 plans committed) at time of validation strategy finalization, not runtime test-pass state — that's the Status column, updated during execution.*

---

## Wave 0 Requirements

- [x] `tests/test_apollo_client.py` additions — `test_create_contacts_bulk`, `test_add_contacts_to_sequence` (04-03), `test_find_custom_field_id_strips_modality_prefix`, `split_contacts_by_origin` coverage (04-06)
- [x] `tests/test_prospects.py` additions — `test_get_drafted_by_path` (04-01), `test_mark_contact_created`, `test_mark_sequenced_only_affects_selected`, `test_partial_enrollment_leaves_skipped_drafted` (04-03/04-04)
- [x] `tests/test_schema.py` addition — `test_template_override_roundtrip` (04-02, idempotent `CREATE TABLE IF NOT EXISTS`, plus seed-fallback read)
- [x] New `tests/test_templates.py` — `test_validate_template_fields` for D-06 (04-02)
- [x] No new framework install needed — pytest already present in `.venv`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Apollo `bulk_create`/`add_contact_ids` response shapes match RESEARCH.md's documented fields | QUEUE-04 | Response shapes were confirmed via live docs fetch + cross-search, not a live authenticated call against this team's real Apollo account — matches this project's established live-call-confirmation convention for every new Apollo endpoint | One live "Approve" on a small real batch (1-2 contacts); inspect the raw response and confirm `created_contacts`/`existing_contacts` and `contacts`/`skipped_contact_ids` fields match what the code expects |
| `send_email_from_email_account_id` (D-13) resolves to a working, active mailbox | QUEUE-04 | Requires a real Apollo account lookup and a real send — cannot be asserted by a mocked unit test | Confirm the hardcoded `APOLLO_SENDING_EMAIL_ACCOUNT_ID` secret matches an active, connected mailbox in Apollo's account settings before the first live enrollment |
| Template editor UI (save, validation warning, re-assembly of visible drafts) renders and behaves correctly | D-03–D-06 | UI flow, no Streamlit component test harness configured (same limitation as Phases 2/3) | Manual click-through: edit a template, break a merge field and confirm the save is blocked with a warning, fix it and confirm queued drafts re-render with the new text |
| Confirm-dialog gate (D-09) and Enrolled-badge display (D-12) render correctly | QUEUE-03 | UI flow, no Streamlit component test harness configured | Manual click-through: Approve Selected/All, confirm the dialog shows the correct count and path name, confirm badges appear on success rows post-enrollment |
| The "AI Opening Line" custom field exists in Apollo, is NOT marked required, and the opening line actually renders inside a real sequence email preview (D-14, A6) | QUEUE-04 | Requires live Apollo account state and a real send-preview — cannot be mocked | 04-05 Task 2 checkpoint: run one real enrollment, open the enrolled contact in Apollo, confirm the field value and its presence in the sequence email preview |
| D-17's `existing_contacts` follow-up (`PATCH /contacts/{id}` with `typed_custom_fields`) actually reaches Apollo for a contact that already existed there | QUEUE-04 | Requires a real Apollo contact that predates this app's registry — cannot be mocked | 04-05 Task 2 step 13: target a contact known to already exist in Apollo, confirm the opening line still lands via the follow-up PATCH, not just for brand-new contacts |
| Developer has explicitly accepted (or rejected) the D-19 tradeoff — editing the template in-app only updates the preview, not what Apollo sends | — (process, not a functional requirement) | Product/UX decision, not a testable behavior | 04-05 Task 2 step 14 + resume-signal: developer must state acceptance/rejection explicitly, not just reply "approved" |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-17 (gsd-plan-checker Dimension 8, re-verified against final 6-plan set after D-14–D-19 fold-in; 0 blockers)
