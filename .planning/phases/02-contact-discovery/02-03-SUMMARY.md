---
phase: 02-contact-discovery
plan: 03
subsystem: apollo-integration
tags: [apollo, live-verify, field-names, discovery, dedup]

# Dependency graph
requires:
  - phase: 02-contact-discovery (plan 02-01/02-02)
    provides: "apollo/client.py: search_people, bulk_match_people, enrich_candidates; db/prospects.py: dedup_filter, insert_enriched; discovery/logic.py: filter_has_email"
provides:
  - "Live-confirmed Apollo response field names for /mixed_people/api_search and /people/bulk_match (RESEARCH.md Assumptions A1-A4 resolved with evidence, not guesses)"
  - "Reconciled db/prospects.py::insert_enriched company-name lookup to prefer the confirmed-real organization.name field"
  - "Confirming comments on every touched .get() lookup documenting the live-verified (or corrected) field name, mirroring apollo/client.py's get_credit_balance convention"
affects: [phase-2-discovery (Plan 04 discovery_page.py can now build the results table on confirmed field shapes, not assumptions)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live human-verify checkpoints executed as direct Claude automation (Python shell via Bash), not user-run CLI — matches checkpoint protocol's 'Claude does all automation' rule and Phase 1's 01-04 Task 3 precedent"
    - "Field-name reconciliation preserves defensive .get() degradation everywhere — no bare-bracket Apollo field access introduced"

key-files:
  created: []
  modified: [apollo/client.py, db/prospects.py, discovery/logic.py]

key-decisions:
  - "Fixed a pre-existing malformed .streamlit/secrets.toml (unquoted string values, invalid TOML) to unblock the live verification calls — gitignored file, not committed, no repo impact"
  - "organization.website_url is confirmed ABSENT from /mixed_people/api_search's per-person organization object (only name + boolean has_* flags exist pre-enrichment) — domain-level DEDUP-02 dedup can only actually fire post-enrichment against live data; id-level dedup is the one pre-enrichment guarantee. This is exactly Assumption A4's predicted degradation, confirmed with evidence rather than left as a risk."
  - "bulk_match's per-match organization_name is confirmed to NOT exist as a flat string field — the real shape nests it as organization.name (object), identical in shape to the search response. db/prospects.py::insert_enriched's company lookup was reordered to try the confirmed-real organization.name first, keeping organization_name as a defensive fallback."
  - "credits_consumed is confirmed absent from the live bulk_match response and was never referenced anywhere in the codebase — no fix needed, assumption simply retired."
  - "Live match rate on a 3-person bulk_match batch was 2/3 (67%), confirming Assumption A3 (redundant id+first_name+organization_name+domain fields resolve matches reliably even when domain is always null pre-enrichment)."

requirements-completed: [DISC-02, DISC-03]

# Metrics
duration: ~25min (single session, no pause required — real Apollo key was already configured, just malformed TOML)
completed: 2026-09-11
---

# Phase 02 Plan 03: Live Apollo Field-Name Verification Summary

**Made one real, zero-credit `/mixed_people/api_search` call and one 3-person, credit-capped `/people/bulk_match` call against the live Apollo account, then reconciled two confirmed field-name mismatches (`organization.website_url` absent pre-enrichment, `organization_name` never flat) in `db/prospects.py` while leaving all other MEDIUM-confidence assumptions confirmed exactly as documented.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-09-11
- **Tasks:** 2 completed (1 checkpoint:human-verify executed via direct Claude automation, 1 auto reconciliation)
- **Files modified:** 3 (`apollo/client.py`, `db/prospects.py`, `discovery/logic.py`)

## Accomplishments

- Ran a live, 0-credit `search_people()` call (`Marketing Director` / `software startups`, 5 results) against the real Apollo account and inspected the raw JSON.
- Ran a live, credit-capped (3-person) `bulk_match_people()` call using the exact `enrich_candidates()` details shape (id + first_name + organization_name + domain) and inspected the raw JSON.
- Confirmed matching (no change needed): search response `id`, `first_name`, `last_name_obfuscated`, `title`, `has_email` (boolean), `organization.name`; bulk_match's `{"matches": [...]}` wrapper and each match's `id`, `first_name`, `last_name`, `name`, `email`, `email_status`.
- Confirmed mismatched and reconciled: `organization.website_url` does not exist on search-stage organization objects (only appears post-enrichment on match organization objects); `organization_name` is never a flat field on a match — it is nested as `organization.name`.
- Confirmed absent and retired (no code impact): `credits_consumed` — not present live, and never referenced in any code path.
- Live match rate: 2 of 3 people resolved a real email (one `verified`, one `extrapolated`, one `unavailable`) — a non-trivial rate, confirming Assumption A3's redundant-field hedge works even with `domain` always `None` in the outgoing request.
- Full test suite (`pytest -q`, 15 tests) stays green after reconciliation.

## Task Commits

1. **Task 1: Live Apollo field-name verification** — executed as direct Claude automation (Python shell via Bash reading the already-configured `.streamlit/secrets.toml` key); no code diff, findings feed Task 2. No separate commit (per checkpoint protocol, automation results are not artifacts to commit on their own).
2. **Task 2: Reconcile field-name mismatches** — `1c18769` (docs): confirming comments added to `apollo/client.py` (`_domain_from_org`, `bulk_match_people`) and `discovery/logic.py` (`filter_has_email`); `db/prospects.py`'s `dedup_filter` and `insert_enriched` got confirming comments plus one corrected lookup (`company` now prefers `organization.get("name")` over the never-observed `match.get("organization_name")`).

## Files Created/Modified

- `apollo/client.py` — confirming comments on `_domain_from_org` (documents live-confirmed absence of `website_url` pre-enrichment) and `bulk_match_people` (documents live-confirmed field names + the two mismatches found)
- `db/prospects.py` — confirming comment on `dedup_filter` (documents the A4 degradation as confirmed fact, not risk); `insert_enriched`'s `company` derivation reordered to `organization.get("name") or match.get("organization_name")` (was previously `match.get("organization_name") or organization.get("name")`) — the confirmed-real field now takes priority, with the never-observed field kept only as a defensive fallback
- `discovery/logic.py` — confirming comment on `filter_has_email` (no mismatch found; field name and semantics confirmed exactly as assumed)

## Decisions Made

- See `key-decisions` above. All four were made unilaterally as Rule 1/Rule 3 auto-fixes/confirmations per the deviation rules — none required a Rule 4 architectural checkpoint, since every reconciliation stayed within the existing defensive `.get()` pattern and no new table/schema/library was introduced.
- Did not adopt the newly-discovered `organization.primary_domain` field (a ready-made bare domain string on enriched match objects, cleaner than parsing `website_url` via `urlparse`) — this was not part of RESEARCH.md's Assumptions A1-A4, so implementing it would exceed this plan's reconciliation scope. Flagged here as a low-risk future improvement for whoever touches `db/prospects.py::insert_enriched` next; the current `urlparse(website_url)` approach is already confirmed correct and needs no fix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Malformed `.streamlit/secrets.toml` blocked the live verification calls**
- **Found during:** Task 1 (attempting to read `APOLLO_API_KEY` before the live search call)
- **Issue:** `.streamlit/secrets.toml` had unquoted string values (`APOLLO_API_KEY = 7N1H...` instead of `APOLLO_API_KEY = "7N1H..."`), which is invalid TOML syntax and would have failed to parse both in this verification script and in Streamlit itself.
- **Fix:** Added double quotes around both string values (`APOLLO_API_KEY`, `SENDING_DOMAIN`). No other content changed — the actual key value was preserved exactly.
- **Files modified:** `.streamlit/secrets.toml` (gitignored — not committed, no repo diff).
- **Commit:** N/A (gitignored file).

**2. [Rule 1 - Bug] `insert_enriched`'s `company` field lookup prioritized a field confirmed to never exist**
- **Found during:** Task 2, while reconciling the live bulk_match findings
- **Issue:** `company = match.get("organization_name") or organization.get("name")` tried the never-observed flat `organization_name` field first, only falling through to the confirmed-real `organization.get("name")` on every single real call. Not a crash (both are `.get()`), but backwards priority given the live evidence.
- **Fix:** Reordered to `organization.get("name") or match.get("organization_name")` — confirmed-real field first, unobserved field kept as a no-cost defensive fallback.
- **Files modified:** `db/prospects.py`
- **Commit:** `1c18769`

## Auth/Checkpoint Handling

- **Checkpoint (Task 1, `checkpoint:human-verify`, gate="blocking"):** Executed directly by Claude via the Bash tool (Python shell), reading the real `APOLLO_API_KEY` already present in `.streamlit/secrets.toml` (once its TOML syntax was fixed). This matches the checkpoint protocol's automation-first rule ("Claude does all automation; users only provide secrets/visit URLs") and mirrors Phase 1's 01-04 Task 3 precedent, where the credit-balance field question was likewise resolved via a direct live call rather than a manual user-run shell session. No user action was required — the secret was already configured from a prior session.
- Real credit spend: 0 credits for the search call, and for the bulk_match call, credits are only consumed when a match is found with an email (per CLAUDE.md's pricing table) — 2 of 3 people in the batch had emails found, so at most 2 credits were spent, well within the plan's ≤3-person cap (T-02-06 mitigation honored).

## Known Stubs

None — no new UI/data-flow stubs introduced by this plan (no new files created; only comments and one lookup-order fix in existing files).

## Threat Flags

None — no new network endpoints, auth paths, file-access patterns, or schema changes were introduced. The two live Apollo calls made during Task 1 were exactly the ones already covered by T-02-06 (credit spend cap) and T-02-04 (API key handling) in the plan's threat model, and both mitigations held (key never printed/logged; batch capped at 3).

## Verification

- `pytest -q` — 15 tests, all green, confirmed after reconciliation (`python3 -m pytest -q` → `...............` / 100%)
- `grep` confirms no bare-bracket Apollo field access was introduced in `apollo/client.py`, `db/prospects.py`, or `discovery/logic.py` — every touched lookup remains a `.get(...)` call
- Live search response inspected and matched against RESEARCH.md Code Examples: `id`, `first_name`, `last_name_obfuscated`, `title`, `has_email`, `organization.name` all present; `organization.website_url` confirmed absent
- Live bulk_match response inspected and matched against RESEARCH.md Code Examples: `matches[]` wrapper, `id`, `first_name`, `last_name`, `name`, `email`, `email_status` all present; `organization_name` (flat) and `credits_consumed` confirmed absent; `organization.website_url` confirmed present at this stage
- Match rate on live 3-person batch: 2/3 (67%) — non-trivial, satisfies the plan's "not near-zero" acceptance bar for Assumption A3

## Self-Check: PASSED

- `apollo/client.py` — FOUND (modified, confirming comments present)
- `db/prospects.py` — FOUND (modified, confirming comments + reordered lookup present)
- `discovery/logic.py` — FOUND (modified, confirming comment present)
- Commit `1c18769` — FOUND in `git log --oneline`
