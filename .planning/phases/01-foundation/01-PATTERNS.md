# Phase 1: Foundation - Pattern Map

**Mapped:** 2026-07-20
**Files analyzed:** 15
**Analogs found:** 0 / 15 (confirmed greenfield repo — see Metadata)

## Greenfield Notice

This repository contains **no application code**. `git status`/directory listing confirms the working tree holds only `CLAUDE.md`, `apollo.MD`, `spec.MD`, and `.planning/`. There are zero prior phases, zero existing modules, and no `.claude/skills` or `.agents/skills` directories to load. Every file below is `no analog — greenfield`.

In place of in-repo analogs, this document points each file at the concrete reference snippet in `01-RESEARCH.md` that the planner/executor should treat as the starting pattern — these are sourced from official docs (Streamlit, dnspython, Apollo project docs) and CLAUDE.md's locked stack decisions, not fabricated. Line numbers below refer to `.planning/phases/01-foundation/01-RESEARCH.md`.

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|---------------|
| `app.py` | controller (entrypoint / page router) | request-response | none | no analog — greenfield |
| `db/__init__.py` | config (package marker) | — | none | no analog — greenfield |
| `db/schema.py` | model / migration (schema bootstrap) | CRUD (DDL, idempotent) | none | no analog — greenfield |
| `apollo/__init__.py` | config (package marker) | — | none | no analog — greenfield |
| `apollo/client.py` | service (external API client) | request-response | none | no analog — greenfield |
| `mailbox/__init__.py` | config (package marker) | — | none | no analog — greenfield |
| `mailbox/dns_checks.py` | service / utility (external DNS client) | request-response | none | no analog — greenfield |
| `pages/health_page.py` (or equivalent `st.Page` target) | component (Streamlit page) | request-response | none | no analog — greenfield |
| `.streamlit/config.toml` | config | — | none | no analog — greenfield |
| `.streamlit/secrets.toml` | config (gitignored, not authored by executor — template only) | — | none | no analog — greenfield |
| `requirements.txt` | config | — | none | no analog — greenfield |
| `requirements-dev.txt` | config | — | none | no analog — greenfield |
| `tests/conftest.py` | test (fixtures) | — | none | no analog — greenfield |
| `tests/test_schema.py` | test | CRUD | none | no analog — greenfield |
| `tests/test_apollo_client.py` | test | request-response | none | no analog — greenfield |
| `tests/test_dns_checks.py` | test | request-response | none | no analog — greenfield |

## Pattern Assignments

### `app.py` (controller, request-response)

**Analog:** none — greenfield. Reference pattern: `01-RESEARCH.md` Pattern 1 (lines 187-202) and Pattern 2 (lines 210-226).

**Core pattern — gated navigation** (RESEARCH.md lines 188-201):
```python
import streamlit as st

apollo_ok = check_apollo_health()  # returns bool

pages = {"Health": [st.Page("health_page.py", title="System Health", default=True)]}
if apollo_ok:
    # Phase 2+ will add real pages here; Phase 1 has none yet beyond Health.
    pass

pg = st.navigation(pages)
pg.run()
```

**Secrets access pattern** (RESEARCH.md lines 471-481):
```python
import streamlit as st

apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")

if not apollo_key:
    st.error("APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
              "Community Cloud secrets console (production).")
    st.stop()
```

**Gating rule to encode (D-01/D-02):** Apollo health failure → `st.stop()` after the banner (hard block, nothing else renders). Mailbox failure → render the rest of the page normally, but flag that send/enroll actions are disabled downstream (no `st.stop()`).

---

### `db/schema.py` (model/migration, CRUD)

**Analog:** none — greenfield. Reference pattern: `01-RESEARCH.md` Pattern 3 (lines 228-234) and full DDL in Code Examples (lines 286-356).

