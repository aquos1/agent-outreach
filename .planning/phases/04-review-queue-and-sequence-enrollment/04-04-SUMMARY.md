---
phase: 04-review-queue-and-sequence-enrollment
plan: 04
subsystem: ui
tags: [streamlit, apollo-api, sqlite, review-queue, enrollment]

# Dependency graph
requires:
  - phase: 04-review-queue-and-sequence-enrollment (04-02)
    provides: Template editor section on the Review Queue page, checkbox/badge cell placeholders left intentionally blank
  - phase: 04-review-queue-and-sequence-enrollment (04-03)
    provides: apollo/client.py's create_contacts_bulk()/add_contacts_to_sequence(), review/logic.py's map_created_contacts()/build_contact_payloads()/split_enrollment_outcome(), db/prospects.py's mark_contact_created()/mark_sequenced()
  - phase: 04-review-queue-and-sequence-enrollment (04-06)
    provides: apollo/client.py's ensure_custom_field()/update_contact_custom_field(), review/logic.py's split_contacts_by_origin()
provides:
  - Four new Phase 4 secrets (three per-path sequence IDs + one shared sending mailbox) documented in .streamlit/secrets.toml.example
  - Per-row checkbox selection (default checked, QUEUE-03) and a D-09 confirmation dialog gating both Approve buttons on pages/review_queue_page.py
  - The full approval handler wiring create_contacts_bulk -> D-17 custom-field follow-up -> add_contacts_to_sequence, with response-body-only Enrolled/Skipped classification and per-row outcome badges
