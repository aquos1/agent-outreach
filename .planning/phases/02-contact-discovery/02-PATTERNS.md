# Phase 2: Contact Discovery - Pattern Map

**Mapped:** 2026-07-24
**Files analyzed:** 7 (2 extended, 5 new)
**Analogs found:** 7 / 7 (2 have no in-repo precedent for their *novel* sub-behavior — see "No Analog Found" — but every file has a strong structural analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|------------------|----------------|
| `apollo/client.py` (EXTEND: add `search_people()`, `bulk_match_people()`, retry helper) | service (external API client) | request-response (search); batch (bulk_match, ≤10/call) | `apollo/client.py` itself (`check_apollo_health`, `get_credit_balance`) | exact |
| `db/prospects.py` (NEW: dedup query + prospect insert) | model (data access layer) | CRUD | `db/schema.py` (DDL + `contacted_registry` view) + `tests/test_schema.py` (query style) | role-match |
| `pages/discovery_page.py` (NEW: two-stage Find/Enrich page) | component / route (Streamlit page) | request-response, event-driven (button-gated) | `pages/health_page.py` | exact |
| `app.py` (EXTEND: register discovery page in `pages` dict) | config / route registration | request-response | `app.py` itself (existing `pages` dict + comment placeholder) | exact |
| `tests/test_apollo_client.py` (EXTEND: RED tests for new client functions) | test | request-response | `tests/test_apollo_client.py` itself + `tests/conftest.py` (`mock_requests_response`) | exact |
| `tests/test_prospects.py` (NEW: dedup + insert tests) | test | CRUD | `tests/test_schema.py` | exact |
| `tests/test_discovery_logic.py` (NEW: pure-function tests — filter translation, has_email prefilter, cost estimate) | test | transform (pure functions, no I/O) | `tests/test_dns_checks.py` | role-match |

## Pattern Assignments

### `apollo/client.py` (EXTEND) — service, request-response/batch

**Analog:** `apollo/client.py` itself (`check_apollo_health`, `get_credit_balance`) — this is a direct in-file extension, not a cross-file port. Copy the exact shape of the two existing functions for the two new ones.

**Module header / imports** (lines 1-17):
```python
"""Apollo.io connectivity client: key-validity gate and informational credit balance.
...
NEVER log or print the api_key (T-03-01).
"""
from __future__ import annotations

import requests

APOLLO_BASE = "https://api.apollo.io/api/v1"
```
Update the module docstring to describe the new search/enrichment functions when extending; keep `APOLLO_BASE` as the single base-URL constant (do not redefine it in a new file).

**Typed-tuple, never-raise, status-code-branching core pattern** (lines 20-44, `check_apollo_health`):
```python
def check_apollo_health(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            f"{APOLLO_BASE}/auth/health",
            headers={"x-api-key": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return False, "Apollo connection failed — check your internet connection and try again."

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
```
`search_people()` must copy this exact shape: `try/except requests.RequestException`, then explicit `if resp.status_code == N` branches in the order 401 → 403 → 429 (new, per D-06/Pitfall 2) → generic `!= 200`, then a defensive `.get()` parse of the success body. Header is always `{"x-api-key": api_key}` — never a Bearer token.

**Defensive `.get()` parsing for uncertain response shape** (lines 47-77, `get_credit_balance`):
```python
data = resp.json()
credits = data.get("credits") or data.get("credit_balance")
if credits is None:
    return None, "Credit balance unavailable (unexpected response shape)"
return credits, "OK"
```
Reuse this exact style for `search_people()`'s `people` array parse and `bulk_match_people()`'s `matches` array parse — every field lookup must be `.get(...)`, never `data["field"]`, because RESEARCH.md's Assumptions A1/A2 flag the exact Apollo field names as MEDIUM confidence (pending the Wave 0 human-verify checkpoint). A field-name mismatch must degrade to an empty list / "unavailable" message, never a `KeyError` traceback — this is the established Phase 1 defensive-degradation convention (comment at lines 66-73 documents exactly this precedent for `get_credit_balance`).

**Error-code-to-banner mapping to extend for the two new functions** (per CLAUDE.md's table, applied identically at lines 34-39):
| Code | `check_apollo_health` precedent | New behavior required (D-06/UI-SPEC Copywriting Contract) |
|------|-----------------------------------|---------------------------------------------------------|
| 401 | `"Apollo connection failed — check that APOLLO_API_KEY is set correctly..."` | Reuse verbatim in `bulk_match_people` |
| 403 | `"Apollo connection failed — this key is not a Master API key..."` | Reuse verbatim in `bulk_match_people` |
| 429 | not yet implemented anywhere (Pitfall 2 — genuinely new) | exponential backoff, max 3 retries, only surface banner after all exhausted — see "No Analog Found" below, use RESEARCH.md Pattern 1/Pitfall 2 code directly |
| 422 | not yet implemented anywhere | surface `resp.json()["message"]` directly per UI-SPEC Copywriting Contract row "Enrichment failure — missing/invalid param or insufficient credits (422)" |

---

### `db/prospects.py` (NEW) — model, CRUD

**Analog:** `db/schema.py` (connection/parameterized-query conventions) + `tests/test_schema.py` (concrete `?`-placeholder query examples against the exact tables/view this module must read/write).

**Connection lifecycle pattern to copy** (`db/schema.py` lines 73-90, `ensure_schema`):
```python
def ensure_schema(db_path: str = "db/outreach.db") -> None:
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        conn.executescript(VIEW_DDL)
        conn.commit()
    finally:
        conn.close()
```
`db/prospects.py`'s functions (e.g. `dedup_filter(db_path, candidates)`, `insert_enriched(db_path, rows)`) should follow the same `conn = sqlite3.connect(db_path)` / `try: ... finally: conn.close()` shape, defaulting `db_path` to the same `"db/outreach.db"` constant used in `db/schema.py` so both modules stay in sync — do not hardcode a second default path.

**The exact view/columns to query for DEDUP-02** (`db/schema.py` lines 54-70, `VIEW_DDL`):
```sql
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
WHERE p.apollo_contact_id IS NOT NULL;
```
`dedup_filter()` must `SELECT apollo_person_id, dedupable_domain FROM contacted_registry` (or equivalent) and filter incoming search candidates against both fields — id-level dedup always applies, domain-level dedup only applies where `dedupable_domain IS NOT NULL` (per RESEARCH.md's Don't Hand-Roll table: don't reimplement the free-domain exclusion list, query this view).

**Parameterized `?`-placeholder query/insert style to copy** (`tests/test_schema.py` lines 46-54 and 88-93 — these are the only existing examples of writing to `prospect` in this codebase):
```python
cur.execute(
    "INSERT INTO prospect (name, company_domain, apollo_contact_id, status) "
    "VALUES (?, ?, ?, 'contact_created')",
    ("Free Domain Contact", "gmail.com", "apollo-contact-1"),
)
```
and
```python
conn1.execute(
    "INSERT INTO prospect (name, company_domain, status) VALUES (?, ?, 'found')",
    ("Reconnect Test Contact", "example.com"),
)
```
`insert_enriched()` must use this exact `?`-placeholder style (never f-string interpolation of Apollo-derived or user free-text values — Phase 1's Security Domain rule, restated in CONTEXT.md's code_context and RESEARCH.md's Anti-Patterns). New rows should set `status = 'enriched'`, populate `apollo_person_id`, `email`, `company_domain` (parsed via `urllib.parse.urlparse` per RESEARCH.md's Don't Hand-Roll table — do not hand-roll a regex domain parser), and `path`.

**Domain-level status enum reference** (`db/schema.py` lines 22-27):
```sql
status TEXT NOT NULL DEFAULT 'found'
    CHECK (status IN (
        'found','selected','enriched',
        'contact_created','drafted','approved','sequenced'
    )),
```
Inserted rows from this phase progress to `'enriched'` (per CONTEXT.md code_context: "status progresses `found` → `selected` → `enriched`") — do not write any other status value from this phase's code.

---

### `pages/discovery_page.py` (NEW) — component/route, request-response + event-driven

**Analog:** `pages/health_page.py` — same role (a single Streamlit page module executed by `st.navigation`), same external-call-wrapping conventions, though `health_page.py`'s flow is single-pass (checks run unconditionally on load) while `discovery_page.py`'s flow is two-stage and button-gated (see "No Analog Found" for the session-state addition RESEARCH.md supplies).

**`st.secrets` read pattern — copy exactly** (`pages/health_page.py` lines 20-29):
```python
import streamlit as st

from apollo.client import check_apollo_health, get_credit_balance
from mailbox.dns_checks import check_dkim, check_dmarc, check_spf

st.title("System Health")
st.caption("Checked automatically every time the app loads.")

apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")
```
`discovery_page.py` opens the same way: `import streamlit as st`, import the new `apollo.client` functions and `db.prospects` functions, `st.title("Contact Discovery")` + `st.caption(...)` (exact copy from UI-SPEC's Copywriting Contract), then `apollo_key = st.secrets.get("APOLLO_API_KEY")` — never re-derive or re-validate the key here; Phase 1's health gate in `app.py`/`health_page.py` already guarantees a valid key by the time any other page runs.

**Try/except-degrade-to-banner wrapping every external call — copy exactly** (`pages/health_page.py` lines 38-44 and 94-97):
```python
try:
    apollo_ok, apollo_banner = check_apollo_health(apollo_key)
except Exception:
    apollo_ok, apollo_banner = (
        False,
        "Apollo connection failed — check your internet connection and try again.",
    )
```
and
```python
try:
    spf_ok, spf_msg = check_spf(sending_domain)
except Exception:
    spf_ok, spf_msg = False, "SPF check failed unexpectedly — please try again."
```
Every call to `search_people()` / `bulk_match_people()` / `db.prospects` functions inside `discovery_page.py`'s button blocks must be wrapped the same way — even though the client functions themselves are typed-tuple never-raise, this second defensive layer is the established belt-and-suspenders convention in this codebase (comment at `health_page.py` line 14-16 states this explicitly: "wrapped in try/except so an unexpected exception renders a plain-language st.error banner instead of a Streamlit traceback").

**`st.spinner` around a blocking external call — copy exactly** (`pages/health_page.py` line 31, and the same pattern repeated per-check):
```python
with st.spinner("Checking Apollo connection and mailbox setup..."):
    ...
```
Use `st.spinner("Searching Apollo for matching contacts...")` around the Find Contacts pipeline and `st.spinner("Enriching contacts with verified emails...")` around the Enrich pipeline (exact copy already locked in UI-SPEC's Layout & Discovery Flow State System table and in RESEARCH.md's Pattern 2).

**`st.status`/`st.success`/`st.error`/`st.warning` semantic-color convention** (`pages/health_page.py` lines 46-63):
```python
if apollo_ok:
    ...
    st.success(apollo_banner, icon=":material/check_circle:")
else:
    st.error(apollo_banner, icon=":material/cancel:")
```
Map directly to UI-SPEC's icon table: `st.info(..., icon=":material/manage_search:")` for the count/cost result, `st.info(..., icon=":material/search_off:")` for the empty state (D-12 — **never** `st.warning`/`st.error` for zero-results, per UI-SPEC's Color table explicitly calling this out as a common mistake to avoid), `st.error(..., icon=":material/cancel:")` for search/enrichment failures, `st.success(..., icon=":material/check_circle:")` for the enrichment-complete confirmation.

**`st.button` + hard-stop-on-failure precedent** (`pages/health_page.py` lines 65-69) — informs the pattern but is NOT copied verbatim, since Phase 2 never hard-stops the page (UI-SPEC: "inputs and both buttons remain usable so the teammate can retry" on failure):
```python
st.button("Recheck Connection", icon=":material/refresh:")
...
if not apollo_ok:
    st.stop()
```
Use this only as a *counter-example*: `discovery_page.py` must NOT call `st.stop()` on a search/enrichment failure — the correct behavior (per UI-SPEC Stage table) is to render the `st.error` banner and let the rest of the page (form inputs, both buttons) continue rendering normally so the teammate can immediately retry.

---

### `app.py` (EXTEND) — config/route registration

**Analog:** `app.py` itself — the extension point is an explicit pre-existing comment.

**Exact insertion point** (lines 36-45):
```python
pages = {
    "Health": [st.Page("pages/health_page.py", title="System Health", default=True)],
    # Phase 2+ will append real pages here (e.g. Discovery, Personalization,
    # Review Queue, Campaign Dashboard) once the Apollo health gate passes.
}

pg = st.navigation(pages)
pg.run()
```
Add a new key (e.g. `"Discovery": [st.Page("pages/discovery_page.py", title="Contact Discovery")]`) to the `pages` dict, replacing the comment placeholder. Keep `"Health"` as `default=True` — Phase 2 does not change the default landing page (per CLAUDE.md's page list, Health remains the boot-time gate). Do not touch the schema-bootstrap (lines 21-22) or secrets-gate (lines 24-34) sections above the `pages` dict — those are unchanged Phase 1 infrastructure this phase depends on but does not modify.

---

### `tests/test_apollo_client.py` (EXTEND) — test, request-response

**Analog:** `tests/test_apollo_client.py` itself + `tests/conftest.py`'s `mock_requests_response` fixture.

**Full existing test to copy the shape of** (lines 1-36):
```python
"""RED tests for Apollo health checks (apollo/client.py, not yet implemented).

Imports are performed inside the test body so `pytest --collect-only` succeeds
before apollo/client.py exists (Plan 01-03 implements it).
"""
import requests


def test_check_apollo_health(monkeypatch, mock_requests_response):
    from apollo.client import check_apollo_health

    # 401 -> invalid/missing key
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: mock_requests_response(401, {})
    )
    ok, message = check_apollo_health("bad-key")
    assert ok is False
    assert isinstance(message, str) and message
    ...
```
New tests (`test_search_people_error_codes`, `test_bulk_match_people_error_codes`, `test_bulk_match_people_batches_of_ten`) must: (1) import the target function inside the test body (RED-test-before-implementation convention, stated explicitly in the module docstring), (2) `monkeypatch.setattr(requests, "post", ...)` (note: new functions use `requests.post`, not `requests.get` — match `search_people`'s/`bulk_match_people`'s actual verb), (3) use the shared `mock_requests_response(status_code, json_data)` fixture, never build a bespoke fake response object.

**Fixture to reuse, not reimplement** (`tests/conftest.py` lines 23-41):
```python
class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


@pytest.fixture
def mock_requests_response():
    def _make(status_code: int, json_data: dict | None = None) -> _FakeResponse:
        return _FakeResponse(status_code, json_data)

    return _make
```
This fixture already covers everything both new client functions need (status_code + json body) — no new conftest fixture is required for `test_apollo_client.py`'s extension, confirming RESEARCH.md's Wave 0 Gaps note ("No new fixtures needed... `mock_requests_response` already cover this phase's needs").

---

### `tests/test_prospects.py` (NEW) — test, CRUD

**Analog:** `tests/test_schema.py` (only existing test file that exercises the `prospect` table and `contacted_registry` view).

**Fixture + idempotent-bootstrap setup pattern to copy** (`tests/test_schema.py` lines 9-16):
```python
def test_ensure_schema_idempotent(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)
    ensure_schema(tmp_db_path)
    ...
```
Every `test_prospects.py` test should start with `from db.schema import ensure_schema` + `ensure_schema(tmp_db_path)` to get a real schema (not a mock) before exercising `db.prospects` functions against it — `tmp_db_path` (from `conftest.py`) is already the established per-test isolated SQLite file fixture, reuse it directly.

**Dedup/registry query assertion style to copy** (`tests/test_schema.py` lines 57-74, `test_registry_excludes_free_domains`):
```python
cur.execute(
    "SELECT company_domain, dedupable_domain FROM contacted_registry "
    "WHERE apollo_contact_id = ?",
    ("apollo-contact-1",),
)
row = cur.fetchone()
assert row[0] == "gmail.com"
assert row[1] is None
```
`test_dedup_filter_excludes_known_contacts` should seed `prospect` rows (via direct parameterized `INSERT`, same as the analog) representing "already contacted" state, then call `db.prospects.dedup_filter(...)` and assert the known id/domain are excluded from the returned candidate list — mirror the seed-then-assert two-part structure exactly.

---

### `tests/test_discovery_logic.py` (NEW) — test, transform (pure functions)

**Analog:** `tests/test_dns_checks.py` — closest existing example of testing pure/near-pure transformation functions with table-style assertions and no database involved.

**Structure to copy** (lines 1-42, full file):
```python
"""RED tests for SPF/DMARC/DKIM checks (mailbox/dns_checks.py, not yet implemented).

Imports are performed inside the test body so `pytest --collect-only` succeeds
before mailbox/dns_checks.py exists (Plan 01-03 implements it).
"""


def test_check_spf_dmarc_dkim(mock_dns_txt):
    from mailbox.dns_checks import check_spf, check_dmarc, check_dkim

    domain = "example.com"

    # SPF present
    mock_dns_txt({domain: ["v=spf1 include:_spf.example.com ~all"]})
    ok, message = check_spf(domain)
    assert ok is True
    assert isinstance(message, str) and message
    ...
```
`test_discovery_logic.py`'s functions (`test_to_filter_list`, `test_has_email_prefilter`, `test_cost_estimate_no_apollo_call`, `test_path_does_not_affect_filters`) are even simpler than this analog — no fixture/monkeypatch needed at all for pure functions like `to_filter_list()` (RESEARCH.md Pattern 4) and the cost-estimate formula (`min(len(final_candidates), 50)`). Keep the same docstring convention (module docstring stating these are RED tests written before the corresponding module exists) and the same "import inside test body" convention. Where the target module doesn't exist yet, decide during planning whether these pure helpers live in `apollo/client.py` (translation + prefilter, since they're tightly coupled to the search/enrichment call sequence) or a new small module — RESEARCH.md's Project Structure does not name a dedicated file for them, so the planner should assign them explicitly (likely co-located in `apollo/client.py` alongside `search_people`, since `to_filter_list` is `search_people`'s direct input-shaping step).

---

## Shared Patterns

### Typed-tuple, never-raise client functions
**Source:** `apollo/client.py` lines 20-44 (`check_apollo_health`), 47-77 (`get_credit_balance`)
**Apply to:** `search_people()`, `bulk_match_people()` in `apollo/client.py`
```python
try:
    resp = requests.post(..., timeout=10)
except requests.RequestException:
    return None, "... — check your internet connection and try again."
if resp.status_code == 401:
    return None, "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."
# ... 403, 429, generic != 200 ...
data = resp.json()
return data.get(...), "OK"
```

### Try/except-wrap every external call at the page layer
**Source:** `pages/health_page.py` lines 38-44, 94-97, 108-111, 122-125
**Apply to:** every `apollo.client.*` / `db.prospects.*` call inside `pages/discovery_page.py`
```python
try:
    result = some_call(...)
except Exception:
    result = (None, "Plain-language fallback message — please try again.")
```

### Parameterized SQL only — never f-string interpolation
**Source:** `tests/test_schema.py` lines 46-54, 88-93 (only existing examples of writing to `prospect`)
**Apply to:** every query/insert in `db/prospects.py`
```python
cur.execute(
    "INSERT INTO prospect (name, company_domain, apollo_contact_id, status) VALUES (?, ?, ?, ?)",
    (name, company_domain, apollo_contact_id, "enriched"),
)
```

### `st.secrets` for API keys, never logged
**Source:** `app.py` lines 26-27, `pages/health_page.py` lines 28-29
**Apply to:** `pages/discovery_page.py` — read `apollo_key = st.secrets.get("APOLLO_API_KEY")` once at module top, pass it into client functions as a parameter; never `print`/`st.write`/log it.

### RED-test-before-implementation, import-inside-body
**Source:** `tests/test_apollo_client.py` lines 1-10, `tests/test_schema.py` lines 1-6, `tests/test_dns_checks.py` lines 1-9 (consistent across all 3 existing test files)
**Apply to:** all 3 new/extended test files — module docstring states tests are written before the target module exists, and every `from <module> import <fn>` happens inside the test function body, not at module top, so `pytest --collect-only` succeeds pre-implementation.

### Empty-state must render as `st.info`, never `st.warning`/`st.error`
**Source:** `02-UI-SPEC.md` Color table (explicit call-out) — no direct code analog exists yet in this codebase (Phase 1 has no "zero results, not a failure" state), but this is a hard cross-cutting rule for `pages/discovery_page.py`'s D-12 empty-state branch. Do not reuse `health_page.py`'s `st.warning` pattern (used there for DKIM/SPF/DMARC soft-fail states) for the zero-contacts case — semantically different (nothing failed, no credits spent).

## No Analog Found

Files/behaviors with no close structural match in the codebase — planner should use RESEARCH.md's worked examples directly instead of a codebase port:

| File | Role | Data Flow | Reason | Recommended Source |
|------|------|-----------|--------|----------------------|
| `pages/discovery_page.py` — the two-stage `st.session_state`-gated Find→Enrich flow itself (as opposed to the single-pass render style `health_page.py` uses) | component | event-driven | Phase 1 has exactly one page and it runs its checks unconditionally on every load — there is no existing multi-button, session-state-persisted flow anywhere in this repo to copy | RESEARCH.md "Pattern 2: Session-state-driven two-stage flow" (full worked example, CITED from official Streamlit docs: docs.streamlit.io/develop/concepts/architecture/session-state) |
| `apollo/client.py` — 429 exponential-backoff retry helper (`_post_with_retry` or equivalent) | utility (internal to service) | request-response | Explicitly flagged in RESEARCH.md Pitfall 2 as "no retry logic exists yet anywhere in the codebase" — Phase 1's two endpoints never hit real rate limits in normal use, so this is genuinely new code | RESEARCH.md "Don't Hand-Roll" table (≤15-line local helper, not a `tenacity` dependency) + Pitfall 2's exact requirement (max 3 retries, only surface banner after all exhausted) |

## Metadata

**Analog search scope:** entire repository (`apollo/`, `db/`, `pages/`, `mailbox/`, `tests/`, `app.py`) — small enough (8 pre-existing `.py` files, 661 total lines) to read in full rather than sample
**Files scanned:** `apollo/client.py`, `db/schema.py`, `pages/health_page.py`, `app.py`, `tests/test_apollo_client.py`, `tests/conftest.py`, `tests/test_schema.py`, `tests/test_dns_checks.py`, `mailbox/dns_checks.py`, `.planning/phases/02-contact-discovery/02-UI-SPEC.md`
**Pattern extraction date:** 2026-07-24
