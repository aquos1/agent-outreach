# Phase 4: Review Queue and Sequence Enrollment - Pattern Map

**Mapped:** 2026-09-17
**Files analyzed:** 12 (5 new/extended-with-new-functions, 5 extended-additive, 2 config-only)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `pages/review_queue_page.py` (new) | controller (Streamlit page) | request-response, session-state-driven | `pages/discovery_page.py` | exact |
| `apollo/client.py` (extend: `create_contacts_bulk`, `add_contacts_to_sequence`) | service (external API client) | request-response (external API) | `apollo/client.py` itself (`bulk_match_people`, `_post_with_retry`, `_chunk`) | exact |
| `db/schema.py` (extend: `template_override` table) | migration | batch (idempotent DDL, brand-new table) | `db/schema.py` itself (existing `DDL` block) | exact |
| `db/prospects.py` (extend: `get_drafted_by_path`, `mark_contact_created`, `mark_sequenced`) | model/service (CRUD) | CRUD (real sqlite) | `db/prospects.py` itself (`update_draft`) | exact |
| `db/templates_store.py` (new) | model/service (CRUD) | CRUD (real sqlite), read-with-fallback | `db/prospects.py`'s connection-lifecycle + CRUD pattern | role-match |
| `personalization/templates.py` (extend: `validate_template_fields`) | utility (pure transform) | transform | `discovery/logic.py`'s pure-function style; the file's own `assemble_email` | exact |
| `app.py` (extend: sequence-ID + mailbox secrets, new nav entry) | config (boot gate + navigation) | request-response | `app.py` itself (existing `APOLLO_API_KEY` gate + `pages` dict) | exact |
| `.streamlit/secrets.toml.example` (extend) | config | — | the file's own existing two-key convention | exact |
| `tests/test_apollo_client.py` (extend) | test | unit (mocked external call) | the file's own `test_search_people_error_codes` / `test_search_people_never_raises_on_network` | exact |
| `tests/test_prospects.py` (extend) | test | CRUD (real sqlite) | the file's own `test_update_draft_writes_status_drafted` | exact |
| `tests/test_schema.py` (extend) | test | batch (idempotency) | the file's own `test_ensure_schema_idempotent` | exact |
| `tests/test_templates.py` (new) | test | unit (pure function) | `tests/test_discovery_logic.py`'s pure-transform test style | role-match |

`tests/conftest.py` and `requirements.txt` need **no changes** this phase — see "No Analog Found / No Change Needed" below.

## Pattern Assignments

### `pages/review_queue_page.py` (controller, new)

**Analog:** `pages/discovery_page.py`

**Module docstring + imports shape** (`pages/discovery_page.py` lines 1-53):
```python
"""[purpose, what this page composes, D-refs]

NEVER log or print the api_key (T-02-04) or the ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import streamlit as st

from apollo.client import enrich_candidates, search_people
from db.prospects import dedup_filter, insert_enriched, update_draft
from discovery.logic import (...)
from personalization.generator import (...)
from personalization.templates import assemble_email

st.title("Contact Discovery")
st.caption("...")

apollo_key = st.secrets.get("APOLLO_API_KEY")
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")
```
`review_queue_page.py` mirrors this exactly: `st.title("Review Queue")`, read `apollo_key = st.secrets.get("APOLLO_API_KEY")` once at module top (never re-fetched mid-handler), plus the three new sequence-ID secrets and `APOLLO_SENDING_EMAIL_ACCOUNT_ID` read the same way. Import `get_drafted_by_path`, `mark_contact_created`, `mark_sequenced` from `db.prospects`; `create_contacts_bulk`, `add_contacts_to_sequence` from `apollo.client`; `assemble_email` from `personalization.templates`; the new `get_template`/`save_template_override` + `validate_template_fields` from `db.templates_store` / `personalization.templates`.

**Session-state result pattern** (`pages/discovery_page.py` lines 66-71):
```python
if "find_result" not in st.session_state:
    st.session_state.find_result = None  # None = not yet searched this session
if "enrich_result" not in st.session_state:
    st.session_state.enrich_result = None
if "draft_result" not in st.session_state:
    st.session_state.draft_result = None
```
Follow identically for a new `st.session_state.approve_result` (init `None`, written as `{"error": ..., "enrolled": [...], "skipped": [...]}` after an Approve action completes) so the per-contact Enrolled/Skipped outcome (D-07/D-08) survives the rerun that follows `st.dialog`'s `st.rerun()` call.

