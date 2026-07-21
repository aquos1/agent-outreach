# Phase 1: Foundation - Research

**Researched:** 2026-07-20
**Domain:** Streamlit app bootstrap, Apollo.io connectivity/health checks, DNS-based email-auth verification, SQLite schema design for dedup registry
**Confidence:** HIGH (Streamlit patterns, SQLite schema, Apollo auth model) / MEDIUM (Apollo credit-balance field shape, DKIM selector reliability)

## Summary

Phase 1 is a walking skeleton: a single-file (or thin multi-page) Streamlit app that (1) boots, (2) calls Apollo's `auth/health` and `usage_stats/api_usage_stats` endpoints to prove connectivity and surface credit balance, (3) runs DNS TXT lookups against a configured sending domain to approximate SPF/DMARC/DKIM health, (4) creates a SQLite database with a `prospect` + `email_events` schema (extending spec.MD §5) plus a dedup-focused view, and (5) renders all of this as a pass/fail landing page using `st.status`/`st.metric`, gating the rest of the (currently nonexistent) app per D-01/D-02.

The two technically nontrivial pieces are: (a) Apollo's `auth/health` endpoint does **not** return credit balance — that requires a second call to `usage_stats/api_usage_stats`, whose exact response schema is not fully published (MEDIUM confidence, verify live) — and (b) DKIM selector discovery has no reliable DNS-only solution (no wildcard record, no registry of selectors per RFC 6376), so the plan must brute-force a short list of common selectors and treat "no known selector found" as a soft/unknown state rather than a hard fail, exactly as CONTEXT.md's fallback anticipates.

**Primary recommendation:** Build a single Streamlit entrypoint (`app.py`) that on every run (a) ensures the SQLite schema exists (idempotent `CREATE TABLE IF NOT EXISTS`), (b) calls Apollo `auth/health` (blocking gate, D-01) and `usage_stats/api_usage_stats` (informational, D-03), (c) runs DNS checks against a `SENDING_DOMAIN` secret for SPF/DMARC (authoritative) and DKIM (best-effort selector brute-force with manual-attestation fallback), and (d) renders all three as `st.status` blocks feeding into an overall `st.navigation` gate — using `st.stop()` to hard-block the rest of the app only on the Apollo check per D-01.

## Architectural Responsibility Map

This is a single-process Streamlit monolith, not a multi-tier web app — Streamlit's server process renders UI and runs backend logic together. Tiers below are adapted to that reality.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Health status page rendering (pass/fail indicators) | Streamlit App (UI+server, single process) | — | `st.status`/`st.metric` render server-side and stream to the browser; no separate frontend build |
| Apollo API key validation | Streamlit App (in-process API client) | Apollo.io (external service) | App makes the `auth/health` call directly; Apollo owns the actual validity determination |
| Apollo credit balance | Streamlit App (in-process API client) | Apollo.io (external service) | Same client, second endpoint (`usage_stats/api_usage_stats`) |
| Mailbox deliverability (SPF/DKIM/DMARC) | Streamlit App (in-process DNS client via `dnspython`) | Public DNS (external) | No Apollo endpoint exposes this — must query DNS directly against the configured sending domain |
| SQLite schema creation & dedup registry | Local Persistence (SQLite file via stdlib `sqlite3`) | Streamlit App (schema owner, runs `CREATE TABLE IF NOT EXISTS` at boot) | App bootstraps schema on first launch; DB itself is a flat file alongside the app |
| Secrets (`APOLLO_API_KEY`, `SENDING_DOMAIN`) | Streamlit secrets subsystem (`st.secrets`, `.streamlit/secrets.toml` / Community Cloud console) | Streamlit App (reads at boot) | Managed outside application code per Streamlit's built-in secrets convention |

## User Constraints (from CONTEXT.md)

<user_constraints>
### Locked Decisions

- **D-01:** An invalid or missing Apollo API key hard-blocks the entire app — no other screen is usable until `auth/health` passes. Prevents downstream Apollo calls from failing cryptically mid-campaign.
- **D-02:** A failed mailbox deliverability check (SPF/DKIM/DMARC) blocks only the send/enroll step — contact discovery and draft review remain usable. Avoids losing in-progress work over a fixable DNS issue, while still preventing a campaign that can't actually deliver.
- **D-03:** A zero or low Apollo credit balance is informational only — shown clearly on the health page but never blocks. DISC-04 (cost-before-commit at discovery time) is the real spending gate; duplicating that gate here would be redundant.
- **D-04:** The health check page is the default landing screen on every app boot, not an on-demand/settings-tab view. Teammate always sees pass/fail status before touching a campaign.

### Claude's Discretion

- **Mailbox deliverability check method:** Apollo's API does not expose SPF/DKIM/DMARC status directly (confirmed — no such endpoint is documented). Default to a direct DNS TXT-record lookup (SPF/DMARC) and DKIM selector lookup against the configured sending domain, since that's fully automatable without extra user setup. If DKIM selector discovery proves unreliable in practice, fall back to a manual "I've configured this" self-attestation checkbox rather than a flaky automated check.
- **Dedup registry scope (DEDUP-01):** Default to excluding common free/personal email domains (gmail.com, outlook.com, yahoo.com, hotmail.com, icloud.com) from domain-level dedup — only company-owned domains get the "already contacted this company" treatment. Contact-ID-level dedup applies to everyone regardless of domain.
- **Error message design:** Default to banner text with a concrete next step (e.g., "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets") rather than a bare status word, since the audience is non-technical and needs to know what to actually do.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