**Core pattern — idempotent bootstrap with parameterized DDL and view drop/recreate** (RESEARCH.md lines 291-356):
```python
import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS prospect (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    company             TEXT,
    company_domain      TEXT,
    apollo_person_id    TEXT,
    apollo_contact_id   TEXT,
    email               TEXT,
    path                TEXT,
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
    event_type          TEXT NOT NULL,
    occurred_at         TIMESTAMP,
    raw_payload         TEXT,
    polled_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS free_email_domains (
    domain TEXT PRIMARY KEY
);
INSERT OR IGNORE INTO free_email_domains (domain) VALUES
    ('gmail.com'), ('outlook.com'), ('yahoo.com'), ('hotmail.com'), ('icloud.com');
"""

VIEW_DDL = """
DROP VIEW IF EXISTS contacted_registry;
CREATE VIEW contacted_registry AS
SELECT
    p.id, p.apollo_person_id, p.apollo_contact_id, p.company_domain,
    CASE
        WHEN p.company_domain IS NULL THEN NULL
        WHEN p.company_domain IN (SELECT domain FROM free_email_domains) THEN NULL
        ELSE p.company_domain
    END AS dedupable_domain,
    p.status
FROM prospect p
WHERE p.apollo_contact_id IS NOT NULL;
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

**Pitfall to avoid (Pitfall 3, RESEARCH.md lines 268-274):** `CREATE VIEW` has no reliable `IF NOT EXISTS` guard for views depending on evolving schema — always pair `DROP VIEW IF EXISTS` immediately before `CREATE VIEW`, run inside the same `ensure_schema()` call executed at every boot, not just first run.

**Pitfall to avoid (Pitfall 4, RESEARCH.md lines 275-280):** Do not hardcode the free-email-domain exclusion list anywhere else (e.g., inline in a future dedup query). It lives only in the `free_email_domains` table seeded here.

**Query parameterization rule (Security Domain, RESEARCH.md line 591):** All future queries against `prospect` must use `?` placeholders — never f-string interpolate values into SQL, even though Phase 1 itself only writes the schema, not prospect rows.

---

### `apollo/client.py` (service, request-response)

**Analog:** none — greenfield. Reference pattern: `01-RESEARCH.md` Code Examples (lines 367-419).

**Core pattern — two separate calls, defensive field lookup** (RESEARCH.md lines 373-419):
```python
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
    credits = data.get("credits") or data.get("credit_balance")
    if credits is None:
        return None, "Credit balance unavailable (unexpected response shape — see Wave 0 verification note)"
    return credits, "OK"
```

**Error-handling rule to encode (CLAUDE.md, project-wide table):** 401/403 → banner, never retry. 422 → surface `response.json()["message"]` directly, don't swallow. 429 → exponential backoff, max 3 retries (not shown above — `auth/health`/`usage_stats` don't hit rate limits in normal boot flow, but any future bulk Apollo call in later phases must implement this).

**Open item to carry into planning (RESEARCH.md Assumptions A1, Open Questions #1, lines 501, 508-511):** The exact JSON key for remaining credits in `usage_stats/api_usage_stats` is unconfirmed (MEDIUM confidence). Plan should include a Wave 0 task to make one live authenticated call and confirm/adjust the `data.get("credits") or data.get("credit_balance")` lookup before building the `st.metric` display around it.

---

### `mailbox/dns_checks.py` (service/utility, request-response)

**Analog:** none — greenfield. Reference pattern: `01-RESEARCH.md` Code Examples (lines 424-466).

**Core pattern — TXT lookup + SPF/DMARC pass-fail + DKIM brute-force with soft "unknown" state** (RESEARCH.md lines 425-466):
```python
import dns.resolver
import dns.exception