**Path selector (D-11)** — reuse the existing `PATH_OPTIONS`/`PATH_CONFIG` pattern from `discovery/logic.py` (lines 14-26) exactly as `discovery_page.py` line 73 already does:
```python
selected_path = st.selectbox(
    "Outreach path", PATH_OPTIONS, index=None, placeholder="Select an outreach path..."
)
```
The Review Queue page uses the same `PATH_OPTIONS`/`PATH_CONFIG` import (no new path-slug vocabulary) but should default to the first path (`index=0`) rather than `index=None`, since D-11 requires the queue to always be scoped to one path with an unambiguous template-editor target — landing on "no path selected" would leave the template editor with nothing to edit. Confirm the exact zero-state UX against `04-UI-SPEC.md` if one exists; otherwise `index=0` is the safe default matching "queue is scoped to one path at a time."

**Table + expander rendering (D-10)** — verbatim reusable block, `pages/discovery_page.py` lines 295-323:
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
...
for draft in draft_result["rows"]:
    with st.expander(
        f"View draft — {draft['name']} ({draft['company']})",
        icon=":material/mail:",
        expanded=False,
    ):
        full_text = f"Subject: {draft['subject']}\n\n{draft['body']}"
        st.code(full_text, language=None)
```
Per RESEARCH.md's Alternatives Considered, do **not** copy the literal `st.dataframe(table_rows)` call for the queue's checkbox column — `st.dataframe` cannot host a per-row checkbox + inline "Enrolled" badge swap (D-12) or a nested `st.expander` per row. Instead, loop prospects manually with `st.columns([...])` per row (checkbox/badge, name, company, title, then an `st.expander` for the full assembled email below the row) — same visual density as the table, same `st.expander`/`st.code` inner block verbatim from the snippet above.

**Try/except-wrapped external call, never a bare traceback** (`pages/discovery_page.py` lines 164-175):
```python
if st.button("Enrich & Continue", type="primary", icon=":material/bolt:"):
    with st.spinner("Enriching contacts with verified emails..."):
        try:
            matches, message = enrich_candidates(apollo_key, find_result["candidates"])
        except Exception:
            matches, message = (
                None,
                "Contact enrichment failed — check your internet connection and try again.",
            )
```
The Approve-flow handler (inside the `st.dialog`'s `on_confirm` callback) must follow this identical try/except-degrades-to-message shape around both `create_contacts_bulk(...)` and `add_contacts_to_sequence(...)` — never let a raised exception escape into a Streamlit traceback; degrade to the same plain-language `st.error` banner convention this page already uses (lines 140, 270).

**`st.dialog` confirmation gate (D-09)** — no existing analog in this codebase (first use of `st.dialog`); use 04-RESEARCH.md's Pattern 3 verbatim as the starting shape:
```python
@st.dialog("Confirm enrollment")
def confirm_approve(count: int, path_label: str, on_confirm):
    st.write(f"Enroll {count} contact{'s' if count != 1 else ''} into the {path_label} sequence?")
    col1, col2 = st.columns(2)
    if col1.button("Confirm", type="primary"):
        on_confirm()
        st.rerun()
    if col2.button("Cancel"):
        st.rerun()
```
This is the one deliberate exception to `discovery_page.py`'s immediate-fire button convention (D-09) — every other button on this page (template save, per-row nothing) still fires immediately; only "Approve Selected"/"Approve All" route through this dialog.

---

### `apollo/client.py` (service, extend)

**Analog:** the file's own existing `bulk_match_people`, `_post_with_retry`, `_chunk` (lines 90-248)

**Typed-tuple, status-code-branching pattern to extend** (`bulk_match_people`, lines 159-194):
```python
def bulk_match_people(api_key: str, details: list[dict]) -> tuple[list[dict] | None, str]:
    """..."""
    resp = _post_with_retry(f"{APOLLO_BASE}/people/bulk_match", api_key, {"details": details})
    if resp is None:
        return None, "Contact enrichment failed — check your internet connection and try again."
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
    data = resp.json()
    return data.get("matches", []), "OK"
```
`create_contacts_bulk(api_key, contacts, label_names) -> tuple[dict | None, str]` and `add_contacts_to_sequence(api_key, sequence_id, contact_ids, send_email_from_email_account_id) -> tuple[dict | None, str]` must follow this exact branch-per-status-code shape, same five branches (network-None / 401 / 403 / 429 / 422 / other-non-200), same message wording style ("X failed — ..." / "Apollo is rate-limiting..." / "Apollo couldn't ... — {apollo_message}"). **Critical divergence from every existing function:** on `resp.status_code == 200`, do **not** just `return resp.json(), "OK"` and call it done — per D-07/Pitfall 1 in RESEARCH.md, `add_contact_ids` can return 200 with some/all contacts in `skipped_contact_ids`. The client function itself still returns the raw parsed dict unconditionally on 200 (`return resp.json(), "OK"` — same shape as `bulk_match_people`'s `return data.get("matches", []), "OK"`); the Enrolled/Skipped **determination** happens one layer up, in `review_queue_page.py`'s page logic, not inside the client function (per RESEARCH.md's Architectural Responsibility Map — "client returns raw parsed response; page decides status").

**Reuse `_post_with_retry` and `_chunk` verbatim, no reimplementation** (lines 90-122, 197-200):
```python
def _post_with_retry(
    url: str, api_key: str, json_body: dict, timeout: int = 15, max_attempts: int = 3,
) -> requests.Response | None:
    """POST with `x-api-key` auth, retrying a 429 with exponential backoff. ..."""
    ...