## Phase Requirements

<phase_requirements>
| ID | Description | Research Support |
|----|-------------|------------------|
| DEDUP-01 | System tracks all previously contacted Apollo contact IDs and company domains in a local registry | SQLite schema below defines `prospect` table with `apollo_person_id`/`apollo_contact_id`/`company_domain` columns, a `free_email_domains` seed table, and a `contacted_registry` view that Phase 2 (DEDUP-02) queries directly — see Code Examples |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.12, Streamlit 1.45+, `requests` for Apollo REST calls, SQLite via stdlib `sqlite3`, Anthropic SDK (later phases only — not this phase).
- Apollo auth via master API key, `x-api-key` header on every request. NOT OAuth.
- Boot-time health check against `GET https://api.apollo.io/api/v1/auth/health`; surface a clear "Apollo connection failed" banner on failure, never a stack trace.
- Secrets via `.streamlit/secrets.toml` (gitignored locally) / `st.secrets` in code; Community Cloud secrets console in production. Never hardcode keys.
- Error handling: 401/403 → banner, never retry; 422 → surface `response.json()["message"]` directly; 429 → exponential backoff, max 3 retries.
- Do NOT use LangChain/LangGraph, FastAPI+React, Postgres/MySQL/MongoDB, Celery/Redis/Airflow, or any parallel email-delivery service — Apollo is the only send path (all "What NOT to Use" table entries apply project-wide, not just to later phases).
- **Note:** `.planning/research/ARCHITECTURE.md` (an earlier, more generic research pass) recommends Next.js + Postgres + pg-boss. This has been superseded — CLAUDE.md's "Recommended Stack" (Streamlit + SQLite + stdlib) is the canonical, locked decision. Ignore the Next.js/Postgres architecture entirely; it does not apply to this project.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| streamlit | 1.59.2 (latest on PyPI; CLAUDE.md floor is 1.45+) [VERIFIED: PyPI registry] | UI + app server | Single-process app; `st.status`, `st.metric`, `st.navigation`/`st.Page` cover the entire health-page + gating requirement natively |
| requests | 2.34.2 (latest on PyPI; CLAUDE.md floor is 2.32+) [VERIFIED: PyPI registry] | Apollo REST calls (`auth/health`, `usage_stats`) | Plain synchronous REST/JSON; no Apollo SDK exists on PyPI |
| dnspython | 2.8.0 (latest on PyPI, matches locally installed dev version) [VERIFIED: PyPI registry] | SPF/DMARC TXT lookups, DKIM selector probing | Standard, mature (20+ year) DNS toolkit; explicitly named in CONTEXT.md discretion guidance |
| sqlite3 (stdlib) | bundled with Python 3.12/3.13 (3.45.3 confirmed locally) [VERIFIED: local interpreter] | Prospect + email_events persistence, dedup registry | No install needed; zero infra per CLAUDE.md |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| checkdmarc | 5.x current on PyPI [ASSUMED — package name from WebSearch, not cross-checked against Context7/official docs] | Optional: more robust SPF chain (nested `include:`) + DMARC policy parsing | Only if raw `dnspython` TXT-record presence checks prove too shallow (e.g., need to validate SPF `include:` chains, not just "a v=spf1 record exists"). **Does not cover DKIM** — confirmed via package docs. Not required for Phase 1's pass/fail-only scope; keep as a v2 upgrade path, not a Phase 1 dependency. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `dnspython` TXT lookups (SPF/DMARC) | `checkdmarc` | `checkdmarc` gives full SPF DNS-lookup-count validation and DMARC RFC compliance parsing, at the cost of an extra dependency for a v1 that only needs binary pass/fail. Recommend deferring. |
| DNS brute-force DKIM selector list | Self-attestation checkbox only (no DNS check at all) | CONTEXT.md's own fallback. Given DKIM selector discovery has no reliable general solution (see Common Pitfalls), a hybrid — try a short common-selector list first, fall back to attestation checkbox if none resolve — gets automated coverage for the common case (Google Workspace `google`, Microsoft 365 `selector1`/`selector2`) without over-promising reliability. |
| SQLite | Google Sheets (`gspread`) | spec.MD explicitly offers this as an alternative for simplicity; SQLite is faster to query for dedup lookups and matches CLAUDE.md's locked decision. Not reconsidered here — SQLite is the constraint, not a research question. |

**Installation:**
```bash
pip install streamlit==1.59.2 requests==2.34.2 dnspython==2.8.0
```

**Version verification:** Confirmed live via `pip3 index versions <package>` against PyPI on 2026-07-20 (see table above). `sqlite3` is stdlib — no separate install. Locally installed dev environment has Python 3.13.2, not the CLAUDE.md-pinned 3.12 (see Environment Availability) — none of the above packages have a hard 3.12 ceiling, but the project's target runtime should still be pinned explicitly (venv or `.python-version`) rather than left to whatever `python3` resolves to.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|--------------|-----------|-------------|
| streamlit | PyPI | 6+ yrs (v0.1 2019) | very high (millions/mo) | github.com/streamlit/streamlit | [OK] | Approved |
| requests | PyPI | 15+ yrs | very high (billions/mo) | github.com/psf/requests | [OK] | Approved |
| dnspython | PyPI | 20+ yrs | very high | github.com/rthalley/dnspython | [OK] | Approved |
| checkdmarc | PyPI | several yrs | low-moderate | github.com/domainaware/checkdmarc | [OK] | Approved (optional/deferred, not installed in Phase 1) |

