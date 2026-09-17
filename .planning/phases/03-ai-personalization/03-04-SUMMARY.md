---
phase: 03-ai-personalization
plan: 04
subsystem: ui
tags: [streamlit, anthropic, claude-haiku, prompt-grounding, session-state]

# Dependency graph
requires:
  - phase: 03-ai-personalization (plan 02)
    provides: "personalization/generator.py (build_opening_line, make_client, should_warn_fallback_rate), personalization/templates.py (assemble_email)"
  - phase: 03-ai-personalization (plan 03)
    provides: "db/schema.py idempotent draft-column migration, db/prospects.py update_draft()"
provides:
  - "pages/discovery_page.py: draft generation auto-chained into Enrich & Continue (D-01), self-clearing st.progress indicator, per-contact 'View draft' expanders (D-02/D-03), D-16 fallback-rate warning banner"
  - "personalization/generator.py: PATH_FRAMING map + path_slug parameter on generate_opening_line/build_opening_line (path-aware business framing, live-discovered fix)"
affects: [phase-04-review-enrollment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Session-state result dict (draft_result), initialized None, keyed error/rows/fallback_count/total, mirroring find_result/enrich_result"
    - "st.empty() placeholder holding st.progress, cleared after the loop (mirrors this page's existing st.spinner self-clearing convention)"
    - "Path-aware prompt injection: a fixed per-path <framing> instruction alongside <contact> tags, kept strictly separate from D-06's fact-grounding scope"

key-files:
  created: []
  modified:
    - pages/discovery_page.py
    - personalization/generator.py
    - tests/test_personalization.py

key-decisions:
  - "Ran this plan's executor on the main working tree (no worktree isolation) because Task 2's blocking human-verify checkpoint needs a real `streamlit run app.py` against `.streamlit/secrets.toml`, which is gitignored and would not exist in an isolated worktree checkout"
  - "Fixed the live st.subheader crash by dropping the unsupported icon kwarg rather than bumping the Streamlit version pin -- smaller blast radius, no compatibility audit needed elsewhere in the app"
  - "Fixed the client_sourcing framing bug by adding a path_slug parameter and PATH_FRAMING instruction map rather than loosening D-06's grounding scope -- the bug was a missing business-purpose instruction, not a new fact the model was allowed to assert about the contact, so the hallucination-risk boundary D-06 established is untouched"

patterns-established:
  - "Business-framing instructions (what the email is asking for) are threaded as a separate prompt parameter (path_slug) from fact-grounding instructions (what the model may assert about the contact) -- keeps the two concerns auditable independently"

requirements-completed: [PERS-01]

# Metrics
duration: ~13min active execution (across 3 commits); checkpoint spanned a longer wall-clock gap while the developer added Anthropic API credits and completed the human sample-review
completed: 2026-09-17
---

# Phase 3 Plan 4: Discovery Page Draft-Generation Wiring Summary

**Draft generation auto-chained into "Enrich & Continue" (pages/discovery_page.py) with a live-verified, path-aware Claude Haiku opening line per contact, persisted to SQLite and rendered as per-contact "View draft" expanders — completing Phase 3's vertical slice.**

## Performance

- **Duration:** ~13 min of active code changes across 3 commits (23:46:54 -> 23:59:13 local time); the plan then paused at its `checkpoint:human-verify` gate for the developer to add Anthropic API credits and complete the manual no-hallucination sample review before final approval
- **Started:** 2026-09-16T23:46:54-07:00 (approx, Task 1 commit)
- **Completed:** 2026-09-17 (developer approval + close-out)
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 3 (`pages/discovery_page.py`, `personalization/generator.py`, `tests/test_personalization.py`)

## Accomplishments
- `pages/discovery_page.py`'s existing "Enrich & Continue" handler now chains draft generation automatically (D-01) immediately after `insert_enriched()` succeeds -- no second button, no confirmation step
- A self-clearing `st.progress` indicator (`st.empty()` placeholder) reads `Personalizing drafts... N/M` and disappears once the batch finishes
- Every enriched contact gets a persisted draft (`update_draft()` advances `status='drafted'`) and a collapsed `View draft — {Name} ({Company})` expander rendering the full assembled `Subject:` + body as one continuous `st.code` block (D-02/D-03) — no split AI-part/template-part sections, no per-row AI-vs-fallback label
- A non-blocking `st.warning` banner surfaces when `should_warn_fallback_rate()` trips (D-16); the page never calls `st.stop()` at any point in this flow
- **Live-verified end to end by the developer**: after two rounds of live testing (rendering confirmed clean, then real AI output confirmed correct once Anthropic credits were added), the developer sampled real generated openers across `client_sourcing` and `club_sponsorship`, confirmed correct grounding and framing, and explicitly approved. Sample evidence (client_sourcing, contact "Rita" at "Runtime Revolution"):
  > Hi Rita,
  >
  > We're a student consulting team interested in supporting Runtime Revolution with development resources on an internal project, and thought you might be the right person to explore this with.

## Task Commits

Each task was committed atomically:

1. **Task 1: Chain draft generation into Enrich & Continue and render the Email Drafts section** - `717b836` (feat)
2. **Fix (found live during Task 2's checkpoint): drop unsupported `icon` kwarg from `st.subheader`** - `0aaa304` (fix)
3. **Fix (found live during Task 2's checkpoint): make opening-line generation path-aware** - `ea6c904` (fix)

**Plan metadata:** (this commit) - `docs: complete plan`

_Note: Task 2 (`checkpoint:human-verify`) has no code commit of its own — it is the developer's live verification pass, which surfaced the two fixes above and then approved the final result._

## Files Created/Modified
- `pages/discovery_page.py` — imports `build_opening_line`/`make_client`/`should_warn_fallback_rate`/`assemble_email`/`update_draft`; adds `anthropic_key` module-level read; adds `draft_result` session-state slot (init `None`, reset alongside `enrich_result` on a new search); chains the per-contact Haiku loop inside the "Enrich & Continue" handler's success branch; renders the D-16 banner, divider, "Email Drafts" subheader, and per-contact expanders
- `personalization/generator.py` — adds `PATH_FRAMING` map and a required `path_slug` parameter on `generate_opening_line()`/`build_opening_line()`, injecting a fixed per-path business-framing instruction into the prompt alongside the existing `<contact>` tags
- `tests/test_personalization.py` — updates all 4 existing `generate_opening_line`/`build_opening_line` call sites to pass `path_slug="club_sponsorship"` (preserving prior expected behavior); adds `test_client_sourcing_framing_reaches_prompt` asserting the client_sourcing-specific framing sentence reaches the prompt sent to the mocked client, and that a different path's framing sentence is used instead when `path_slug` differs

## Decisions Made
- **Executor ran on the main working tree, not an isolated worktree** — Task 2's blocking checkpoint requires a real `streamlit run app.py` against `.streamlit/secrets.toml`, which is gitignored/untracked and would not exist in a fresh worktree checkout. Running on the main tree meant the developer's real secrets were immediately usable.
- **Dropped the `icon` kwarg rather than upgrading Streamlit** — see Deviations below; chosen for minimal blast radius given the project pins `streamlit==1.59.2`.
- **Added `path_slug` + `PATH_FRAMING` rather than loosening D-06** — see Deviations below; framing (the email's business purpose) is a fixed instruction, not a new fact about the contact, so it does not reopen the hallucination-risk surface D-06 was designed to close.

## Deviations from Plan

Both deviations below were caught **live during the Task 2 human-verify checkpoint**, not by automated tests — this is expected and matches 03-RESEARCH.md's own flagged limitation that grounding/rendering quality is inherently probabilistic and UI behavior has no component-test harness in this stack.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dropped unsupported `icon` kwarg from `st.subheader`, caused a live TypeError crash**
- **Found during:** Task 2, the developer's first live click-through of the checkpoint (`streamlit run app.py`)
- **Issue:** `03-UI-SPEC.md` locked `st.subheader("Email Drafts", icon=":material/drafts:")` verbatim, but the project's pinned `streamlit==1.59.2` (`requirements.txt`, confirmed against the actual `python3.13` interpreter that `.venv/bin/streamlit`'s shebang runs — a separate, stray `python3.14`/streamlit-1.64.0 environment under the same `.venv` was shadowing `python`/`python3` and would have given a misleading version check). Reading `heading.py`'s `subheader()` signature directly in the pinned 1.59.2 site-packages confirmed no `icon` parameter exists on `header`/`subheader`/`title` at that version — only `alert.py`'s `error`/`warning` and `layouts.py`'s `expander` support `icon`. The developer hit `TypeError: HeadingMixin.subheader() got an unexpected keyword argument 'icon'` the moment the drafts section tried to render.
- **Fix:** Dropped the `icon` kwarg, keeping the plain `st.subheader("Email Drafts")`. Plan's own acceptance criteria only requires the literal `st.subheader("Email Drafts"` call to appear once and does not pin the icon kwarg in its grep checks, so this is a spec/dependency-version mismatch fix, not a plan-contract violation.
- **Files modified:** `pages/discovery_page.py`
- **Verification:** `python3.13 -m py_compile` clean; full `pytest -q` (23/23, no regressions); headless `streamlit.testing.v1.AppTest` render with `at.exception` empty; live restart of the Streamlit process confirmed clean boot (`curl` returns `HTTP 200`, no traceback in the boot log)
- **Committed in:** `0aaa304`

**2. [Rule 1 - Bug] Made opening-line generation path-aware — client_sourcing was producing a nonsensical "we want to learn from you" opener**
- **Found during:** Task 2, the developer's second live verification round, after real Anthropic API output became available. Developer's exact words on the original output: *"this is not good - doesnt make sense. we want to solve for them we dgaf ab their approach to recruiting."*
- **Issue:** `generate_opening_line()`/`build_opening_line()` only ever took `title`/`company` — the single generic `SYSTEM_PROMPT` had no awareness of which of the three outreach paths it was writing for. That framing is correct for `club_sponsorship`/`productthon` (the email asks the company to sponsor, so "genuine interest in their work" fits), but wrong for `client_sourcing`, whose template pitches the *opposite*: the student org offering a free consulting team to help the company, not asking to learn from it. The generic prompt defaulted to a sponsorship-style "learn about your approach" framing regardless of path, which read as actively wrong for `client_sourcing`.
- **Fix:** Added a `PATH_FRAMING` map (`personalization/generator.py`) with one fixed business-framing instruction sentence per path, injected into the prompt as a `<framing>` tag alongside the existing `<contact>` tags. `generate_opening_line()`/`build_opening_line()` gained a required `path_slug` parameter; `pages/discovery_page.py`'s call site now passes the already-computed `slug`. **Important:** this is not a D-06 grounding-scope change — `PATH_FRAMING` never adds a new fact the model may assert about the contact (still title/company only); it fixes a missing business-purpose instruction, a fundamentally different axis from D-06's fact-grounding restriction.
- **Files modified:** `personalization/generator.py`, `pages/discovery_page.py`, `tests/test_personalization.py`
- **Verification:** `python3.13 -m py_compile` clean; full `pytest -v` (24/24 — 23 prior + 1 new test asserting the client_sourcing-specific framing sentence reaches the prompt and is absent for a different path); live re-verification by the developer against real Anthropic output across both `client_sourcing` and `club_sponsorship` paths, explicitly approved with a pasted sample draft
- **Committed in:** `ea6c904`

---

**Total deviations:** 2 auto-fixed (2 bug fixes, both Rule 1, both caught live during the human-verify checkpoint rather than by automated tests)
**Impact on plan:** Both fixes were necessary for the checkpoint to pass at all — the first was a hard crash blocking any verification, the second was a business-correctness bug the plan's own success criteria (assembled draft must be trustworthy before send) would not have passed without. No scope creep beyond what was required to make the checkpoint's own pass/fail criteria achievable.

**Gap worth flagging for future prompt-design work:** `03-CONTEXT.md`'s D-05/D-06 scoped which *facts* the AI opening line may reference (title/company only) but never addressed that the *rhetorical angle/framing* also needs to vary by outreach path. This gap wasn't caught until a real generated draft was read by a human during the live checkpoint — future phases that touch prompt design across multiple business-purpose paths should explicitly scope per-path framing during discuss-phase, not just grounding-field scope, so this class of bug is caught in planning rather than live verification.

## Issues Encountered
None beyond the two deviations documented above, both resolved and re-verified before developer approval.

## User Setup Required

**`[SPONSORSHIP_LINK]` is still an unresolved literal placeholder (D-11)** in `personalization/templates.py`'s `club_sponsorship` and `productthon` templates (carried over from plan 03-02, still unresolved as of this plan's completion). Before any real campaign send, the teammate must host the sponsorship deck/prospectus — see `tmp/Product Space UW — Sponsorship Prospectus.docx`, `tmp/Sponsorship Deck - Presentation.pdf`, `tmp/UW PS Portfolio Brochure (Spring).pdf` — somewhere accessible (Google Drive/Notion/etc.) and replace the literal `[SPONSORSHIP_LINK]` string in `personalization/templates.py` with the real hosted URL. This is a manual setup step, not a build gap.

**Anthropic account credits:** during this plan's checkpoint, the developer's Anthropic account temporarily ran out of API credits (confirmed via a live HTTP 400 "Your credit balance is too low"), which correctly triggered the D-14 fallback path (generic opener, no crash) rather than breaking the app. Credits have since been added and real AI output is confirmed working — flagging here only as a reminder that campaign volume should be monitored against account balance going forward, not as an unresolved blocker.

## Next Phase Readiness
- Phase 3 (AI Personalization) is now fully complete: every requirement (PERS-01) is shipped and live-verified across plans 03-02 (generator + templates), 03-03 (schema + persistence), and 03-04 (this plan, the page-level wiring and live checkpoint).
- Phase 4 (Review Queue and Sequence Enrollment) can now build directly on `status='drafted'` rows with populated `opening_line`, `draft_source`, and `first_name` columns.
- No blockers for Phase 4. The one open item (`[SPONSORSHIP_LINK]`) is a manual user-setup task outside any phase's code scope, and does not block Phase 4's start (only blocks a real production send of the two sponsorship-path templates).

---
*Phase: 03-ai-personalization*
*Completed: 2026-09-17*

## Self-Check: PASSED

All claimed files verified present on disk (`pages/discovery_page.py`, `personalization/generator.py`, `tests/test_personalization.py`, `.planning/phases/03-ai-personalization/03-04-SUMMARY.md`). All three commits (`717b836`, `0aaa304`, `ea6c904`) verified present in `git log`.
