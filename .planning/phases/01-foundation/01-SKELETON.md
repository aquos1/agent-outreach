# Walking Skeleton — Outreach Agent

**Phase:** 1 (Foundation)
**Generated:** 2026-07-20

## Capability Proven End-to-End

A teammate runs `streamlit run app.py` and lands on a System Health page that reports live Apollo API-key validity, remaining credit balance, and mailbox deliverability (SPF/DMARC/DKIM) — backed by a SQLite registry that is auto-created on first launch and persists across restarts. This exercises the full stack: Streamlit UI → in-process Apollo REST client → public DNS client → local SQLite persistence, with secrets read from `st.secrets`.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | Streamlit 1.59.2 (single-process UI + server) | CLAUDE.md locked stack; one process renders UI and runs backend logic — no separate API server. Free Community Cloud hosting, `st.secrets` keeps keys off disk/git. |
| Routing | `st.navigation` + `st.Page` (programmatic) | Enables the D-01 runtime gate (hide/show pages based on the Apollo health check) that the older `pages/` folder convention cannot do. Phase 2+ appends pages at the extension point in `app.py`. |
| Data layer | SQLite via stdlib `sqlite3`, file at `db/outreach.db` | CLAUDE.md locked; zero infra for <500 prospects/week. Idempotent `ensure_schema()` (`CREATE TABLE IF NOT EXISTS`; `DROP VIEW IF EXISTS` + `CREATE VIEW`) runs at every boot. |
| External API client | `requests` 2.34.2, synchronous, `x-api-key` header | Apollo is plain REST/JSON; no SDK. Two calls: `auth/health` (validity gate, D-01) and `usage_stats/api_usage_stats` (credits, D-03). |
| Mailbox checks | `dnspython` 2.8.0 TXT lookups against `SENDING_DOMAIN` | Apollo exposes no SPF/DKIM/DMARC endpoint. SPF/DMARC are authoritative pass/fail; DKIM is best-effort selector brute-force with a soft "unknown" + manual self-attestation fallback (RFC 6376 has no selector enumeration). |
| Auth | None at app level (Apollo master key only) | Internal student-org tool; Community Cloud restricts access at the GitHub-account level. No Auth0/Clerk per CLAUDE.md. |
| Secrets | `st.secrets` / `.streamlit/secrets.toml` (gitignored); template `.streamlit/secrets.toml.example` committed | Keys never in code or git; `APOLLO_API_KEY`, `SENDING_DOMAIN`. |
| Deployment target | Streamlit Community Cloud (later); local `streamlit run app.py` for dev | Free, deploys from GitHub; SQLite persists within a deployment. Phase 1 ships the documented local full-stack run command. |
| Directory layout | Package-per-concern: `db/`, `apollo/`, `mailbox/`, `pages/`, `tests/`; `app.py` entrypoint | Matches RESEARCH.md Recommended Project Structure; each external boundary isolated in its own module for independent testing. |
| Test framework | pytest 9.0.2, `testpaths=["tests"]` in `pyproject.toml`, network mocked | Wave 0 test infra; per-task `pytest tests/ -x -q`, full suite before verify. |

## Stack Touched in Phase 1

- [x] Project scaffold — `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.gitignore`, `.streamlit/config.toml`, package markers (Plan 01-01)
- [x] Routing — `st.navigation` with a default `System Health` page, Apollo-gated (Plan 01-04)
- [x] Database — real write (prospect INSERT) AND real read (`contacted_registry` view / SELECT after reconnect) proven idempotent and persistent (Plan 01-02)
- [x] UI — interactive `Recheck Connection` button + DKIM self-attestation checkbox wired to the check functions (Plan 01-04)
- [x] Deployment — documented local full-stack run: `pip install -r requirements.txt && streamlit run app.py` (Community Cloud deployment deferred)

## Out of Scope (Deferred to Later Slices)

- Contact discovery, Apollo People Search, enrichment, credit-gated spending (Phase 2)
- AI personalization / Claude Haiku opening lines (Phase 3)
- Review queue, contact creation, sequence enrollment (Phase 4)
- Analytics polling, open/reply rates (Phase 5)
- Deep email-auth validation (SPF `include:` chain / 10-lookup limit via `checkdmarc`) — Phase 1 does presence-only pass/fail
- Any send/enroll action gated by the D-02 soft mailbox block — no such action exists until Phase 4
- Streamlit Community Cloud production deployment + secrets-console setup
- Populating `prospect.company_domain` from live Apollo responses (Phase 2 — the column exists now)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2 (Contact Discovery): adds a path-selection + targeting page under `st.navigation`; writes `prospect` rows; reads `contacted_registry` for DEDUP-02.
- Phase 3 (AI Personalization): adds the Anthropic client (`anthropic` SDK) and a draft-per-contact view; writes `drafted` status.
- Phase 4 (Review Queue + Enrollment): adds the review-queue page, Apollo contact creation + sequence enrollment; the D-02 mailbox soft-block first gates a real send action here.
- Phase 5 (Analytics Dashboard): adds a polling job populating `email_events` and a dashboard page reading open/reply rates.