def _chunk(items: list, size: int = 10):
    """Yield successive `size`-length chunks of `items` (Pattern 3, DISC-03)."""
    for i in range(0, len(items), size):
        yield items[i : i + size]
```
`create_contacts_bulk` must call `_chunk(contacts, size=100)` (its own documented 100-per-call cap, not the `size=10` default `enrich_candidates` uses) if the queue exceeds 100 selected contacts, then merge each chunk's `created_contacts`/`existing_contacts` lists before returning — mirror `enrich_candidates`'s fail-fast batching loop (lines 226-248) for this merge, not a new batching helper.

**Fail-fast batching wrapper pattern** (`enrich_candidates`, lines 226-248) — the shape to follow if `create_contacts_bulk` needs its own multi-chunk wrapper:
```python
def enrich_candidates(api_key: str, candidates: list[dict]) -> tuple[list[dict] | None, str]:
    """..."""
    all_matches: list[dict] = []
    for batch in _chunk(candidates, 10):
        details = [...]
        matches, msg = bulk_match_people(api_key, details)
        if matches is None:
            return None, msg
        all_matches.extend(matches)
    return all_matches, "OK"
```
Adapt directly for a `create_contacts_bulk` chunking wrapper if needed — same "accumulate across chunks, return first failing chunk's `(None, msg)` immediately" fail-fast shape. `add_contacts_to_sequence` does not need chunking (Apollo's `add_contact_ids` documents no per-call cap in this repo's research; a single call per approve action is sufficient at this project's <500 prospects/week scale).

**NEVER log or print the api_key** — module docstring rule (line 19) applies unchanged to both new functions; also never log/print `send_email_from_email_account_id` derived secrets beyond what's already an acceptable UI-facing value (it's a mailbox ID, not a credential, but still keep it out of any error message that gets logged verbatim).

---

### `db/schema.py` (migration, extend)

**Analog:** the file's own existing `DDL` block (lines 15-51) — this is a **brand-new table**, not a column addition to `prospect`, so the simpler `CREATE TABLE IF NOT EXISTS` path applies (no `_NEW_COLUMNS`/`_migrate_columns` entry needed).

**DDL block shape to extend** (lines 15-51, showing the pattern to append to):
```python
DDL = """
CREATE TABLE IF NOT EXISTS prospect (
    ...
);

CREATE TABLE IF NOT EXISTS email_events (
    ...
);

CREATE TABLE IF NOT EXISTS free_email_domains (
    domain TEXT PRIMARY KEY
);
INSERT OR IGNORE INTO free_email_domains (domain) VALUES
    ('gmail.com'), ('outlook.com'), ('yahoo.com'), ('hotmail.com'), ('icloud.com');
"""
```
Append a fourth `CREATE TABLE IF NOT EXISTS template_override (...)` block to this same `DDL` string, exactly matching 04-RESEARCH.md's Pattern 4:
```python
DDL += """
CREATE TABLE IF NOT EXISTS template_override (
    path        TEXT PRIMARY KEY,   -- 'club_sponsorship' | 'productthon' | 'client_sourcing'
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
```
Or (preferred, matching the existing single-string convention more closely) append this block directly inside the existing `DDL = """..."""` triple-quoted string in `db/schema.py`, rather than a separate `DDL +=` statement — check which style is cleaner against the file's actual current line count at implementation time; either is idempotent and correct. **Do not** add `path`/`subject`/`body` to `_NEW_COLUMNS` (lines 79-83) — that list is exclusively for `ALTER TABLE prospect ADD COLUMN` migrations onto the pre-existing `prospect` table; a brand-new table needs no `ALTER TABLE` step at all (RESEARCH.md Anti-Patterns: "Re-inventing a migration runner for `template_override`").

**Idempotent-boot call site** (`ensure_schema`, lines 101-119) — no change needed here beyond what `conn.executescript(DDL)` already covers, since `template_override` is folded into the same `DDL` string:
```python
def ensure_schema(db_path: str = "db/outreach.db") -> None:
    """..."""
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        conn.executescript(VIEW_DDL)
        _migrate_columns(conn)
        conn.commit()
    finally:
        conn.close()
```

---

### `db/prospects.py` (model/service, extend)

**Analog:** the file's own `update_draft()` (lines 132-158) — establishes the exact shape for advancing `prospect.status`.

**Status-transition function shape to replicate** (lines 132-158):
```python
def update_draft(
    prospect_id: str | int,
    opening_line: str,
    source: str,
    first_name: str | None = None,
    db_path: str = "db/outreach.db",
) -> None:
    """Persist a generated draft and advance the contact to status='drafted'.

    D-04: drafts must live in SQLite, not session state only, so Phase 4's
    Review Queue can query them. `apollo_person_id` (not the internal `id`
    primary key) is the match key, matching how insert_enriched stores it
    and what the caller's raw Apollo match dict carries as `id`.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prospect SET "
            "opening_line = ?, draft_source = ?, first_name = ?, "
            "status = 'drafted', updated_at = CURRENT_TIMESTAMP "
            "WHERE apollo_person_id = ?",
            (opening_line, source, first_name, prospect_id),
        )
        conn.commit()
    finally:
        conn.close()