COMMON_DKIM_SELECTORS = [
    "google", "selector1", "selector2",
    "k1", "s1", "s2", "default", "dkim", "mail", "m1",
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
            if "p=" in r:
                return "pass", f"DKIM record found under selector '{selector}'"
    return "unknown", (
        "Could not auto-detect a DKIM record under common selectors "
        f"({', '.join(COMMON_DKIM_SELECTORS)}). This does not necessarily mean DKIM is "
        "misconfigured — some providers use custom selectors. Please confirm manually."
    )
```

**Pitfall to avoid (Pitfall 2, RESEARCH.md lines 261-266):** Never render "DKIM: FAIL" from a brute-force miss — render "Unknown / could not auto-detect" and surface a manual self-attestation checkbox as the actual pass condition (CONTEXT.md discretion). Since D-02 only soft-blocks, treat "unknown" as non-blocking, same as attested-pass.

**Don't hand-roll (RESEARCH.md line 246):** Use `dns.resolver.resolve(domain, "TXT")`, not raw sockets — dnspython correctly distinguishes NXDOMAIN vs. no-record vs. timeout.

---

### `pages/health_page.py` (component, request-response)

**Analog:** none — greenfield. Reference pattern: `01-RESEARCH.md` Pattern 2 (lines 210-226).

**Core pattern — one `st.status` block per check, hard-stop only on Apollo failure** (RESEARCH.md lines 213-226):
```python
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

Repeat the same `st.status` shape for: Apollo credit balance (`st.metric`, informational only per D-03, never `st.stop()`), SPF, DMARC, DKIM (soft-block only downstream at send/enroll per D-02, page itself still renders), and SQLite schema bootstrap status.

---

### `tests/test_schema.py`, `tests/test_apollo_client.py`, `tests/test_dns_checks.py`, `tests/conftest.py` (test)

**Analog:** none — greenfield. Reference: `01-RESEARCH.md` Validation Architecture section (lines 539-571) and Wave 0 Gaps checklist (lines 566-571).

**Test framework:** pytest (system-installed 9.0.2; must be added to `requirements-dev.txt` — not yet a pinned project dependency).

**Test-to-requirement map** (RESEARCH.md lines 550-558):
- `test_schema.py::test_ensure_schema_idempotent` — `ensure_schema()` runs twice without error (DEDUP-01)
- `test_schema.py::test_registry_excludes_free_domains` — `contacted_registry` view nulls `dedupable_domain` for seeded free-email domains (DEDUP-01)
- `test_schema.py::test_persistence_across_reconnect` — rows written before a fresh `sqlite3.connect()` to the same file are still queryable
- `test_apollo_client.py::test_check_apollo_health` — mocked `requests`, asserts `(False, ...)` on 401/403 and `(True, ...)` on 200 + `is_logged_in: true`
- `test_dns_checks.py::test_check_spf_dmarc_dkim` — mocked `dns.resolver`, asserts correct classification for known-good vs. absent records

**conftest.py should provide:** a temp SQLite DB path fixture per test, and `requests`/`dns.resolver` mocking helpers (no existing test infra to copy from — build fresh per this pattern).

---

## Shared Patterns

### Secrets access
**Source:** RESEARCH.md lines 471-481 (Streamlit official docs pattern)
**Apply to:** `app.py`, `apollo/client.py` (via caller), `mailbox/dns_checks.py` (via caller)
```python
apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")
if not apollo_key:
    st.error("APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
              "Community Cloud secrets console (production).")
    st.stop()
```
Never hardcode keys. `.streamlit/secrets.toml` must be gitignored locally; production uses the Community Cloud secrets console.

### Error banner design (non-technical audience)
**Source:** CONTEXT.md discretion decision + RESEARCH.md lines 383-393
**Apply to:** `apollo/client.py`, `app.py`/`health_page.py` rendering layer
Banner text always includes a concrete next step, e.g. `"Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."` — never a bare status word, never a raw stack trace (Security Domain, RESEARCH.md line 590: wrap all Apollo/DNS calls in try/except, render `st.error(...)`, never let an unhandled exception surface Streamlit's default traceback view).

### Gating semantics (D-01 hard block vs D-02 soft block vs D-03 informational)
**Source:** CONTEXT.md D-01/D-02/D-03; RESEARCH.md Pattern 1/2 (lines 181-226)
**Apply to:** `app.py`, `pages/health_page.py`
- Apollo `auth/health` fail → render banner, then `st.stop()` (hard block, D-01)
- Mailbox SPF/DMARC/DKIM fail → render status, do NOT `st.stop()`; only disable send/enroll actions downstream (D-02) — no such actions exist yet in Phase 1, so this is a flag to carry into Phase 2's plan, not something Phase 1 renders disabled UI for
- Apollo credit balance low/zero → `st.metric`/informational text only, never blocks (D-03)

### Idempotent SQLite bootstrap
**Source:** RESEARCH.md lines 228-356 (Pattern 3 + Code Examples), Pitfall 3 (lines 268-274)
**Apply to:** `db/schema.py`, any future migration additions
`CREATE TABLE IF NOT EXISTS` for tables; `DROP VIEW IF EXISTS` + `CREATE VIEW` (no `IF NOT EXISTS` for views) — run both in the same `ensure_schema()` call, executed at every boot.

### Parameterized SQL only
**Source:** RESEARCH.md line 591 (Security Domain — Tampering/SQL injection)
**Apply to:** Any file that queries `prospect`/`email_events` (Phase 1's `db/schema.py` establishes this even though it only runs DDL; Phase 2+ must follow it for all row-level queries)
Use `?` placeholders exclusively — never f-string user/Apollo-derived values into SQL.

## No Analog Found

All 15 files below have no in-repo analog — this is a confirmed greenfield repository (only `CLAUDE.md`, `apollo.MD`, `spec.MD`, `.planning/` exist, verified via directory listing at pattern-mapping time). Use the RESEARCH.md reference snippets cited under Pattern Assignments above instead of an in-repo analog.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app.py` | controller | request-response | No prior Streamlit entrypoint exists in this repo |
| `db/schema.py` | model/migration | CRUD | No prior SQLite schema/migration code exists |
| `apollo/client.py` | service | request-response | No prior external API client exists |
| `mailbox/dns_checks.py` | service/utility | request-response | No prior DNS client code exists |
| `pages/health_page.py` | component | request-response | No prior Streamlit page/component exists |
| `.streamlit/config.toml` / `secrets.toml` | config | — | No prior Streamlit config exists |
| `requirements.txt` / `requirements-dev.txt` | config | — | No prior dependency manifest exists |
| `tests/conftest.py`, `tests/test_*.py` | test | CRUD / request-response | No prior test infrastructure exists |

## Metadata

**Analog search scope:** Full repository root (`.`, excluding `.git` and `.planning`) — confirmed via `find . -maxdepth 2` that only `CLAUDE.md`, `apollo.MD`, `spec.MD` exist as non-planning files. No `src/`, `app/`, `lib/`, or equivalent directories present. No `.claude/skills` or `.agents/skills` directories present.
**Files scanned:** 3 (all root docs — no source files to scan)
**Pattern extraction date:** 2026-07-20
