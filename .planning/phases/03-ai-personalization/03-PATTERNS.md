# Phase 3: AI Personalization - Pattern Map

**Mapped:** 2026-09-17
**Files analyzed:** 13 (5 new, 8 modified)
**Analogs found:** 13 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `personalization/__init__.py` | config (package init) | — | `apollo/__init__.py` | exact |
| `personalization/generator.py` | service | request-response (external API) | `apollo/client.py` | exact |
| `personalization/templates.py` | utility | transform | `discovery/logic.py` | role-match |
| `db/schema.py` (extend) | migration | batch (idempotent DDL) | `db/schema.py` itself (existing `ensure_schema`) | exact |
| `db/prospects.py` (extend) | model/service | CRUD | `db/prospects.py`'s own `insert_enriched` | exact |
| `pages/discovery_page.py` (extend) | controller (Streamlit page) | request-response, chained event | `pages/discovery_page.py` itself (existing "Enrich & Continue" handler) + `pages/health_page.py` (banner convention) | exact |
| `app.py` (extend) | config (boot gate) | request-response | `app.py` itself (existing `APOLLO_API_KEY` gate) | exact |
| `tests/test_personalization.py` | test | unit (mocked external client) | `tests/test_apollo_client.py` (mocking pattern) + `tests/test_prospects.py` (real-schema pattern) | exact |
| `tests/test_prospects.py` (extend) | test | CRUD (real sqlite) | `tests/test_prospects.py` itself (`test_insert_enriched_writes_enriched_status`) | exact |
| `tests/test_schema.py` (extend) | test | batch (idempotency) | `tests/test_schema.py` itself (`test_ensure_schema_idempotent`) | exact |
| `tests/conftest.py` (extend) | test fixture | — | `tests/conftest.py` itself (`mock_requests_response` factory fixture) | exact |
| `requirements.txt` (extend) | config | — | `requirements.txt` itself | exact |
| `.streamlit/secrets.toml.example` (extend) | config | — | `.streamlit/secrets.toml.example` itself | exact |

## Pattern Assignments

### `personalization/generator.py` (service, request-response)

**Analog:** `apollo/client.py`

**Imports pattern** (lines 1-27 of `apollo/client.py`):
```python
"""[module docstring: purpose, never-raise contract, NEVER log/print api_key rule]"""
from __future__ import annotations

import time

import requests

APOLLO_BASE = "https://api.apollo.io/api/v1"
```
For `personalization/generator.py`, mirror this exactly but with `import anthropic` and a `MODEL = "claude-haiku-4-5-20251001"` module constant instead of `APOLLO_BASE`. Same `NEVER log or print the api_key` docstring rule applies to `ANTHROPIC_API_KEY`.

**Typed-tuple, never-raise client-call pattern** (`apollo/client.py` lines 30-54, `check_apollo_health`):
```python
def check_apollo_health(api_key: str) -> tuple[bool, str]:
    """Validate the Apollo Master API key via GET /auth/health.

    Returns (valid, banner_message). Never raises.
    """
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
    ...
```
`generate_opening_line(client, title, company) -> tuple[str | None, str]` must follow this exact shape: try the call, catch the SDK's typed exceptions (not a bare `except Exception` for the network call itself — see error-handling section below), return `(None, message)` on any failure, `(line, "OK")` on success. Never raises, never lets an `anthropic.*Error` propagate to the caller (`pages/discovery_page.py`).

**Error handling pattern** — status-code-branching style from `bulk_match_people` (`apollo/client.py` lines 159-194), adapted to Anthropic's typed exception hierarchy instead of HTTP status codes:
```python
    if resp.status_code == 401:
        return None, "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."
    if resp.status_code == 403:
        return None, "Apollo connection failed — this key is not a Master API key. Check Apollo Settings → Integrations → API Keys."
    if resp.status_code == 429:
        return None, "Apollo is rate-limiting enrichment requests — please wait a few minutes and try again."
    if resp.status_code == 422:
        apollo_message = resp.json().get("message", "invalid request")
        return None, f"Apollo couldn't enrich these contacts — {apollo_message}"
    if resp.status_code != 200:
        return None, f"Contact enrichment failed — unexpected status {resp.status_code}."
```
Map this 1:1 onto `anthropic.APIConnectionError` / `anthropic.RateLimitError` / `anthropic.APIStatusError` (see 03-RESEARCH.md Pattern 1 for the exact except-clause shape) — same "one branch per known failure mode, plain-language message, never a raw exception/traceback" convention.