All four packages scanned `[OK]` via `slopcheck` (PyPI-backed check) on 2026-07-20. No `[SLOP]` or `[SUS]` verdicts. Package names for `streamlit`, `requests`, and `dnspython` also match CLAUDE.md's own locked stack table (project-level decision, not newly sourced this session) — treat those three as `[VERIFIED: PyPI registry]`. `checkdmarc` was discovered via WebSearch during this research session and is not installed by the Phase 1 plan (deferred to a future phase, see Alternatives Considered) — tag `[ASSUMED]` per the package-name provenance rule if it is ever added later; re-verify at that time.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Teammate's browser
      │
      │ HTTP (Streamlit websocket)
      ▼
┌─────────────────────────────────────────────────────────────┐
│  Streamlit process (app.py — single entrypoint)               │
│                                                                 │
│  1. Boot: ensure_schema() ──────────────► SQLite file (.db)   │
│     CREATE TABLE IF NOT EXISTS prospect, email_events,        │
│     free_email_domains; CREATE VIEW contacted_registry        │
│                                                                 │
│  2. check_apollo_health() ──► GET  /api/v1/auth/health   ┐    │
│     check_apollo_credits() ─► POST /api/v1/usage_stats/  │    │
│                                api_usage_stats            ▼    │
│                                                     Apollo.io   │
│                                                     (external)  │
│                                                                 │
│  3. check_mailbox_health(domain) ──► DNS TXT queries:          │
│     • {domain} TXT               (SPF: v=spf1 ...)             │
│     • _dmarc.{domain} TXT        (DMARC: v=DMARC1 ...)         │
│     • {selector}._domainkey.{domain} TXT  (DKIM, brute-force   │
│       common selectors: google, selector1, selector2, ...)     │
│                                          ▼                      │
│                                     Public DNS (external)       │
│                                                                 │
│  4. Render landing page: st.navigation gate                    │
│     - Apollo FAIL  → st.stop() after banner (D-01, hard block) │
│     - Apollo OK, Mailbox FAIL → render page, flag campaign     │
│       send/enroll actions disabled downstream (D-02, soft)     │
│     - Credit balance → st.metric, informational only (D-03)    │
└─────────────────────────────────────────────────────────────┘
```

A reader can trace the primary flow: browser loads app → app ensures schema exists → app calls Apollo twice (health, credits) → app queries DNS three ways → app renders one `st.status` block per check → gating logic decides whether `st.stop()` fires.

### Recommended Project Structure

```
outreach-agent/
├── app.py                      # Entrypoint; calls st.navigation, renders health page first
├── requirements.txt            # streamlit, requests, dnspython (pinned)
├── .streamlit/
│   ├── config.toml             # optional Streamlit config (theme, server settings)
│   └── secrets.toml            # gitignored — APOLLO_API_KEY, SENDING_DOMAIN
├── .gitignore                  # must include .streamlit/secrets.toml, *.db
├── db/
│   ├── __init__.py
│   ├── schema.py                # ensure_schema(): CREATE TABLE IF NOT EXISTS ... (idempotent)
│   └── outreach.db              # gitignored SQLite file, created at first boot
├── apollo/
│   ├── __init__.py
│   └── client.py                # ApolloClient: health(), usage_stats(), error-code handling
├── mailbox/
│   ├── __init__.py
│   └── dns_checks.py             # check_spf(), check_dmarc(), check_dkim() (selector brute-force)
├── pages/                        # (or st.Page-based routing from app.py — see Pattern 1)
└── tests/
    ├── conftest.py
    ├── test_schema.py
    ├── test_apollo_client.py
    └── test_dns_checks.py
```

### Pattern 1: Gated Landing Page with `st.navigation`

**What:** Use `st.navigation`/`st.Page` to conditionally control which pages are reachable, keyed off the Apollo health check result. This is the mechanism later phases (Discovery, Personalization, etc.) will extend — Phase 1 only needs to prove the gate works, since no other pages exist yet.

**When to use:** Any time a boot-time precondition (D-01: valid Apollo key) must block *all* other functionality, not just show a warning.

**Example:**
```python
# Source: docs.streamlit.io/develop/api-reference/navigation/st.navigation (Streamlit 1.59)
import streamlit as st

apollo_ok = check_apollo_health()  # returns bool

pages = {"Health": [st.Page("health_page.py", title="System Health", default=True)]}
if apollo_ok:
    # Phase 2+ will add real pages here; Phase 1 has none yet beyond Health.
    pass

pg = st.navigation(pages)
pg.run()
```
Inside `health_page.py`, use `st.stop()` immediately after rendering the Apollo failure banner so the rest of that page's script (mailbox check, SQLite status, etc.) still renders — `st.stop()` halts the *current script run*, not navigation, so render the Apollo block first, decide there, and only call `st.stop()` if it hard-fails per D-01.

### Pattern 2: `st.status` Blocks Per Health Check

**What:** One `st.status(...)` container per check (Apollo auth, Apollo credits, SPF, DMARC, DKIM, SQLite schema), each updated to `state="complete"` or `state="error"` after the underlying call finishes.

**When to use:** Directly matches ROADMAP.md success criterion 1 ("pass/fail indicators").

**Example:**
```python
# Source: docs.streamlit.io/develop/api-reference/status/st.status (Streamlit 1.59)
import streamlit as st