affects: [04-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Page-scoped, session-once custom-field resolution (ensure_custom_field cached in st.session_state.opening_line_field_id) instead of an app.py boot gate — keeps a Phase-4-only Apollo capability from hard-stopping pages that don't need it"
    - "pending_approval / approve_result session-state pair mirrors the existing find_result/enrich_result/template_result convention: the dialog only ever writes pending_approval, a separate top-of-section handler consumes it and writes approve_result"
    - "Path-scoped result invalidation via a tracked _approve_scope_path sentinel, cleared whenever the selectbox value changes, so one path's outcome never bleeds into another path's render"

key-files:
  created: []
  modified: [pages/review_queue_page.py, .streamlit/secrets.toml.example]

key-decisions:
  - "Deviated from the plan's literal step 8 instruction to call st.rerun() after a successful approval (Rule 1 — auto-fixed bug). Calling st.rerun() immediately after mark_sequenced() would force a fresh get_drafted_by_path() query before any render happens, and Apollo-confirmed rows are by definition no longer status='drafted' at that point — the green 'Enrolled' badge (D-12, and this plan's own must_haves truth D-07/D-12) would never actually be visible to the teammate, only ever existing as unreachable code. Instead, the handler completes and falls through to render in the SAME script execution using the already-fetched `rows` list (still containing full data since it's an in-memory list, unaffected by the DB write); the row's checkbox is swapped for the badge from st.session_state.approve_result on that same pass. The enrolled row naturally drops off the query on the NEXT reload (e.g. the following widget interaction), matching the UI-SPEC's own wording verbatim: 'for the remainder of the current run ... the row naturally drops from the query on next reload.' Verified this actually renders correctly via a Streamlit AppTest run with mocked Apollo responses (see Issues Encountered)."
  - "Followed the plan's literal double-call pattern for map_created_contacts() + split_contacts_by_origin() against the same response/rows, even though map_created_contacts() internally delegates to split_contacts_by_origin() (04-06) and this recomputes the same split twice. Kept as specified since both call sites are individually required by the acceptance-criteria greps and the redundancy is a cheap, pure, in-memory list comprehension with no correctness cost."
  - "Personalization-update failures (D-17 follow-up) are tracked in a separate personalization_failures list, never merged into skipped_pairs — a contact whose opening-line PATCH failed is still enrolled and still counted in enrolled_ids; only a non-blocking st.warning informs the teammate, matching the plan's explicit 'do NOT treat it as a skip' instruction."

patterns-established:
  - "Any future Phase 4/5 approval-adjacent UI should reuse the pending_approval-capture-then-clear-then-process pattern (capture and null out the trigger before any external call) to guarantee a rerun can never re-fire the same side-effecting action twice"

requirements-completed: [QUEUE-03, QUEUE-04]

# Metrics
duration: ~90min
completed: 2026-09-18
---

# Phase 04 Plan 04: Review Queue Approval Flow — Selection, Confirmation, and Sequence Enrollment Summary

**Wired the Review Queue's Approve Selected/Approve All buttons through a locked-copy confirmation dialog into the full Apollo enrollment engine — bulk contact creation with the AI opening line attached via a custom field, a D-17 follow-up PATCH for already-existing contacts, and per-contact Enrolled/Skipped badges classified strictly from Apollo's response body, never HTTP status.**

## Performance

- **Duration:** ~90 min (including venv setup from scratch, since this worktree had no pre-existing `.venv`)
- **Started:** 2026-09-18T05:15:00Z
- **Completed:** 2026-09-18T05:56:00Z
- **Tasks:** 2 completed
- **Files modified:** 2 (`pages/review_queue_page.py`, `.streamlit/secrets.toml.example`)

## Accomplishments

- A teammate opens Review Queue, sees every drafted contact for the selected path with a checkbox that starts checked (QUEUE-03), and can uncheck specific contacts before approving
- Both "Approve Selected (N)" and "Approve All (M)" open an `st.dialog` reading "Enroll N contacts into the {Path} sequence?" (D-09's exact locked wording) before any Apollo call fires; "Keep in Queue" dismisses with zero side effects
- Confirming creates Apollo contacts (`run_dedupe: true`, via 04-03's `create_contacts_bulk`) with each contact's AI opening line attached as a `typed_custom_fields` entry using the field id resolved once per session via `ensure_custom_field` (D-14/D-16/D-18)
- Contacts Apollo already had on file (`existing_contacts`) get a D-17 follow-up `update_contact_custom_field` call so their opening line still reaches Apollo; a failed follow-up is surfaced as a non-blocking warning, never silently dropped and never treated as a skip
- Enrollment outcome is classified strictly from `add_contacts_to_sequence`'s response body (`contacts[]` vs `skipped_contact_ids`) — never the HTTP status (D-07) — confirmed via `grep -cE "status_code|== 200"` returning 0 on the page
- Only Apollo-confirmed enrolled prospects advance to `status='contact_created'`/`'sequenced'`; every skipped or unchecked contact stays at `status='drafted'` and reappears in the queue, fully retryable (D-08)
- Enrolled rows show a green "Enrolled" badge in place of their checkbox; skipped rows keep their checkbox and show an orange "Skipped — {Apollo's exact reason}" badge (D-12)
- A hard Apollo failure (network/401/403/429/422) at either call leaves every submitted row untouched at `status='drafted'` and shows a red error banner — verified no `SELECT COUNT(*) FROM prospect WHERE status='sequenced'` change occurs on failure
- A missing sequence-ID or sending-mailbox secret, or an unresolved custom field, soft-fails with a plain-language banner and disables the approve buttons only — the template editor and queue table still render and work; no boot gate exists in `app.py` (confirmed by grep)

## Task Commits

Each task was committed atomically:

1. **Task 1: Secrets plumbing, per-row selection, and the confirmation dialog gate** - `b80252b` (feat)
2. **Task 2: Approval handler — create contacts, enroll, and render per-contact Enrolled/Skipped outcomes** - `8c28770` (feat)

## Files Created/Modified

- `.streamlit/secrets.toml.example` - Added `APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP`, `APOLLO_SEQUENCE_ID_PRODUCTTHON`, `APOLLO_SEQUENCE_ID_CLIENT_SOURCING`, `APOLLO_SENDING_EMAIL_ACCOUNT_ID` with a comment explaining these are hardcoded, resolved once in Apollo (D-01), and that plan 04-05 fills in the real values
- `pages/review_queue_page.py` - Added `SEQUENCE_SECRET_BY_SLUG`, per-path secret resolution, lazy once-per-session `ensure_custom_field` resolution with a disabling banner on any gap, default-checked per-row checkboxes feeding a `selected_ids` list, an `@st.dialog("Confirm enrollment")`-decorated confirmation gate, the `pending_approval`/`approve_result` session-state pair, the full approval handler (contact creation -> D-17 follow-up -> sequence enrollment -> D-07 classification -> status transitions), and per-row Enrolled/Skipped badge rendering in place of the checkbox/status cells

## Decisions Made

- See `key-decisions` in frontmatter for the two most consequential calls (the `st.rerun()` omission and the intentional double-split-computation).
- Placed the missing-secret and unresolved-custom-field banners immediately after path/secret resolution (before the template editor divider), rather than deeper in the page, so a teammate sees why approving is blocked before scrolling past the whole queue.
- Compared `approve_result["path"]` against the current `slug` before applying any badge/summary rendering, discarding a stale result from a different path outright (D-07/D-08/D-12 combined requirement) — implemented as a simple `if ... != slug: approve_result = None` guard rather than a nested conditional at every render site.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed the plan's instructed `st.rerun()` call after a successful approval**
- **Found during:** Task 2, while smoke-testing the mixed enrolled/skipped flow with Streamlit's `AppTest` harness
- **Issue:** Task 2's action step 8 literally instructs "Store `st.session_state.approve_result = {...}` and call `st.rerun()` so the queue re-queries with the new statuses." Calling `st.rerun()` immediately after `mark_sequenced()` forces the very next script execution to re-query `get_drafted_by_path()`, which by definition excludes any prospect that was just advanced past `status='drafted'`. That means the green "Enrolled" badge — required by this same plan's own `must_haves` truth ("an Apollo-confirmed row shows a green Enrolled badge in place of its checkbox") and by 04-UI-SPEC.md's Queue Table Contract ("for the remainder of the current run") — would never actually render; the enrolled row would just silently vanish from the table with no visible confirmation at all.
- **Fix:** Removed the `st.rerun()` call from the success branch only (error branches never called it, matching the plan's own wording, which is unaffected). The handler now falls through into the same script execution's render section, which uses the already-in-memory `rows` list (fetched before the handler ran, unaffected by the DB write) to render the enrolled row with its green badge in that same pass. The row naturally drops out of the table on the *next* natural rerun (e.g. the following checkbox toggle), exactly matching 04-UI-SPEC.md's own documented behavior.
- **Files modified:** `pages/review_queue_page.py`
- **Verification:** Ran a Streamlit `AppTest` simulation (pre-seeding `pending_approval` to sidestep AppTest's separate, documented inability to simulate multi-turn `@st.dialog` interactions — see Issues Encountered) with mocked `create_contacts_bulk`/`add_contacts_to_sequence` returning one enrolled and one skipped contact. Confirmed output: `approve_result` correctly populated, `st.success("1 contact enrolled, 1 skipped.")` rendered, the enrolled row rendered as `:green-badge[:material/check_circle: Enrolled]`, the skipped row rendered as `:orange-badge[:material/error: Skipped — contacts_active_in_other_campaigns]` with its checkbox still present, and the database showed the enrolled prospect at `status='sequenced'` with `apollo_contact_id` set while the skipped prospect remained at `status='drafted'` with no `apollo_contact_id`.
- **Committed in:** `8c28770` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix, a plan instruction that would have made a required must-have behavior unobservable)
**Impact on plan:** Necessary for correctness — without this fix, the D-07/D-12 "green Enrolled badge" must-have truth and the phase's "real per-contact confirmation" success criterion would never actually be visible to a teammate, even though all the underlying data (DB status transitions, `approve_result`) would still be correct. No scope creep; every other instruction in both tasks was followed exactly as written and verified against the full acceptance-criteria grep suite.

## Issues Encountered

- **Streamlit `AppTest` cannot simulate multi-turn `@st.dialog` interactions.** Attempting to fully automate the click-Approve -> click-Confirm-Enrollment flow through `AppTest` failed: clicking the dialog's own "Confirm Enrollment" button had no effect, because `@st.dialog`-decorated functions are implemented as fragments (`streamlit/elements/dialog_decorator.py`), and — per Streamlit's own documentation and confirmed by reproducing the exact official `st.dialog` example from that same docstring under `AppTest` — a dialog only reopens on a subsequent script run if the *original calling code path* (`if st.button(...): my_dialog(...)`) evaluates `True` again, which it doesn't on the rerun triggered by a widget click *inside* the dialog. This is a known limitation of the `AppTest` testing tool, not a bug in this page's code (the page follows Streamlit's own canonical dialog pattern verbatim, and the initial dialog-open step — clicking "Approve All", seeing the modal with the exact locked wording "Enroll N contacts into the {Path} sequence?" render correctly — was verified successfully). Worked around this by pre-seeding `st.session_state["pending_approval"]` (and the path-scope sentinel `_approve_scope_path`, to avoid the page's own path-change-reset logic wiping it on the very first run) directly before calling `AppTest.run()`, which exercises the approval handler's real logic end-to-end without depending on the dialog's own internal click-handling. The dialog-open half of the flow (rendering, exact copy, button presence) was separately verified via a live `AppTest` run through the "Approve All" click.
- **No pre-existing `.venv` in this worktree** (gitignored, per-checkout, matching 04-06's SUMMARY note) — created one from `/usr/local/bin/python3.13` (the real system interpreter; `.venv/bin/python3.13`'s inherited `PATH` pointed at the *main repo's* venv, and a bare `python3 -m venv` on this machine resolves to a stray Python 3.14, matching 04-RESEARCH.md's Pitfall 4) and installed `requirements.txt`/`requirements-dev.txt` before running any verification commands.

## User Setup Required

None — no external service configuration required. This plan's four new secrets are documented in `.streamlit/secrets.toml.example` with placeholder values only; plan 04-05 is explicitly responsible for resolving the real Apollo sequence IDs and sending-mailbox account id via a live human-verify checkpoint. (A local `.streamlit/secrets.toml` with dummy values and a transiently-seeded `db/outreach.db` were created in this worktree only, for `py_compile`/`AppTest`-based smoke testing; both are gitignored, were never committed, and were deleted after verification completed.)

## Next Phase Readiness

- The full approve-to-enrolled vertical slice is code-complete and unit/AppTest-verified against mocked Apollo responses; 04-05 is where the real Apollo sequence IDs, the real sending-mailbox id, and the real `add_contacts_to_sequence`/`bulk_create` response shapes (04-RESEARCH.md Open Question 2 — exact `skipped_contact_ids` reason-code strings) get confirmed against a live account.
- `approve_disabled` (driven by a missing secret or an unresolved custom field) is the single gate 04-05's live-verify checkpoint should exercise first — pointing the four new secrets at real values should immediately unblock the Approve buttons with no further code changes needed.
- The `st.dialog` AppTest limitation documented above only affects *this worktree's automated verification*; it does not affect real end-user behavior (Streamlit's production dialog fragment mechanism is unaffected) and does not need to be revisited unless a future plan wants CI-level automated coverage of the full confirm-to-enroll click path (which would require either a real browser-driven test like Playwright, or restructuring the confirm step to avoid `@st.dialog`, neither of which this plan's scope calls for).

## Self-Check: PASSED

- FOUND: pages/review_queue_page.py (checkboxes, dialog, approval handler, badges all present)
- FOUND: .streamlit/secrets.toml.example (four new secret keys present)
- FOUND commit b80252b
- FOUND commit 8c28770
- Full test suite: all tests passed (verified via `.venv/bin/python3.13 -m pytest -q`, exit code 0)

---
*Phase: 04-review-queue-and-sequence-enrollment*
*Completed: 2026-09-18*