```
`mark_contact_created(prospect_id, apollo_contact_id, db_path=...) -> None` and `mark_sequenced(prospect_id, db_path=...) -> None` must follow this identical shape: fresh `sqlite3.connect()`, `?`-placeholder `UPDATE`, `status = 'x'` plus `updated_at = CURRENT_TIMESTAMP`, `conn.commit()` in a `finally`-closed block. **Key divergence for `mark_contact_created`:** the `WHERE` clause must key on the internal `id` primary key (`WHERE id = ?`), not `apollo_person_id` — by this point in the pipeline the prospect row is uniquely addressed by its own `id` (RESEARCH.md Pattern 2's reconciliation step maps Apollo response entries back to `prospect_id` via the pre-built `email -> prospect_id` map, so the caller already has the internal `id` in hand, not the `apollo_person_id`). Example:
```python
def mark_contact_created(
    prospect_id: int, apollo_contact_id: str, db_path: str = "db/outreach.db"
) -> None:
    """Record the Apollo contact id and advance status='contact_created'."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE prospect SET apollo_contact_id = ?, "
            "status = 'contact_created', updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (apollo_contact_id, prospect_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_sequenced(prospect_id: int, db_path: str = "db/outreach.db") -> None:
    """Advance status='sequenced' after Apollo confirms enrollment (D-07)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE prospect SET status = 'sequenced', updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (prospect_id,),
        )
        conn.commit()
    finally:
        conn.close()
```
**D-08 discipline:** callers (in `review_queue_page.py`) must only invoke `mark_sequenced(prospect_id)` for prospect IDs whose mapped Apollo contact ID appears in `response["contacts"]` — never in a blanket loop over "everything submitted" (RESEARCH.md Pitfall 5). Skipped contacts get no status-mutating call at all; they simply stay `status='drafted'` because nothing touched their row.

**Read-query function** — no existing exact analog (every current `db/prospects.py` function is a write), but follow the same connection-lifecycle convention as `dedup_filter` (lines 37-80), which is this file's one existing read query:
```python
def dedup_filter(candidates: list[dict], db_path: str = "db/outreach.db") -> list[dict]:
    """..."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT apollo_person_id, dedupable_domain FROM contacted_registry")
        rows = cur.fetchall()
    finally:
        conn.close()
    ...
    return survivors
```
`get_drafted_by_path(path_slug: str, db_path: str = "db/outreach.db") -> list[dict]` should follow this same `connect → cur.execute(SELECT ...) → fetchall in try/finally → transform outside the connection block` shape: `SELECT id, name, company, company_domain, email, path, first_name, opening_line FROM prospect WHERE status = 'drafted' AND path = ?`, returning a list of dicts (not raw tuples) built from `cur.description`-driven or explicit column unpacking, matching this file's existing style of returning plain dicts/counts rather than cursor objects to callers.

---

### `db/templates_store.py` (model/service, new)

**Analog:** `db/prospects.py`'s own module-docstring + connection-lifecycle convention (lines 1-12), applied to a new file for a new table.

**Module docstring + imports shape** (`db/prospects.py` lines 1-12):
```python
"""Dedup query against contacted_registry + enriched-row insert (DEDUP-02).