with st.status("Apollo API connection", expanded=True) as status:
    ok, detail = check_apollo_health()
    if ok:
        status.update(label="Apollo API connection: OK", state="complete", expanded=False)
    else:
        st.error(
            "Apollo connection failed — check that APOLLO_API_KEY is set correctly "
            "in Streamlit secrets."
        )
        status.update(label="Apollo API connection: FAILED", state="error", expanded=True)
        st.stop()  # D-01: hard block, nothing below this renders
```

### Pattern 3: Idempotent Schema Bootstrap

**What:** Run `CREATE TABLE IF NOT EXISTS` / `CREATE VIEW IF NOT EXISTS` (SQLite does not support `CREATE VIEW IF NOT EXISTS` directly pre-3.something reliably — use `DROP VIEW IF EXISTS` + `CREATE VIEW` for views, since views are cheap to recreate) on every app boot, not just "first run." This satisfies success criterion 3 (no manual setup) and is safe to call on every restart.

**When to use:** Always, for a file-based SQLite app with no separate migration tool in v1.

**Example:** see Code Examples below.

### Anti-Patterns to Avoid

- **Checking Apollo credit balance via `auth/health`:** That endpoint only returns `is_logged_in`/`healthy` (and possibly a `user` object) — it has no credit fields (verified via docs.apollo.io fetch, MEDIUM confidence on exact shape). Calling it and grepping for a "credits" key will silently return nothing. Use `usage_stats/api_usage_stats` instead.
- **Treating DKIM absence as a hard SPF/DMARC-style pass/fail:** Because there is no reliable way to enumerate DKIM selectors via DNS (RFC 6376 — no wildcard, no registry), a "no selector found" result must be rendered as "Unknown / could not verify" rather than "FAIL," or teammates with correctly configured DKIM under an unlisted selector will see a false failure and be blocked incorrectly per D-02. This is why CONTEXT.md's manual-attestation fallback exists — use it when the brute-force list comes back empty, don't just report FAIL.
- **Building a separate Postgres/event-driven backend:** `.planning/research/ARCHITECTURE.md` (older, generic pass) recommends Next.js + Postgres + pg-boss. This is superseded by CLAUDE.md's locked Streamlit + SQLite stack — do not resurrect it for Phase 1 or any phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| DNS TXT record parsing/query retries | A raw `socket`-based DNS client | `dnspython`'s `dns.resolver.resolve(domain, "TXT")` | Handles UDP/TCP fallback, timeouts, NXDOMAIN vs. no-record vs. timeout distinctions correctly; hand-rolled sockets will misclassify "domain doesn't exist" vs. "no TXT record" |
| Apollo request retry/backoff | Custom retry loop | `requests` + a small `tenacity`-style manual backoff wrapper (or hand-written 3-try exponential backoff per CLAUDE.md's own spec — this one small piece is fine to hand-write since CLAUDE.md explicitly specifies the exact policy: 429 → backoff, max 3 retries) | CLAUDE.md already dictates the exact policy; a full retry library is unnecessary weight for 3 fixed retries on 2 endpoints, but don't reinvent Apollo's error-code semantics — follow the documented 401/403/422/429 table exactly |
| SPF/DMARC full-chain validation | Manual regex parsing of `include:` chains and 10-DNS-lookup limits | `checkdmarc` (if/when full chain validation is needed — not required for Phase 1's binary presence check) | SPF's `include:` mechanism and 10-lookup RFC limit are genuinely fiddly; Phase 1 only needs "record exists," so this is deferred, not built |

**Key insight:** Phase 1's checks are intentionally shallow (presence/absence, not deep protocol compliance) per the walking-skeleton mandate — resist the urge to build a full email-authentication validator when a pass/fail landing page is the actual requirement.

## Common Pitfalls

### Pitfall 1: Assuming `auth/health` Returns Credit Balance

**What goes wrong:** Code written to extract `response.json()["credits"]` (or similar) from the `auth/health` call returns `None`/`KeyError` because that field doesn't exist there.
**Why it happens:** The endpoint name ("health") and the phase requirement ("show credit balance") get conflated into one call in a first draft.
**How to avoid:** Two separate Apollo calls: `GET /api/v1/auth/health` (key validity, D-01 gate) and `POST /api/v1/usage_stats/api_usage_stats` (credit/usage info, D-03 informational). The exact JSON field name for remaining credits in the usage_stats response was not confirmed from public docs during this research pass (MEDIUM confidence) — the plan should include a live test call (with a real or sandbox key) early in Wave 0 to confirm the field name before building the `st.metric` display around it, and treat "field not found" as a display of "Credit balance unavailable" rather than a crash.
**Warning signs:** `KeyError`/`None` where a credit number is expected; the number shown looks like a boolean or a rate-limit count instead of a credit balance.

### Pitfall 2: DKIM Selector Brute-Force False Negatives

**What goes wrong:** The mailbox health check reports DKIM as "FAIL" for a domain that is, in fact, correctly configured with DKIM — just under a selector name not in the brute-force list (e.g., a rotated/custom selector).
**Why it happens:** DNS has no wildcard or enumeration mechanism for `_domainkey` records (confirmed via multiple sources — RFC 6376 constraint, not an implementation bug). A brute-force list of common selectors (`google`, `selector1`, `selector2`, `k1`, `s1`, `s2`, `default`, `dkim`, `mail`, `m1` for Mailgun) will always miss custom selectors.
**How to avoid:** Never render "DKIM: FAIL" from a brute-force miss. Render "DKIM: Unknown — could not auto-detect" and surface CONTEXT.md's manual self-attestation checkbox ("I've configured DKIM for this domain") as the actual pass condition when auto-detection is inconclusive. Since D-02 only soft-blocks (send/enroll), treating "Unknown" as non-blocking (same as attested-pass) is a reasonable default — teammates aren't locked out over a detection limitation.
**Warning signs:** A domain known to have working DKIM (verified manually via `dig TXT selector._domainkey.domain`) still shows FAIL in the app.

### Pitfall 3: SQLite View Recreation Breaking on Every Boot

**What goes wrong:** `CREATE VIEW contacted_registry AS ...` throws `sqlite3.OperationalError: view contacted_registry already exists` on the second and every subsequent app boot, because SQLite's `CREATE VIEW IF NOT EXISTS` support is inconsistent for views that reference other schema objects that may also be evolving.
**Why it happens:** Views (unlike tables) are frequently recreated wholesale rather than migrated incrementally in small apps; a naive `CREATE VIEW` without a guard fails on restart.
**How to avoid:** Always pair `DROP VIEW IF EXISTS contacted_registry;` immediately before `CREATE VIEW contacted_registry AS ...` in the schema bootstrap function, and run both inside the same idempotent `ensure_schema()` call executed at every boot (not just first run).
**Warning signs:** App works on `streamlit run app.py` first time, crashes with `OperationalError` on the second run/restart.

### Pitfall 4: Hardcoding the Free-Domain Exclusion List In Query Logic

**What goes wrong:** The gmail.com/outlook.com/yahoo.com/hotmail.com/icloud.com exclusion list from CONTEXT.md gets hardcoded as a Python list inline in Phase 2's dedup query, duplicated wherever dedup logic runs, and drifts out of sync when someone wants to add a domain later.
**Why it happens:** It's a short, stable-looking list, so hardcoding feels harmless in the moment.
**How to avoid:** Seed it as a `free_email_domains` table in Phase 1's schema bootstrap (5 rows, insert-or-ignore) so the `contacted_registry` view (and any future admin UI to edit the list) reads from one place. This is a Phase 1 schema decision even though the list isn't *used* until Phase 2/4 — get the shape right now since DEDUP-01 is explicitly this phase's requirement.
**Warning signs:** Two different files contain the same five-domain literal list.

## Code Examples

### Idempotent Schema Bootstrap (`db/schema.py`)

```python
# Design recommendation based on spec.MD §5 + DEDUP-01 requirement (not sourced from
# an external reference — this is this-session's schema design synthesis)
import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS prospect (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    company             TEXT,
    company_domain      TEXT,               -- lowercased registrable domain, e.g. "acme.com"
    apollo_person_id    TEXT,                -- id from mixed_people/api_search (pre-enrichment)
    apollo_contact_id   TEXT,                -- id from /contacts, set only once converted
    email               TEXT,
    path                TEXT,                -- 'club_sponsorship' | 'productthon' | 'client_sourcing'
    status              TEXT NOT NULL DEFAULT 'found'
                        CHECK (status IN (
                            'found','selected','enriched',
                            'contact_created','drafted','approved','sequenced'
                        )),
    sequence_id         TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id         INTEGER NOT NULL REFERENCES prospect(id),
    apollo_contact_id   TEXT,
    event_type          TEXT NOT NULL,       -- 'sent' | 'opened' | 'replied' | 'bounced' | 'unsubscribed'
    occurred_at         TIMESTAMP,
    raw_payload         TEXT,                -- JSON blob; Apollo stats schema is under-documented (MEDIUM
                                              -- confidence) — store raw response for forward-compat
    polled_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS free_email_domains (
    domain TEXT PRIMARY KEY
);
INSERT OR IGNORE INTO free_email_domains (domain) VALUES
    ('gmail.com'), ('outlook.com'), ('yahoo.com'), ('hotmail.com'), ('icloud.com');
"""

# Views must be dropped and recreated explicitly — see Pitfall 3
VIEW_DDL = """
DROP VIEW IF EXISTS contacted_registry;
CREATE VIEW contacted_registry AS
SELECT
    p.id,
    p.apollo_person_id,
    p.apollo_contact_id,
    p.company_domain,
    CASE
        WHEN p.company_domain IS NULL THEN NULL
        WHEN p.company_domain IN (SELECT domain FROM free_email_domains) THEN NULL
        ELSE p.company_domain
    END AS dedupable_domain,   -- NULL means "don't use for domain-level dedup"
    p.status
FROM prospect p
WHERE p.apollo_contact_id IS NOT NULL;   -- only rows that reached "contact_created" or later
"""

def ensure_schema(db_path: str = "db/outreach.db") -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        conn.executescript(VIEW_DDL)
        conn.commit()
    finally:
        conn.close()
```

Phase 2 dedup query (DEDUP-02, for reference only — not built in Phase 1):
```python
# id-level dedup applies to everyone; domain-level dedup only for dedupable_domain
cur.execute("SELECT apollo_person_id FROM contacted_registry WHERE apollo_person_id = ?", (candidate_id,))
cur.execute("SELECT 1 FROM contacted_registry WHERE dedupable_domain = ?", (candidate_domain,))
```

### Apollo Health + Credit Check (`apollo/client.py`)

```python
# Source: apollo.MD, spec.MD §2/§6, CLAUDE.md error-handling table (all first-party project docs)
import requests

APOLLO_BASE = "https://api.apollo.io/api/v1"

def check_apollo_health(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            f"{APOLLO_BASE}/auth/health",
            headers={"x-api-key": api_key},
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"Apollo connection failed — network error: {e}"

    if resp.status_code == 401:
        return False, "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."
    if resp.status_code == 403:
        return False, "Apollo connection failed — this key is not a Master API key. Check Apollo Settings → Integrations → API Keys."
    if resp.status_code != 200:
        return False, f"Apollo connection failed — unexpected status {resp.status_code}."

    data = resp.json()
    if not data.get("is_logged_in", False):
        return False, "Apollo connection failed — key present but not recognized as logged in."
    return True, "Apollo connection OK"


def get_credit_balance(api_key: str) -> tuple[int | None, str]:
    """Returns (credits_remaining_or_None, status_message). Never blocks (D-03)."""
    try:
        resp = requests.post(
            f"{APOLLO_BASE}/usage_stats/api_usage_stats",
            headers={"x-api-key": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return None, "Credit balance unavailable (network error)"

    if resp.status_code != 200:
        return None, "Credit balance unavailable"

    data = resp.json()
    # NOTE (MEDIUM confidence): exact field name for remaining credits was not confirmed
    # against a live authenticated response during research. Verify in Wave 0 and adjust
    # this key lookup — candidates to check first: data.get("credits"), data.get("credit_balance"),
    # or a nested structure under a "usage" / "rate_limits" key.
    credits = data.get("credits") or data.get("credit_balance")
    if credits is None:
        return None, "Credit balance unavailable (unexpected response shape — see Wave 0 verification note)"
    return credits, "OK"
```

### DNS Mailbox Checks (`mailbox/dns_checks.py`)

```python
# Source: dnspython docs (dns.resolver) + RFC 6376 DKIM selector constraint (no enumeration)
import dns.resolver
import dns.exception

COMMON_DKIM_SELECTORS = [
    "google", "selector1", "selector2",  # Google Workspace, Microsoft 365
    "k1", "s1", "s2", "default", "dkim", "mail", "m1",  # SendGrid/generic/Mailgun-style
]

def _txt_records(name: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT")
        return ["".join(r.strings[i].decode() for i in range(len(r.strings))) if hasattr(r, "strings") else str(r) for r in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
        return []

def check_spf(domain: str) -> tuple[bool, str]:
    records = _txt_records(domain)
    for r in records:
        if r.startswith("v=spf1"):
            return True, f"SPF record found: {r}"
    return False, "No SPF record found (expected v=spf1 ... TXT record on the root domain)"

def check_dmarc(domain: str) -> tuple[bool, str]:
    records = _txt_records(f"_dmarc.{domain}")
    for r in records:
        if r.startswith("v=DMARC1"):
            return True, f"DMARC record found: {r}"
    return False, "No DMARC record found (expected v=DMARC1 ... TXT record at _dmarc.<domain>)"

def check_dkim(domain: str) -> tuple[str, str]:
    """Returns ('pass' | 'unknown', message). Never returns a hard 'fail' — see Pitfall 2."""
    for selector in COMMON_DKIM_SELECTORS:
        records = _txt_records(f"{selector}._domainkey.{domain}")
        for r in records:
            if "p=" in r:  # DKIM TXT records contain a public key field
                return "pass", f"DKIM record found under selector '{selector}'"
    return "unknown", (
        "Could not auto-detect a DKIM record under common selectors "
        f"({', '.join(COMMON_DKIM_SELECTORS)}). This does not necessarily mean DKIM is "
        "misconfigured — some providers use custom selectors. Please confirm manually."
    )
```

### Secrets Access Pattern

```python
# Source: docs.streamlit.io/develop/concepts/connections/secrets-management
import streamlit as st

apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")

if not apollo_key:
    st.error("APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
              "Community Cloud secrets console (production).")
    st.stop()
```

`.streamlit/secrets.toml` (local dev, gitignored):
```toml
APOLLO_API_KEY = "your-master-api-key"
SENDING_DOMAIN = "outreach.yourclub.org"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Streamlit `pages/` directory convention for multipage apps | `st.navigation()` + `st.Page()` programmatic routing | Introduced Streamlit 1.36 (2024), now the documented default pattern as of 1.59 | Enables the exact conditional-page-gating behavior D-01 needs (hide/show pages based on a runtime health check) — the older `pages/` folder convention cannot conditionally hide pages at runtime |

**Deprecated/outdated:** None specific to this phase's scope beyond the navigation pattern above.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `usage_stats/api_usage_stats` response contains a credit-balance field, but the exact JSON key name was not confirmed via an authenticated live call or Context7 during this research pass (MEDIUM confidence per WebFetch of docs.apollo.io) | Common Pitfalls #1, Code Examples (Apollo client) | If the field name differs from what's coded, `get_credit_balance()` returns "unavailable" gracefully (already designed for this) rather than crashing — low risk, but the plan should budget a Wave 0 live-call verification step |
| A2 | Apollo's `mixed_people/api_search` response includes an organization primary-domain field usable to populate `prospect.company_domain` | Standard Stack / schema design (affects Phase 2, not Phase 1 build, but Phase 1 defines the column) | If no domain field exists on search results, `company_domain` would need to be derived from the enriched email's domain instead (available post-enrichment, i.e., later in the pipeline than search) — schema itself doesn't change, only when the column gets populated. Phase 2 research should re-verify this against a live Apollo response. |
| A3 | `checkdmarc` package name/existence — discovered via WebSearch, not Context7 or official docs, though `slopcheck` confirms it exists on PyPI | Standard Stack (Supporting), Don't Hand-Roll | Low risk — package is explicitly marked deferred/optional and not part of the Phase 1 install list |
| A4 | Streamlit's `st.stop()` halts only the current script run and does not prevent `st.navigation` from re-evaluating on the next rerun/interaction (used to justify the D-01 gating pattern) | Architecture Patterns, Pattern 1/2 | If `st.stop()` behaves differently than assumed, the gate might not re-check on every interaction — mitigate by re-running the Apollo check at the top of every script execution (Streamlit's normal execution model reruns the whole script on each interaction anyway, which is the standard framework behavior, so this is low risk) |

## Open Questions (RESOLVED)

1. **Exact `usage_stats/api_usage_stats` response schema (credit balance field name)** — RESOLVED: addressed via defensive coding, not a live-call confirmation. Not a blocker.
   - What we know: Endpoint exists, requires master key, POST method, documented as showing "credits used within the current billing cycle" per Apollo's knowledge base article "What Are Credits?"
   - What's unclear: The literal JSON key(s) for remaining/used credits
   - Resolution: Plan 01-03 codes `get_credit_balance()` defensively (per the example in this doc) so a missing/renamed field never crashes the health page — D-03 makes this informational-only by design. Plan 01-04 Task 3 (human-verify checkpoint) captures the raw JSON from a real authenticated call and confirms/adjusts the field name during execution, per the Wave-0-verify comment left in 01-03.

2. **Whether Apollo's People Search response includes an organization-level `primary_domain` (or similarly named) field** — RESOLVED: deferred to Phase 2, correct phase boundary.
   - What we know: Apollo's org data model generally includes a primary domain concept (used elsewhere, e.g., organization search)
   - What's unclear: Whether the *people* search response (not organization search) surfaces it directly, or whether it must be derived from the enriched contact's email domain after Phase 2's enrichment step
   - Resolution: Out of scope for Phase 1. The `company_domain` column exists in the schema (Plan 01-02) and accepts a value whenever it becomes available in the pipeline; Phase 2 research will re-verify against a live Apollo response before Phase 2 planning.

3. **Whether DNS is reachable from the eventual Streamlit Community Cloud hosting environment for the DKIM/SPF/DMARC checks** — RESOLVED: moot for Phase 1, since Community Cloud deployment is out of scope this phase (local dev only).
   - What we know: DNS resolution worked from this local dev machine during research (confirmed live)
   - What's unclear: Whether Streamlit Community Cloud's egress allows arbitrary DNS TXT queries (as opposed to just HTTPS to known API hosts) — most cloud hosts allow this, but not verified for Community Cloud specifically
   - Resolution: Flagged as a smoke-test item for whichever future phase first deploys to Community Cloud; does not block Phase 1 execution, which runs locally.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.12 (CLAUDE.md-pinned) | Entire app runtime | ✗ (only 3.13.2 found on PATH; no `python3.12` binary present) | — | Use available Python 3.13.2 via an explicit venv (Streamlit 1.59 and all Phase 1 deps support 3.13); document the version drift from CLAUDE.md and pin explicitly in `requirements.txt`/`.python-version` rather than silently relying on whatever `python3` resolves to. Not a hard blocker. |
| Network access to `api.apollo.io` | Apollo health/credit checks | ✓ | — (HTTP 200 confirmed on `auth/health` from this machine) | — |
| Public DNS resolution (TXT queries) | SPF/DMARC/DKIM checks | ✓ | — (TXT query against gmail.com succeeded from this machine) | — |
| `dnspython` | DNS checks | ✓ (already installed in local dev env) | 2.8.0 | — |
| `pytest` | Test suite (Wave 0 setup) | ✓ (system-wide) | 9.0.2 | Add explicit `pytest` pin to `requirements-dev.txt` rather than relying on the system install |
| SQLite (stdlib) | Schema/persistence | ✓ | 3.45.3 (bundled with local Python 3.13.2) | — |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:**
- Python 3.12 pinned binary — use 3.13.2 via venv, document drift (see above)

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (system-installed; not yet a project dependency — add to `requirements-dev.txt` in Wave 0) |
| Config file | none — see Wave 0 Gaps |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| DEDUP-01 | `ensure_schema()` creates `prospect`, `email_events`, `free_email_domains` tables and `contacted_registry` view idempotently (runs twice without error) | unit | `pytest tests/test_schema.py::test_ensure_schema_idempotent -x` | ❌ Wave 0 |
| DEDUP-01 | `contacted_registry` view correctly nulls out `dedupable_domain` for seeded free-email domains and passes through company domains | unit | `pytest tests/test_schema.py::test_registry_excludes_free_domains -x` | ❌ Wave 0 |
| (ROADMAP success criterion 1) | `check_apollo_health()` returns `(False, ...)` on 401/403 and `(True, ...)` on 200 with `is_logged_in: true` | unit (mocked `requests`) | `pytest tests/test_apollo_client.py::test_check_apollo_health -x` | ❌ Wave 0 |
| (ROADMAP success criterion 1) | `check_spf`/`check_dmarc`/`check_dkim` correctly classify a domain with known-good records (mocked DNS responses) vs. no records | unit (mocked `dns.resolver`) | `pytest tests/test_dns_checks.py::test_check_spf_dmarc_dkim -x` | ❌ Wave 0 |
| (ROADMAP success criterion 4) | Prospect rows written before an app "restart" (fresh `sqlite3.connect()` to the same file) are still queryable afterward | integration | `pytest tests/test_schema.py::test_persistence_across_reconnect -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `requirements-dev.txt` — add `pytest` (currently only system-available, not project-pinned)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — set `testpaths = ["tests"]`
- [ ] `tests/conftest.py` — shared fixtures: temp SQLite DB path per test, `requests`/`dns.resolver` mocking helpers
- [ ] `tests/test_schema.py`, `tests/test_apollo_client.py`, `tests/test_dns_checks.py` — all net-new, no existing test infra in this greenfield repo

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V2 Authentication | Partial — this is Apollo's own key-based auth, not app-level user auth (no login system in v1 per CLAUDE.md "Auth layer" table) | Master API key treated as a bearer secret; validated via `auth/health`, never logged |
| V3 Session Management | No | N/A — Streamlit Community Cloud access is restricted at the platform/GitHub-account level, not app-level sessions (per CLAUDE.md) |
| V4 Access Control | No | N/A — single-tenant internal tool, no per-user roles in v1 |
| V5 Input Validation | Yes | `SENDING_DOMAIN` from secrets should be validated as a plausible domain string before being interpolated into DNS query names (prevents malformed queries, not a security boundary per se since it's admin-supplied config, not end-user input) |
| V6 Cryptography | No hand-rolled crypto | N/A — no cryptographic operations in this phase; DKIM checks only *read* existing public DNS TXT records, never generate or validate signatures |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| Apollo master API key leakage (logged, committed to git, or exposed client-side) | Information Disclosure | `st.secrets` only, `.streamlit/secrets.toml` in `.gitignore`, key read server-side (Streamlit's entire execution model is server-side — there is no client-side code path where this could leak, unlike a React/Next.js app) |
| Stack traces shown to non-technical users on Apollo failures leaking internal details | Information Disclosure | CLAUDE.md/CONTEXT.md already mandate banner-with-next-step instead of raw exceptions; wrap all Apollo/DNS calls in try/except that render `st.error(...)` and never let an unhandled exception surface Streamlit's default traceback view |
| SQL injection via string-built queries against the SQLite `prospect` table | Tampering | Use parameterized queries (`?` placeholders) exclusively — stdlib `sqlite3` supports this natively; never f-string user/Apollo-derived values into SQL (relevant even though Phase 1 doesn't write dynamic prospect data yet — establish the pattern now since Phase 2 will) |

## Sources

### Primary (HIGH confidence)
- CLAUDE.md, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/PROJECT.md` — project-level locked decisions
- `apollo.MD`, `spec.MD` — first-hand Apollo API exploration (project root)
- `.planning/phases/01-foundation/01-CONTEXT.md` — locked Phase 1 decisions (D-01 through D-04) and discretion guidance
- `.planning/research/STACK.md`, `.planning/research/PITFALLS.md` — prior project-level research (2026-07-19), superseding `.planning/research/ARCHITECTURE.md`'s Next.js recommendation
- Local tool verification: `pip3 index versions <pkg>` (PyPI, 2026-07-20), `slopcheck` scan (4/4 packages OK), live `curl` to `api.apollo.io/api/v1/auth/health` (200), live DNS TXT query against gmail.com (succeeded), local `python3 --version`/`sqlite3.sqlite_version` checks

### Secondary (MEDIUM confidence)
- https://docs.apollo.io/docs/test-api-key — `auth/health` response shape (fetched via WebFetch, response body not exhaustively documented on the page)
- https://docs.apollo.io/reference/view-api-usage-stats — `usage_stats/api_usage_stats` endpoint existence, method, master-key requirement (exact response JSON not available in fetched content)
- https://docs.streamlit.io/develop/api-reference/navigation/st.navigation, https://docs.streamlit.io/develop/api-reference/status/st.status, https://docs.streamlit.io/develop/api-reference/data/st.metric, https://docs.streamlit.io/develop/concepts/connections/secrets-management — all fetched live 2026-07-20
- https://powerdmarc.com/how-to-find-dkim-selector/ (WebSearch summary; direct fetch blocked by 403) — common DKIM selector list

### Tertiary (LOW confidence)
- https://pypi.org/project/checkdmarc/ — package capability summary (fetched, but not cross-verified against Context7 or an official maintainer doc)
- General DKIM-selector-discovery-is-unreliable claim — corroborated by multiple independent WebSearch sources (CaptainDNS, ZeroHook, PowerDMARC) citing RFC 6376's lack of enumeration mechanism; treated as MEDIUM given cross-source agreement despite no single authoritative fetch

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all four packages version-verified live against PyPI and slopcheck-clean; matches CLAUDE.md's already-locked choices
- Architecture: HIGH — Streamlit `st.navigation`/`st.status`/`st.metric` patterns fetched from current official docs; SQLite schema is a direct, low-risk extension of spec.MD §5
- Pitfalls: MEDIUM — DKIM selector unreliability is well-corroborated (multiple independent sources) but not from a single authoritative spec; Apollo credit-balance field name is genuinely unconfirmed pending a live authenticated test call

**Research date:** 2026-07-20
**Valid until:** 30 days for Streamlit/library version pins (fast-moving PyPI ecosystem); Apollo endpoint behavior and DKIM/DNS fundamentals are stable and effectively valid indefinitely absent an Apollo API change