**Retry pattern (D-15):** `apollo/client.py`'s `_post_with_retry` (lines 90-122) hand-rolls exponential backoff for 429s — **do NOT copy this helper for the Anthropic call**. RESEARCH.md's Don't Hand-Roll table is explicit: use `anthropic.Anthropic(max_retries=1, timeout=20.0)` (constructed once, mirroring `apollo/client.py`'s `timeout=15` convention on `_post_with_retry`) instead of a second hand-rolled retry loop. The `timeout=` convention (bounded, not the SDK's 10-minute default) is the one thing to carry over from `_post_with_retry`'s spirit, not its code.

**Defensive `.get()` pattern** (`apollo/client.py` line 84, `get_credit_balance`):
```python
    credits = data.get("credits") or data.get("credit_balance")
```
Apply the same style when reading `match.get("title")`, `match.get("organization", {}).get("name")` from the raw Apollo match dict inside the calling loop in `discovery_page.py` — never assume a key is present.

---

### `personalization/templates.py` (utility, transform)

**Analog:** `discovery/logic.py`

**Module shape** (`discovery/logic.py` lines 1-11):
```python
"""Pure, network-free discovery transforms for the Find Contacts stage.

No `requests`, no live Apollo, no AI normalization — every function here is a
deterministic transform over already-fetched data or plain free-text strings.
"""
from __future__ import annotations

CONTACT_CAP = 50
```
`personalization/templates.py` should follow the same "pure functions, module-level constants, no I/O" shape — module docstring stating "no network calls, static string templates only," then `PATH_TEMPLATES` as the module-level constant dict (parallel to `PATH_CONFIG` in `discovery/logic.py`), then `assemble_email()` as a pure function.

**Pure-function-with-docstring-rationale pattern** (`discovery/logic.py` lines 41-52, `build_search_filters`):
```python
def build_search_filters(
    company_type: str, target_role: str
) -> tuple[list[str], list[str]]:
    """Translate free text into (person_titles, org_keyword_tags).

    Takes NO path argument — path selection never affects search filters
    (DISC-01/PATH-02, D-01). person_titles derives from target_role,
    org_keyword_tags derives from company_type.
    """
    person_titles = to_filter_list(target_role)
    org_keyword_tags = to_filter_list(company_type)
    return person_titles, org_keyword_tags
```
`assemble_email(path_slug, first_name, company, opening_line) -> tuple[str, str]` should follow the same "typed signature, one-line summary, a rationale-callout paragraph referencing the driving decision (D-09), pure transform body, tuple return" shape. Also mirror the `PATH_CONFIG` slug convention already established (`"club_sponsorship"`, `"productthon"`, `"client_sourcing"` — these exact slugs from `discovery/logic.py`'s `PATH_CONFIG` must be reused as `PATH_TEMPLATES` dict keys, not re-invented).

---

### `personalization/__init__.py` (config, package init)

**Analog:** `apollo/__init__.py`

Empty file — `apollo/__init__.py` and `db/__init__.py` are both zero-byte files. Create `personalization/__init__.py` as an empty file with no content, exactly matching this convention (no `__all__`, no re-exports).

---

### `db/schema.py` (migration, extend)

**Analog:** the file's own existing `ensure_schema()` / `DDL` structure

**Idempotent-boot pattern** (`db/schema.py` lines 73-90, `ensure_schema`):
```python
def ensure_schema(db_path: str = "db/outreach.db") -> None:
    """Create the dedup registry schema if it does not already exist.

    Idempotent: safe to call on every app boot. Creates the parent directory
    of db_path if missing so a fresh checkout auto-creates the DB with no
    manual setup step (SC-3).
    """
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
Add a `_NEW_COLUMNS` list + `_migrate_columns(conn)` helper (exact code given in 03-RESEARCH.md Pitfall 1 — `opening_line TEXT`, `first_name TEXT`, `draft_source TEXT`, each guarded by `try/except sqlite3.OperationalError` swallowing only `"duplicate column name"`), called from inside `ensure_schema()`'s existing `try:` block, after `conn.executescript(VIEW_DDL)` and before `conn.commit()`. This is additive to the existing function — do not touch `DDL`'s `CREATE TABLE IF NOT EXISTS prospect (...)` string itself, since that has no effect against the already-populated `db/outreach.db` (Pitfall 1 in RESEARCH.md — critical, do not skip the migration step and assume editing `DDL` is sufficient).

**Connection lifecycle convention:** every function in this codebase (`ensure_schema`, `insert_enriched`, `dedup_filter`) uses `conn = sqlite3.connect(db_path); try: ... finally: conn.close()`. Follow this exactly — never leave a connection unclosed on an exception path.

---

### `db/prospects.py` (model/service, extend)

**Analog:** the file's own `insert_enriched()` (lines 83-129)

**Imports pattern** (lines 1-12):
```python
"""[module docstring: purpose, security rule pointer]

Follows db/schema.py's connection lifecycle convention exactly: a fresh
sqlite3.connect() per call, wrapped in try/finally so the connection always
closes. All SQL uses `?` placeholders exclusively — never f-string/`.format`/
`%` interpolation of Apollo-derived or user free-text values into SQL
(Phase 1 Security Domain rule, T-02-01).
"""
from __future__ import annotations

import sqlite3
from urllib.parse import urlparse
```

**Parameterized-write CRUD pattern** (lines 104-129, `insert_enriched`):
```python
def insert_enriched(
    rows: list[dict], path: str, db_path: str = "db/outreach.db"
) -> int:
    """..."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        count = 0
        for match in rows:
            name = match.get("name")
            ...
            cur.execute(
                "INSERT INTO prospect "
                "(name, company, company_domain, apollo_person_id, email, path, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'enriched')",
                (name, company, company_domain, apollo_person_id, email, path),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()
```
This is the exact shape for the new `update_draft()` function — 03-RESEARCH.md's Code Examples section already provides the concrete implementation to use verbatim:
```python
def update_draft(
    prospect_id: str | int, opening_line: str, source: str, db_path: str = "db/outreach.db"
) -> None:
    """Persist a generated draft and advance status to 'drafted' (D-04)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE prospect SET opening_line = ?, draft_source = ?, "
            "status = 'drafted', updated_at = CURRENT_TIMESTAMP "
            "WHERE apollo_person_id = ?",
            (opening_line, source, prospect_id),
        )
        conn.commit()
    finally:
        conn.close()
```
Note `apollo_person_id` (not the internal `id` PK) is the correct `WHERE` key — matches the raw Apollo match dict's `id` field already in scope in `discovery_page.py`'s loop, consistent with how `insert_enriched` stores it.

---

### `pages/discovery_page.py` (controller, extend)

**Analog:** the file's own existing "Enrich & Continue" handler + `pages/health_page.py`'s banner convention

**Session-state result pattern** (lines 50-53, 117, 176):
```python
if "find_result" not in st.session_state:
    st.session_state.find_result = None  # None = not yet searched this session
if "enrich_result" not in st.session_state:
    st.session_state.enrich_result = None
...
find_result = st.session_state.find_result
...
enrich_result = st.session_state.enrich_result
```
Add `st.session_state.draft_result` following this identical pattern (init to `None`, write a dict with `"error"` + payload keys, read back for rendering below).

**Try/except-wrapped external call, never a bare traceback** (lines 145-175, the "Enrich & Continue" button handler):
```python
if st.button("Enrich & Continue", type="primary", icon=":material/bolt:"):
    with st.spinner("Enriching contacts with verified emails..."):
        try:
            matches, message = enrich_candidates(
                apollo_key, find_result["candidates"]
            )
        except Exception:
            matches, message = (
                None,
                "Contact enrichment failed — check your internet connection and try again.",
            )

        if matches is None:
            st.session_state.enrich_result = {"error": message, "rows": None}
        else:
            try:
                slug = PATH_CONFIG[selected_path]["slug"]
                insert_enriched(matches, path=slug)
                st.session_state.enrich_result = {"error": None, "rows": matches}
            except Exception:
                # Rule 2: a DB write failure means the "written to
                # prospect" guarantee did not hold — surface a
                # failure banner rather than a false success.
                st.session_state.enrich_result = {
                    "error": "Contact enrichment failed — check your internet connection and try again.",
                    "rows": None,
                }
```
D-01's automatic chaining goes directly inside this same `if matches is None: ... else:` block, immediately after `insert_enriched(matches, path=slug)` succeeds — not a separate button. Wrap the per-contact Haiku loop in the same try/except-degrades-to-banner style; never let an `anthropic` exception or a stray `KeyError` escape to a traceback.

**Progress-bar pattern (new, not in existing code — use `st.progress`):** No existing analog for `st.progress` in this repo (only `st.spinner` is used today, e.g. line 81, 146). RESEARCH.md's Code Examples section is authoritative here — use `st.progress(0, text=...)` updated per-iteration, since a 50-contact batch is a distinctly-visible-duration operation unlike the single spinner-wrapped calls elsewhere in this file.

**Banner convention** (`pages/health_page.py` lines 94-137, mailbox soft-block section — never `st.stop()`):
```python
    if spf_ok:
        st.success(spf_msg, icon=":material/check_circle:")
    else:
        st.warning(
            "SPF: not found — add a TXT record starting with v=spf1 to your "
            "sending domain's DNS settings before sending a campaign.",
            icon=":material/error:",
        )
```
D-16's batch-failure banner must use `st.warning(..., icon=":material/error:")` in this same non-blocking style (no `st.stop()`), matching `discovery_page.py`'s own existing `st.error`/`st.info` banner calls (lines 121, 125, 132, 139, 180) rather than `health_page.py`'s D-01 hard-block pattern (lines 65-69, `st.stop()`) — this page's own docstring (lines 16-21) explicitly states "This page never hard-stops on a failure."

**Table + expander rendering** (lines 189-200, the existing `st.dataframe` results table):
```python
            table_rows = [
                {
                    "Name": match.get("name"),
                    "Company": (match.get("organization") or {}).get("name"),
                    "Title": match.get("title"),
                    "Email": match.get("email"),
                }
                for match in rows
            ]
            st.dataframe(table_rows)
```
D-02's "expandable View draft per row" extends this same block — after `st.dataframe(table_rows)`, loop over `rows` again pairing each with its `draft_result` entry and render `st.expander(f"View draft — {match.get('name')}")` containing the single combined subject+body block (D-03).

---

### `app.py` (config, extend)

**Analog:** the file's own existing `APOLLO_API_KEY` presence gate (lines 24-34)

```python
# 2. Secrets presence gate (SC-2). This only checks that the key is *set*;
#    validity against Apollo's API is checked inside health_page.py (D-01).
apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")

if not apollo_key:
    st.error(
        "APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
        "Community Cloud secrets console (production)."
    )
    st.stop()
```
Add an identical `if not anthropic_key: st.error(...); st.stop()` block right after this one, reading `st.secrets.get("ANTHROPIC_API_KEY")`, with the equivalent message text substituting `ANTHROPIC_API_KEY`. Same fail-closed-before-navigation philosophy — this is a hard boot-time gate, unlike the page-level soft-fail convention in `discovery_page.py`.

---

### `tests/test_personalization.py` (new test file)

**Analogs:** `tests/test_apollo_client.py` (mocked-external-call pattern) + `tests/test_prospects.py` (real-schema pattern, for any persistence-adjacent test)

**Deferred-import-for-RED-collection pattern** (`tests/test_apollo_client.py` lines 1-9, module docstring):
```python
"""RED tests for Apollo health checks (apollo/client.py, not yet implemented).

Imports are performed inside the test body so `pytest --collect-only` succeeds
before apollo/client.py exists (Plan 01-03 implements it).
"""
```
Every test function in `test_personalization.py` must do `from personalization.generator import generate_opening_line` (etc.) **inside the test body**, not at module top, exactly matching this repo-wide convention — so `pytest --collect-only` succeeds before `personalization/generator.py` exists.

**Monkeypatched-client-error-code-table pattern** (`tests/test_apollo_client.py` lines 45-98, `test_search_people_error_codes` / `test_search_people_never_raises_on_network`):
```python
def test_search_people_never_raises_on_network(monkeypatch):
    from apollo.client import search_people

    def _raise(*a, **k):
        raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "post", _raise)
    people, message = search_people("good-key", ["director"], ["software"])
    assert people is None
    assert isinstance(message, str) and message