Follows db/schema.py's connection lifecycle convention exactly: a fresh
sqlite3.connect() per call, wrapped in try/finally so the connection always
closes. All SQL uses `?` placeholders exclusively — never f-string/`.format`/
`%` interpolation of Apollo-derived or user free-text values into SQL
(Phase 1 Security Domain rule, T-02-01).
"""
from __future__ import annotations

import sqlite3
```
`db/templates_store.py` mirrors this docstring pattern with a template-specific opening line (persistence for D-05's per-path template overrides), same `from __future__ import annotations` / `import sqlite3` header, plus `from personalization.templates import PATH_TEMPLATES` for the seed-fallback default.

**Read-with-seed-fallback function** — 04-RESEARCH.md Pattern 4 gives the exact implementation to use, matching this file's connection-lifecycle style:
```python
def get_template(path_slug: str, db_path: str = "db/outreach.db") -> tuple[str, str]:
    """Return (subject, body) — override if one exists, else PATH_TEMPLATES default.

    Does NOT write a seed row on read (D-05: lazy fallback, not a forced
    write-on-read — avoids every path silently getting a permanent override
    row the first time anyone just views the queue)."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT subject, body FROM template_override WHERE path = ?", (path_slug,))
        row = cur.fetchone()
    finally:
        conn.close()
    if row:
        return row[0], row[1]
    default = PATH_TEMPLATES[path_slug]
    return default["subject"], default["body"]
