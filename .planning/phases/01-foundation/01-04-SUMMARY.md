---
phase: 01-foundation
plan: 04
subsystem: ui
tags: [streamlit, apollo, health-check, entrypoint, human-verify]

# Dependency graph
requires:
  - phase: 01-foundation (plan 01-02)
    provides: "db/schema.py: ensure_schema()"
  - phase: 01-foundation (plan 01-03)
    provides: "apollo/client.py: check_apollo_health, get_credit_balance; mailbox/dns_checks.py: check_spf, check_dmarc, check_dkim"
provides:
  - "app.py: Streamlit entrypoint — schema boot, secrets-presence gate, st.navigation routing to health page"
  - "pages/health_page.py: System Health landing page rendering all three D-01/D-02/D-03 gated checks"
  - "Live-verified: real Apollo Master API key path, DB auto-create, bad-key banner hard-block, Apollo Credits permanent-unavailable behavior"
affects: [phase-2-discovery (app.py's st.navigation extension point for new pages), all future phases (health page is the app's default landing surface)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "app.py owns schema boot + secrets-presence gate + navigation only; health_page.py owns the Apollo hard-block + all check rendering (separation kept so credit/mailbox sections can render once Apollo passes)"
    - "D-01/D-02/D-03 gating: Apollo connection is the only st.stop() in the page; credits and mailbox checks always render regardless of pass/fail"

key-files:
  created: [app.py, pages/health_page.py]
  modified: [apollo/client.py]

key-decisions:
  - "Resolved RESEARCH.md Open Question #1 definitively: confirmed via live authenticated call that usage_stats/api_usage_stats returns per-endpoint rate-limit consumption, not a credit balance — no 'credits' or 'credit_balance' field exists anywhere in the 70-key response. Apollo does not expose credit balance via any API endpoint (confirmed against docs.apollo.io/docs/api-pricing — dashboard-only, Settings > Billing and credits). Updated apollo/client.py's comment from 'unconfirmed field name, verify' to 'confirmed: this will permanently show unavailable, that is correct D-03 behavior' — no behavior change, since the existing defensive .get() already degrades gracefully exactly as required."
  - "Verified via manual browser testing (user) rather than claude-in-chrome automation — browser extension was declined for this session, so the resume-signal's checklist was walked by the user directly against the running app with screenshots reported back."
  - "Bad-key path was verified incidentally and for free: the user's first secrets.toml attempt still had placeholder values ('your-master-api-key'), which correctly produced the exact plain-language banner ('key present but not recognized as logged in') rather than a crash — this doubled as the SC-2/D-01 bad-key verification step."

requirements-completed: [SC-1, SC-2, SC-3]

# Metrics
duration: ~45min (includes a paused session between task 2 completion and task 3 human-verify)
completed: 2026-07-22
---

# Phase 01 Plan 04: App Entrypoint + Health Page Summary

**Wires the walking skeleton end-to-end: `app.py` boots, auto-creates the SQLite schema, gates on Apollo key validity, and routes to a `System Health` landing page rendering all three checks — live-verified against a real Apollo account.**

## Performance

- **Duration:** ~45 min total (Tasks 1-2 auto; Task 3 spanned a session pause/resume for real credentials)
- **Completed:** 2026-07-22
- **Tasks:** 3 completed (2 auto, 1 human-verify checkpoint)
- **Files modified:** 2 created, 1 modified

## Accomplishments
- `app.py`: boots `ensure_schema()`, gates on `APOLLO_API_KEY` presence with a plain-language banner + `st.stop()`, registers `st.navigation` routing to `pages/health_page.py` as the default page
- `pages/health_page.py`: renders Apollo Connection (hard block, D-01), Apollo Credits (informational, D-03), and Mailbox Deliverability SPF/DMARC/DKIM (soft block, D-02) per the locked UI-SPEC copy/icons
- Live-verified end-to-end against a real Apollo Master API key: connection OK, DB auto-created with all 4 tables (`prospect`, `contacted_registry`, `email_events`, `free_email_domains`), SPF passed, DMARC/DKIM degraded gracefully with actionable copy
- Closed RESEARCH.md Open Question #1 for good: Apollo's `usage_stats/api_usage_stats` endpoint has no credit-balance field at all (confirmed via live call + official docs) — "Credit balance unavailable" is the correct permanent state, not a bug

## Task Commits

1. **Task 1: app.py entrypoint** - `f1ff4b1` (feat)
2. **Task 2: pages/health_page.py** - `bc053b9` (feat)
3. **Task 3: human-verify checkpoint + credit-field comment fix** - this commit (docs/chore)

Tasks 1-2 merged into `main` via `8821dec` in a prior session.

## Files Created/Modified
- `app.py` - Streamlit entrypoint: schema boot, secrets gate, Apollo-gated navigation
- `pages/health_page.py` - System Health page rendering all 3 indicators per UI-SPEC
- `apollo/client.py` - Updated stale "unconfirmed field name" comment to reflect the confirmed live-call finding (no behavior change)

## Decisions Made
- See `key-decisions` above — the credit-field research question is now closed with evidence, not deferred further
- Kept `.streamlit/secrets.toml.example` deletion (pre-existing, untouched by this plan) out of scope — flagged to user, not restored, since it wasn't part of this plan's file set

## Deviations from Plan
None — all 3 tasks completed as specified. The credit-field investigation (plan step 7 of the how-to-verify checklist) was completed as an explicit checklist item, not a deviation.

## Verification
- `streamlit run app.py` opens System Health as the default landing page (D-04) — confirmed via screenshot
- Valid key → three indicators render (SC-1); `db/outreach.db` auto-created with expected schema (SC-3) — confirmed
- Invalid/placeholder key → plain-language banner ("Apollo connection failed — key present but not recognized as logged in."), no traceback, hard block via `st.stop()` (SC-2, D-01) — confirmed
- Credit balance "unavailable" never blocks (D-03); SPF/DMARC/DKIM render warnings but never `st.stop()` (D-02) — confirmed