```
Adapt this exact shape for `generate_opening_line`: monkeypatch a fake `client.messages.create` to raise `anthropic.APIConnectionError`/`anthropic.RateLimitError`/`anthropic.APIStatusError`, assert `(None, message)` with a non-empty string message — never a raised exception escaping the test.

**Fake-response-object factory pattern** (`tests/conftest.py` lines 23-41, `_FakeResponse` / `mock_requests_response`) — see conftest.py section below for the new `mock_anthropic_message` fixture this test file will consume.

---

### `tests/test_prospects.py` (extend)

**Analog:** the file's own `test_insert_enriched_writes_enriched_status` (lines 76-118)

```python
def test_insert_enriched_writes_enriched_status(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched

    rows = [...]
    count = insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)
    assert count == 2

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT ... FROM prospect ORDER BY name")
        inserted = cur.fetchall()
    finally:
        conn.close()

    assert len(inserted) == 2
    for name, email, apollo_person_id, company_domain, path, status in inserted:
        assert status == "enriched"
        ...
```
`test_update_draft_writes_status_drafted` should follow this exact shape: `ensure_schema(tmp_db_path)` → seed a row at `status='enriched'` via raw `sqlite3` insert (or `insert_enriched`) → call `update_draft(...)` → reconnect and assert `opening_line`, `draft_source`, `status == 'drafted'` via direct SQL SELECT, never through the function under test.

---

### `tests/test_schema.py` (extend)

**Analog:** the file's own `test_ensure_schema_idempotent` (lines 9-33)

```python
def test_ensure_schema_idempotent(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)
    ensure_schema(tmp_db_path)  # Second call must not raise

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('prospect', 'email_events', 'free_email_domains')"
        )
        table_names = {row[0] for row in cur.fetchall()}
        assert table_names == {"prospect", "email_events", "free_email_domains"}
    finally:
        conn.close()