```

**Write function** — follow `db/prospects.py`'s parameterized-write CRUD shape (`insert_enriched`, lines 83-129), but as an upsert since `path` is a `PRIMARY KEY`:
```python
def save_template_override(
    path_slug: str, subject: str, body: str, db_path: str = "db/outreach.db"
) -> None:
    """Persist an edited template as the new permanent default for path_slug (D-05).

    Caller (review_queue_page.py) must call validate_template_fields(body)
    and block this call on failure — this function does not re-validate.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO template_override (path, subject, body, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(path) DO UPDATE SET "
            "subject = excluded.subject, body = excluded.body, "
            "updated_at = CURRENT_TIMESTAMP",
            (path_slug, subject, body),
        )
        conn.commit()
    finally:
        conn.close()
```
`INSERT ... ON CONFLICT DO UPDATE` (SQLite's upsert syntax) is new to this codebase (every existing write is a plain `INSERT` or `UPDATE`, never both) — this is the one genuinely new SQL shape this phase introduces; keep it isolated to this single function rather than generalizing a helper, consistent with this codebase's "one function, one query" convention throughout `db/prospects.py`.

---

### `personalization/templates.py` (utility, extend)

**Analog:** the file's own `assemble_email()` (lines 139-153) — pure-function, typed-signature, no I/O convention.

**Pure-function shape to replicate** (lines 139-153):
```python
def assemble_email(
    path_slug: str, first_name: str, company: str, opening_line: str
) -> tuple[str, str]:
    """Merge the opening line and Apollo fields into a ready-to-send email.

    D-09: {opening_line} sits on its own standalone line directly after the
    greeting in every template's body, before the intro paragraph. Pure
    function -- no I/O, no logging.
    """
    template = PATH_TEMPLATES[path_slug]
    subject = template["subject"].format(company=company)
    body = template["body"].format(
        first_name=first_name, company=company, opening_line=opening_line
    )
    return subject, body
```
Add `validate_template_fields(body: str) -> tuple[bool, str]` in this same file, right below `assemble_email` — same "typed signature, one-line docstring, pure body, no I/O" shape, per 04-RESEARCH.md's Code Examples:
```python
import re

REQUIRED_FIELDS = {"first_name", "company", "opening_line"}


def validate_template_fields(body: str) -> tuple[bool, str]:
    """Confirm all 3 required merge fields are present before a save (D-06).

    Pure function -- no I/O. Missing/misspelled placeholders block the save
    in review_queue_page.py rather than shipping a literal '{first_name}' or
    a silently generic email to a real contact.
    """
    present = set(re.findall(r"\{(\w+)\}", body))
    missing = REQUIRED_FIELDS - present
    if missing:
        return False, f"Missing merge field(s): {', '.join(sorted(missing))}"
    return True, "OK"
```
No templating engine (Jinja2, etc.) — matches this module's existing docstring rule ("plain str.format only", line 6-7). `PATH_TEMPLATES` itself is unchanged and stays the seed/fallback default (D-05) — `db/templates_store.py` reads it, this file never reads or writes SQLite.

---

### `app.py` (config, extend)

**Analog:** the file's own existing `APOLLO_API_KEY`/`ANTHROPIC_API_KEY` presence gate (lines 27-43) + `pages` dict (lines 47-52).

**Secrets presence gate pattern to extend** (lines 27-43):
```python
apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")

if not apollo_key:
    st.error(
        "APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
        "Community Cloud secrets console (production)."
    )
    st.stop()

if not anthropic_key:
    st.error(
        "ANTHROPIC_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
        "Community Cloud secrets console (production)."
    )
    st.stop()
```
Whether the 3 new sequence-ID secrets (`APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP`, `APOLLO_SEQUENCE_ID_PRODUCTTHON`, `APOLLO_SEQUENCE_ID_CLIENT_SOURCING`) and `APOLLO_SENDING_EMAIL_ACCOUNT_ID` need a **hard boot-time gate** here (matching `APOLLO_API_KEY`'s `st.stop()` pattern) or a **page-level soft-fail** (matching `discovery_page.py`'s never-hard-stop convention) is a planning-time call, not settled by this pattern map — but structurally, if hard-gated, they follow this exact `if not X: st.error(...); st.stop()` shape, read once at module top before `st.navigation` is constructed.

**Navigation registration pattern** (lines 47-54):
```python
pages = {
    "Health": [st.Page("pages/health_page.py", title="System Health", default=True)],
    "Discovery": [st.Page("pages/discovery_page.py", title="Contact Discovery")],
    # Phase 3+ will append remaining real pages here (Personalization, Review
    # Queue, Campaign Dashboard) once the Apollo health gate passes.
}

pg = st.navigation(pages)
pg.run()
```
Add a `"Review Queue": [st.Page("pages/review_queue_page.py", title="Review Queue")]` entry to this same `pages` dict, matching the existing two-entry style exactly (a new top-level nav section, not nested under `"Discovery"`).

---

### `.streamlit/secrets.toml.example` (config, extend)

**Analog:** the file's own existing three-key convention (verbatim, full current file):
```toml
APOLLO_API_KEY = "your-master-api-key"
SENDING_DOMAIN = "outreach.yourclub.org"
ANTHROPIC_API_KEY = "your-anthropic-api-key"
```
Add four new lines matching D-02's SCREAMING_SNAKE_CASE naming exactly, same placeholder-string style:
```toml
APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP = "your-club-sponsorship-sequence-id"
APOLLO_SEQUENCE_ID_PRODUCTTHON = "your-productthon-sequence-id"
APOLLO_SEQUENCE_ID_CLIENT_SOURCING = "your-client-sourcing-sequence-id"
APOLLO_SENDING_EMAIL_ACCOUNT_ID = "your-sending-mailbox-account-id"
```

---

### `tests/test_apollo_client.py` (extend)

**Analog:** the file's own `test_search_people_error_codes` (lines 45-80+) — status-code-table testing style, plus `test_search_people_never_raises_on_network` shape referenced in `03-PATTERNS.md`.

```python
def test_search_people_error_codes(monkeypatch, mock_requests_response):
    from apollo.client import search_people

    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    monkeypatch.setattr(requests, "post", lambda *a, **k: mock_requests_response(401, {}))
    people, message = search_people("bad-key", ["director"], ["software"])
    assert people is None
    assert isinstance(message, str) and message
    ...
```
`test_create_contacts_bulk` and `test_add_contacts_to_sequence` must follow this exact table-of-status-codes shape (401/403/429/422/200), using the same `monkeypatch.setattr(requests, "post", lambda *a, **k: mock_requests_response(CODE, BODY))` + `mock_requests_response` factory fixture from `tests/conftest.py` (no changes needed there — the existing fixture already returns a generic `.status_code`/`.json()` stand-in usable for any endpoint). For the 200 case, assert the raw dict shape is returned unmodified (`{"created_contacts": [...], "existing_contacts": [...]}` / `{"contacts": [...], "skipped_contact_ids": {...}}`) — this file's job is only to prove the client returns the parsed body on 200, not to test the Enrolled/Skipped determination logic (that belongs in a page-logic or `db/prospects.py` test, per RESEARCH.md's Architectural Responsibility Map).

---

### `tests/test_prospects.py` (extend)

**Analog:** the file's own `test_update_draft_writes_status_drafted` (lines 121-179) — real-schema, seed-then-assert-via-raw-SQL style.

```python
def test_update_draft_writes_status_drafted(tmp_db_path):
    from db.schema import ensure_schema
    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched, update_draft

    rows = [...]
    insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)
    update_draft("apollo-1", "A grounded opener.", "ai", first_name="Jamie", db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT opening_line, draft_source, first_name, status FROM prospect WHERE apollo_person_id = ?", ("apollo-1",))
        opening_line, draft_source, first_name, status = cur.fetchone()
        ...
    finally:
        conn.close()

    assert status == "drafted"
```
New tests to add, each following this exact seed-via-`insert_enriched`/`update_draft` → call-function-under-test → reconnect-and-assert-via-raw-SQL shape:
- `test_get_drafted_by_path` — seed 2+ rows across two different `path` values at `status='drafted'`, assert `get_drafted_by_path("club_sponsorship")` returns only that path's rows with all expected fields present.
- `test_mark_contact_created` — seed a `status='enriched'` row, call `mark_contact_created(prospect_id, "apollo-contact-123")`, assert `status == 'contact_created'` and `apollo_contact_id == "apollo-contact-123"` via raw SELECT.
- `test_mark_sequenced_only_affects_selected` — seed 2 `status='drafted'` rows, call `mark_sequenced` on only one `prospect_id`, assert that row is `'sequenced'` and the other is untouched at `'drafted'` — directly mirrors `test_update_draft_writes_status_drafted`'s existing "untouched" assertion pattern (lines 162-179, the `untouched` tuple check).
- `test_partial_enrollment_leaves_skipped_drafted` — seed 2 `status='drafted'` rows; simulate a partial-failure batch by calling `mark_sequenced` only for the "enrolled" one; assert the "skipped" one's `status` is still `'drafted'` (D-08) — same untouched-row assertion style as above.

---

### `tests/test_schema.py` (extend)

**Analog:** the file's own `test_ensure_schema_idempotent` (lines 9-33).

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
Add `template_override` to this existing test's `IN (...)` tuple and `assert table_names == {...}` set (simplest change — this table's existence is provable in the same query as the other three tables, since it's a brand-new `CREATE TABLE IF NOT EXISTS`, not a migration). Add a new `test_template_override_roundtrip(tmp_db_path)`: call `ensure_schema`, insert a row directly via raw SQL, reconnect, assert it's readable — same shape as `test_persistence_across_reconnect` (lines 79-105). Do **not** model this on `test_column_migration_idempotent` (lines 108-159) — that test's whole point is proving `ALTER TABLE` retroactively adds columns to a *pre-existing populated table*, which does not apply here (RESEARCH.md: "this is a brand-new table, so CREATE TABLE IF NOT EXISTS alone is idempotent").

---

### `tests/test_templates.py` (new)

**Analog:** `tests/test_discovery_logic.py`'s pure-function testing style (no `tmp_db_path`, no mocking — plain input/output assertions), and `tests/test_apollo_client.py`'s deferred-import-inside-test-body convention.

```python
def test_validate_template_fields_all_present():
    from personalization.templates import validate_template_fields

    ok, message = validate_template_fields(
        "Hi {first_name}, ... {company} ... {opening_line} ..."
    )
    assert ok is True
    assert message == "OK"


def test_validate_template_fields_missing_field():
    from personalization.templates import validate_template_fields

    ok, message = validate_template_fields("Hi {first_name}, ... {company} ...")
    assert ok is False
    assert "opening_line" in message
```
Deferred import inside each test body (matching every other RED-test file in this repo's stated convention — `test_apollo_client.py` line 1-9's docstring, `test_prospects.py` line 1-6's docstring) — this file's module docstring should state the same "imports performed inside the test body so pytest --collect-only succeeds before the function exists" rationale, even though `personalization/templates.py` already exists (only the new function is RED).

---

## Shared Patterns

### Typed-tuple, never-raise external-API client function
**Source:** `apollo/client.py` (every function: `check_apollo_health`, `get_credit_balance`, `search_people`, `bulk_match_people`)
**Apply to:** `apollo/client.py`'s new `create_contacts_bulk()`, `add_contacts_to_sequence()`
Every external-service call in this codebase returns `(result_or_None, message: str)` and never lets a library exception propagate past the function boundary. On a 200, the client returns the raw parsed response dict unconditionally — **per-item outcome parsing (Enrolled vs Skipped) is explicitly NOT the client's job**; it belongs to the caller (`review_queue_page.py`), a first-time-in-this-codebase separation this phase introduces (every prior Apollo endpoint here has a single pass/fail outcome per call, not per-item mixed outcomes inside one 200).

### Reuse `_post_with_retry` / `_chunk`, never reimplement retry or batching
**Source:** `apollo/client.py` lines 90-122 (`_post_with_retry`), 197-200 (`_chunk`)
**Apply to:** both new `apollo/client.py` functions
Already implements the CLAUDE.md-mandated 429 exponential backoff (max 3 attempts) and generic chunking. `create_contacts_bulk` needs `_chunk(items, size=100)` (its own documented cap), not the `size=10` default used elsewhere.

### Idempotent, additive-only `ensure_schema()` DDL
**Source:** `db/schema.py`'s `DDL` string + `ensure_schema()` (lines 15-51, 101-119)
**Apply to:** the new `template_override` table
A brand-new table needs only `CREATE TABLE IF NOT EXISTS` inside the existing `DDL` string — no `ALTER TABLE`/`_NEW_COLUMNS` entry, since that mechanism exists solely for adding columns to the already-populated `prospect` table.

### Status-transition function: fresh connection, `?`-placeholder `UPDATE`, `status='x'` + `updated_at`
**Source:** `db/prospects.py`'s `update_draft()` (lines 132-158)
**Apply to:** `db/prospects.py`'s new `mark_contact_created()`, `mark_sequenced()`
`conn = sqlite3.connect(db_path); try: cur.execute("UPDATE prospect SET ..., status = 'x', updated_at = CURRENT_TIMESTAMP WHERE <key> = ?", (...)); conn.commit(); finally: conn.close()`. Never advance status in a blanket loop over "everything submitted" — only for IDs the Apollo response actually confirms (D-08, Pitfall 5).

### Parameterized SQL only, `?` placeholders, fresh-connection-per-call with try/finally
**Source:** `db/prospects.py` module docstring (lines 5-8) + every function body in `db/prospects.py`, `db/schema.py`
**Apply to:** `db/prospects.py`'s new functions, `db/templates_store.py`'s new module
No f-string/`.format`/`%` interpolation of any Apollo-derived, AI-generated, or user free-text value into a SQL string (Phase 1 Security Domain rule, T-02-01) — this includes the teammate-edited template `body`/`subject` text, which is free-text user input.

### `st.secrets.get(...)` read once at module top; never log/print
**Source:** `pages/discovery_page.py` line 63-64, `app.py` lines 27-29
**Apply to:** `review_queue_page.py`'s new sequence-ID + mailbox-ID secret reads, `app.py`'s boot-gate extension
Read once per page/module top-level, pass down as a parameter — never re-fetch mid-handler.

### Session-state result dict, initialized to `None`, keyed `"error"` + payload
**Source:** `pages/discovery_page.py` lines 66-71 (`find_result`, `enrich_result`, `draft_result`)
**Apply to:** `review_queue_page.py`'s new `approve_result` (and any `template_result` if the editor needs its own save-confirmation state)

### Try/except-wrapped external call, degrade to plain-language banner, never `st.stop()` on this page family
**Source:** `pages/discovery_page.py` module docstring (lines 24-30) + every button handler in the file
**Apply to:** `review_queue_page.py`'s Approve-flow handler wrapping `create_contacts_bulk`/`add_contacts_to_sequence`
Matches Discovery's "never hard-stop on a failure — inputs and buttons stay usable so the teammate can retry" convention; contrast with `health_page.py`'s stricter `st.stop()` gate, which does not apply here.

## No Analog Found / No Change Needed

- **`st.dialog` confirmation modal (D-09):** No existing codebase analog — this is the first use of `st.dialog` in the project (every prior button on `discovery_page.py` fires immediately). 04-RESEARCH.md Pattern 3 supplies the concrete starting shape (decorator-based modal, `st.columns(2)` for Confirm/Cancel, `st.rerun()` on both paths).
- **`INSERT ... ON CONFLICT DO UPDATE` upsert (`db/templates_store.py::save_template_override`):** No existing codebase analog — every prior write in `db/prospects.py` is a plain `INSERT` or `UPDATE`, never an upsert, because no prior table has a natural business-key `PRIMARY KEY` a teammate can re-save against. Keep this isolated to the one function that needs it.
- **Manual `st.columns` row-loop replacing `st.dataframe` for a table (D-10/D-12 tension):** `discovery_page.py`'s existing `st.dataframe(table_rows)` is explicitly read-only (comment: "read-only — no on_select (D-10)" from that phase). This phase's queue needs per-row interactivity `st.dataframe` cannot provide (nested expander + swappable badge/checkbox) — no analog exists; 04-RESEARCH.md's Alternatives Considered section is authoritative on the recommended manual-loop approach.
- **`tests/conftest.py`:** No changes needed — the existing `mock_requests_response` factory fixture (lines 27-45) is generic enough (`.status_code` + `.json()`) to cover both new Apollo endpoints' mocked responses without modification.
- **`requirements.txt`:** No changes needed — `streamlit==1.59.2`, `requests==2.34.2`, and stdlib `sqlite3` already cover every capability this phase requires (RESEARCH.md's Package Legitimacy Audit: "Not applicable — this phase installs no new external packages").

## Metadata

**Analog search scope:** `apollo/`, `db/`, `pages/`, `personalization/`, `discovery/`, `tests/`, `app.py`, `.streamlit/secrets.toml.example`, `requirements.txt` (entire repo excluding `.git`, `.planning`, `__pycache__`, `.venv`)
**Files read in full:** `apollo/client.py`, `db/schema.py`, `db/prospects.py`, `pages/discovery_page.py`, `personalization/templates.py`, `personalization/generator.py` (partial), `app.py`, `discovery/logic.py`, `tests/conftest.py`, `tests/test_apollo_client.py` (partial), `tests/test_prospects.py`, `tests/test_schema.py`, `.streamlit/secrets.toml.example`, `requirements.txt`
**Pattern extraction date:** 2026-09-17