```
`test_column_migration_idempotent` needs one extra setup step this analog doesn't have: create a `prospect` table **without** the new columns first (simulating the pre-existing populated `db/outreach.db`), then call `ensure_schema()` twice, then assert via `PRAGMA table_info(prospect)` that `opening_line`/`first_name`/`draft_source` are present and no exception was raised on either call — directly testing Pitfall 1 from RESEARCH.md.

---

### `tests/conftest.py` (extend)

**Analog:** the file's own `_FakeResponse` / `mock_requests_response` factory fixture (lines 23-41)

```python
class _FakeResponse:
    """Minimal stand-in for requests.Response used in unit tests."""

    def __init__(self, status_code: int, json_data: dict | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


@pytest.fixture
def mock_requests_response():
    """Factory fixture: mock_requests_response(status_code, json_data) -> _FakeResponse."""

    def _make(status_code: int, json_data: dict | None = None) -> _FakeResponse:
        return _FakeResponse(status_code, json_data)

    return _make
```
Add a parallel `mock_anthropic_message` factory fixture in this exact style — a minimal fake-object class plus a factory fixture function. RESEARCH.md's Wave 0 Gaps section specifies the shape needed: `.content = [SimpleNamespace(type="text", text="...")]` (matching the real SDK response's `message.content` list-of-content-blocks shape consumed by `generator.py`'s `text_blocks = [b.text for b in message.content if b.type == "text"]` line), so tests can monkeypatch `client.messages.create` without a real API key — same "minimal stand-in, not the real SDK object" philosophy as `_FakeResponse`.

---

### `requirements.txt` (extend)

**Analog:** the file's own existing pinned-version convention

```
streamlit==1.59.2
requests==2.34.2
dnspython==2.8.0
```
Add `anthropic==1.6.0` as a fourth line, exact-pinned (matching the existing convention of exact `==` pins for every dependency, not a `>=` range) per RESEARCH.md's Standard Stack recommendation.

---

### `.streamlit/secrets.toml.example` (extend)

**Analog:** the file's own existing two-key convention

```toml
APOLLO_API_KEY = "your-master-api-key"
SENDING_DOMAIN = "outreach.yourclub.org"
```
Add `ANTHROPIC_API_KEY = "your-anthropic-api-key"` as a third line, matching the existing placeholder-string style exactly.

## Shared Patterns

### Typed-tuple, never-raise external-API client function
**Source:** `apollo/client.py` (every function: `check_apollo_health`, `get_credit_balance`, `search_people`, `bulk_match_people`)
**Apply to:** `personalization/generator.py`'s `generate_opening_line()`
Every external-service call in this codebase returns `(result_or_None, message: str)` and never lets a library exception propagate past the function boundary. This is the single most important cross-cutting convention for the new Anthropic-calling code.

### Plain-language banner, never a traceback; page never hard-stops on external-call failure
**Source:** `pages/discovery_page.py` (module docstring, lines 16-21) + `pages/health_page.py`'s soft-block sections (SPF/DMARC/DKIM, lines 94-137)
**Apply to:** `pages/discovery_page.py`'s new draft-generation block (D-16's banner)
Every external call site in `discovery_page.py` is wrapped `try/except Exception` and degrades to `st.error`/`st.warning`/`st.info` — never `st.stop()` on this page (contrast with `health_page.py`'s D-01 hard block on the *Apollo Connection* card specifically, which is a different, stricter gate that does not apply to Discovery or Personalization).

### Parameterized SQL only, `?` placeholders, fresh-connection-per-call with try/finally
**Source:** `db/prospects.py` module docstring (lines 5-8) + every function body in `db/prospects.py` and `db/schema.py`
**Apply to:** `db/prospects.py`'s new `update_draft()`, `db/schema.py`'s new `_migrate_columns()`
No f-string/`.format`/`%` interpolation of any Apollo-derived, AI-generated, or user free-text value into a SQL string — this rule is explicitly called out as still in force for this phase in RESEARCH.md's Anti-Patterns section.

### `st.secrets.get(...)` read once at module top; never log/print the key
**Source:** `pages/discovery_page.py` line 48 (`apollo_key = st.secrets.get("APOLLO_API_KEY")`), `pages/health_page.py` line 28, `app.py` line 26
**Apply to:** `pages/discovery_page.py`'s new `anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")` line, `app.py`'s new boot-gate check
Read the secret once per page/module top-level, pass it down as a parameter — never re-fetch mid-handler, never include it in an f-string that could end up in a log or error message.

### Session-state result dict, initialized to `None`, keyed `"error"` + payload
**Source:** `pages/discovery_page.py` lines 50-53 (`find_result`, `enrich_result`)
**Apply to:** `pages/discovery_page.py`'s new `draft_result`
`if "draft_result" not in st.session_state: st.session_state.draft_result = None`, written as `{"error": message_or_None, ...payload}` on completion, read back for rendering in the same rerun.

## No Analog Found

None — every file in this phase's scope has at least a role-match or exact analog already established in Phase 1/2 code. The one genuinely novel piece (the LLM grounding/prompt design itself, `SYSTEM_PROMPT` in `personalization/generator.py`) has no codebase analog by definition (first AI-generation call in this repo) — use 03-RESEARCH.md Pattern 1's verbatim system-prompt text as the starting point instead, per RESEARCH.md's own "Key insight" (prompt design is the one place more engineering effort than a first instinct is justified).

## Metadata

**Analog search scope:** `apollo/`, `db/`, `pages/`, `discovery/`, `tests/`, `app.py`, `requirements.txt`, `.streamlit/secrets.toml.example` (entire repo excluding `.git`, `.planning`, `__pycache__`, `tmp/`)
**Files scanned:** 13 (all existing source + test files read in full; all ≤200 lines, single-pass reads, no re-reads)
**Pattern extraction date:** 2026-09-17
