# Phase 4: Review Queue and Sequence Enrollment - Research

**Researched:** 2026-09-17
**Domain:** Apollo.io contact-creation + sequence-enrollment REST integration; Streamlit multi-widget review-queue UI; SQLite template-override persistence
**Confidence:** MEDIUM-HIGH (Apollo endpoint shapes CITED from live docs.apollo.io fetch + cross-search corroboration; Streamlit widget availability VERIFIED directly against the project's own installed package; one un-resolved secret/config gap flagged as an Open Question)

## Summary

Phase 4 wires the last mile of the pipeline: turn `status='drafted'` prospects into live Apollo sequence members. Two Apollo calls are involved — `POST /contacts/bulk_create` (create Apollo Contacts from drafted prospects, `run_dedupe: true`) and `POST /emailer_campaigns/{sequence_id}/add_contact_ids` (enroll those contacts into the path's pre-built sequence). Both were directly fetched from `docs.apollo.io` in this session (not just training knowledge) and their response shapes are more specific than CLAUDE.md/spec.MD document: `bulk_create` splits results into `created_contacts` / `existing_contacts` arrays (not just a flat 200), and `add_contact_ids` splits into a `contacts` array (successfully enrolled, full contact objects) and a `skipped_contact_ids` **object** keyed by contact ID with a specific reason-code string. This maps directly onto D-07's requirement to key off the response body, not the HTTP status.

One material gap was found that CONTEXT.md's locked decisions do not cover: `add_contact_ids` requires `send_email_from_email_account_id`, and nothing in this repo (secrets, schema, or prior phases) resolves this value today. This is flagged as an Open Question — the natural resolution, consistent with D-01/D-02's "hardcode sequence IDs in secrets.toml" pattern, is a new `APOLLO_SENDING_EMAIL_ACCOUNT_ID` secret, but that decision was never made explicitly and should be confirmed with the user or the planner before task-writing, not assumed silently.

On the Streamlit side, the project's `.venv` has a real, directly-introspectable install of the pinned `streamlit==1.59.2` (at `.venv/lib/python3.13/site-packages`) — this research queried its actual function signatures rather than trusting docs or training data. `st.dialog` (decorator-based modal, GA since 1.37), `st.data_editor` with `st.column_config.CheckboxColumn`, and `st.text_area` all exist and work as expected in 1.59.2. `st.subheader` genuinely has **no** `icon` kwarg in 1.59.2 (confirming Phase 3's prior finding) while `st.expander` and `st.button` do. A separate, unrelated environment problem was also found and is worth flagging: `.venv/bin/python3` is a broken symlink pointing at a stray system Python 3.14 with an unpinned `streamlit==1.64.0` install — any command that runs `python3` (not `python3.13`) inside this venv silently uses the wrong Streamlit version. The correct interpreter for all dev/test commands is `.venv/bin/python3.13`.

**Primary recommendation:** Implement `create_contacts_bulk()` and `add_contacts_to_sequence()` in `apollo/client.py` following the existing `(result, message)`-tuple pattern; key D-07's Enrolled/Skipped determination off `response["contacts"]` (id present → Enrolled) vs `response["skipped_contact_ids"]` (id present → Skipped + reason), not the HTTP status code. Build the template-override table as an additive migration in `db/schema.py` exactly like the `prospect` table's `_NEW_COLUMNS` pattern. Use `st.dialog` for the D-09 confirmation gate and a manual per-row `st.columns` layout (not literal `st.dataframe`) for the queue table, so each row's checkbox can be swapped for a status badge in place after enrollment (D-12). Before finalizing task breakdown, resolve the `send_email_from_email_account_id` gap explicitly.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Review queue rendering (table, expander, template editor) | Frontend (Streamlit page) | — | Single-process Streamlit app; UI and logic share a process, but rendering belongs in `pages/review_queue_page.py` |
| Template CRUD + validation (D-05/D-06) | Backend (Python module) | Database (SQLite) | Validation is pure logic (`personalization/templates.py`-adjacent), persistence is SQLite — mirrors `db/prospects.py`'s split of pure transforms vs. DB writes |
| Apollo contact creation (bulk_create) | API client (`apollo/client.py`) | — | External REST call, must follow the established never-raises tuple pattern |
| Apollo sequence enrollment (add_contact_ids) | API client (`apollo/client.py`) | — | Same as above |
| Per-contact Enrolled/Skipped determination (D-07/D-08) | Backend (page logic, post-API-call) | — | Business logic over the API response, not a UI concern and not inside the client wrapper (client returns raw parsed response; page decides status) |
| Dedup registry update after enrollment | Database (SQLite) | — | Writes to `prospect.status='sequenced'`; `contacted_registry` view auto-reflects it (no separate registry table to update) |
| Sequence ID / sending-mailbox ID resolution | Configuration (`st.secrets`) | — | D-01/D-02 locked this as static secrets, zero live-lookup dependency at enrollment time |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| streamlit | 1.59.2 (pinned, requirements.txt) | Review Queue page, `st.dialog` confirm gate, `st.text_area` template editor | Already the project's sole UI framework (CLAUDE.md); no new dependency |
| requests | 2.34.2 (pinned) | Two new Apollo POST calls | Already the project's sole HTTP client; `apollo/client.py`'s `_post_with_retry` helper is reused as-is |
| sqlite3 (stdlib) | built-in | New `template_override` table | Matches `db/schema.py`'s existing idempotent, additive-migration convention |

No new third-party packages are required for this phase — every capability (HTTP calls, SQLite, Streamlit dialogs/data editor) is already installed and pinned. **Package Legitimacy Audit is not applicable this phase** (see below).

### Supporting
None beyond the above — this phase is glue code over existing modules (`apollo/client.py`, `db/prospects.py`, `db/schema.py`, `personalization/templates.py`), not a new dependency surface.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual per-row `st.columns` + `st.checkbox` loop for the queue table | `st.data_editor` with `st.column_config.CheckboxColumn` | `data_editor` gives a "real" table with a native checkbox column (closer to D-10's literal wording) but returns a single edited DataFrame per rerun, making it awkward to (a) nest a `st.expander` "View draft" per row inside a table cell (not supported — expanders can't live inside dataframe cells) and (b) swap an individual row's checkbox for a green "Enrolled" badge in place (D-12) without fighting the editor's own state model. A manual loop keeps each row as independent widgets, which is what D-12's dynamic per-row badge and D-10's per-row expander both actually require. Recommended: manual loop, styled with `st.columns` to visually approximate a table.
| `st.dialog` for confirmation | Session-state "are you sure" banner + second button click | `st.dialog` (GA since Streamlit 1.37, confirmed present in the pinned 1.59.2 via direct introspection) is the idiomatic modal pattern and matches D-09's "explicit Confirm/Cancel" requirement more literally than a two-click banner pattern, which is easy to mis-click through accidentally on an irreversible send action. |

## Package Legitimacy Audit

Not applicable — this phase installs no new external packages. All work is written against already-pinned dependencies (`streamlit==1.59.2`, `requests==2.34.2`) and Python's stdlib (`sqlite3`). Skip the slopcheck/registry-verification protocol.

## Architecture Patterns

### System Architecture Diagram

```
[Review Queue page load]
        │
        ▼
  Query SQLite: SELECT * FROM prospect WHERE status='drafted' AND path=<selected path>
        │
        ▼
  Load template override (or PATH_TEMPLATES seed default) for <selected path>  ── template_override table
        │
        ├──► Teammate edits template text ──► validate merge fields (D-06) ──► save override + re-assemble all visible drafts (D-04)
        │
        ▼
  Render queue: per-row [checkbox|Enrolled badge] + Name/Company/Title + "View draft" expander (full assembled email)
        │
        ▼
  Teammate clicks "Approve Selected" / "Approve All"
        │
        ▼
  st.dialog confirmation ("Enroll N contacts into the [Path] sequence?") ── Cancel returns to queue unchanged
        │ Confirm
        ▼
  apollo/client.py: create_contacts_bulk(api_key, selected_prospects, path_label)  ── POST /contacts/bulk_create, run_dedupe=true
        │
        ├─ created_contacts[] ──► map prospect.id → apollo_contact_id (order is NOT guaranteed to match input order — match by email)
        └─ existing_contacts[] ──► also usable (already-Apollo contacts) — map by email the same way
        │
        ▼
  db/prospects.py: mark_contact_created(prospect_id, apollo_contact_id)  ── status → 'contact_created'
        │
        ▼
  apollo/client.py: add_contacts_to_sequence(api_key, sequence_id, contact_ids, send_email_from_email_account_id)
        │
        ├─ response["contacts"][*]["id"] present ──► Enrolled ──► mark_sequenced(prospect_id) ── status → 'sequenced'; contacted_registry auto-includes it (view filters on apollo_contact_id IS NOT NULL)
        └─ response["skipped_contact_ids"][id] = reason ──► Skipped ──► prospect.status stays 'drafted' (per D-08, stays in queue for retry) but the reason is surfaced in the UI row
        │
        ▼
  Rerun: st.rerun() ── re-query prospect table; Skipped rows reappear as drafted (checkbox), Enrolled rows have dropped from the WHERE status='drafted' query (D-12: badge visible for the remainder of the current run's in-memory result before the rerun re-queries)
```

### Recommended Project Structure
```
pages/
├── review_queue_page.py     # New: registers in app.py's st.navigation, mirrors discovery_page.py's structure
apollo/
├── client.py                 # Extended: create_contacts_bulk(), add_contacts_to_sequence()
db/
├── schema.py                  # Extended: template_override table + migration
├── prospects.py                # Extended: mark_contact_created(), mark_sequenced(), get_drafted_by_path()
├── templates_store.py          # New (suggested): load_template_override()/save_template_override(), seeded from personalization/templates.py's PATH_TEMPLATES
personalization/
├── templates.py                # Unchanged: PATH_TEMPLATES stays the seed/fallback default (D-05); assemble_email() unchanged
```

### Pattern 1: `(result, message)` tuple, never raises — extended to bulk endpoints
**What:** Every Apollo call in this codebase returns `tuple[T | None, str]` and never lets an exception escape (see `search_people`, `bulk_match_people` in `apollo/client.py`).
**When to use:** Both new functions this phase adds.
**Example:**
```python
# Source: apollo/client.py existing pattern (bulk_match_people), extended
def create_contacts_bulk(
    api_key: str, contacts: list[dict], label_names: list[str]
) -> tuple[dict | None, str]:
    """POST /contacts/bulk_create with run_dedupe=true. Returns the raw
    {"created_contacts": [...], "existing_contacts": [...]} dict on 200,
    or (None, message) on any failure. Caller reconciles prospect rows by
    matching email, NOT by list position (Apollo does not guarantee
    input-order == output-order across the two result arrays)."""
    payload = {
        "contacts": contacts,          # up to 100 — chunk with existing _chunk() if queue > 100
        "run_dedupe": True,
        "append_label_names": label_names,
    }
    resp = _post_with_retry(f"{APOLLO_BASE}/contacts/bulk_create", api_key, payload)
    if resp is None:
        return None, "Contact creation failed — check your internet connection and try again."
    if resp.status_code == 401:
        return None, "Apollo connection failed — check that APOLLO_API_KEY is set correctly."
    if resp.status_code == 403:
        return None, "Apollo connection failed — this key is not a Master API key."
    if resp.status_code == 429:
        return None, "Apollo is rate-limiting contact creation — please wait a moment and try again."
    if resp.status_code == 422:
        apollo_message = resp.json().get("message", "invalid request")
        return None, f"Apollo couldn't create these contacts — {apollo_message}"
    if resp.status_code != 200:
        return None, f"Contact creation failed — unexpected status {resp.status_code}."
    return resp.json(), "OK"
```

### Pattern 2: Reconciling bulk responses by email, not list position
**What:** `bulk_create`'s `created_contacts`/`existing_contacts` arrays and `add_contact_ids`'s `contacts`/`skipped_contact_ids` are not documented as preserving input order, and `skipped_contact_ids` is keyed by **contact ID** (an Apollo ID that only exists after the create step), not by any local prospect key.
**When to use:** Any code that maps an Apollo response entry back to a local `prospect.id`.
**Example:**
```python
# Build an email -> prospect_id map BEFORE the bulk_create call, since email is
# the one identifier guaranteed present on both the outbound payload and every
# inbound created_contacts/existing_contacts entry.
email_to_prospect_id = {p["email"]: p["id"] for p in selected_prospects}

data, msg = create_contacts_bulk(api_key, contacts_payload, label_names=[path_slug])
if data is None:
    ...  # surface msg, stop
all_created = data.get("created_contacts", []) + data.get("existing_contacts", [])
for contact in all_created:
    prospect_id = email_to_prospect_id.get(contact.get("email"))
    if prospect_id is not None:
        mark_contact_created(prospect_id, contact["id"])
```

### Pattern 3: `st.dialog` confirmation gate (D-09)
**What:** A decorator-based modal confirmed present and GA in the pinned Streamlit 1.59.2 (verified via direct `inspect.signature` against `.venv/lib/python3.13/site-packages/streamlit`).
**When to use:** Before firing "Approve Selected"/"Approve All" — irreversible, sends real emails.
**Example:**
```python
# Source: verified signature — st.dialog(title, *, width='small', dismissible=True, icon=None, on_dismiss='ignore')
@st.dialog("Confirm enrollment")
def confirm_approve(count: int, path_label: str, on_confirm):
    st.write(f"Enroll {count} contact{'s' if count != 1 else ''} into the {path_label} sequence?")
    col1, col2 = st.columns(2)
    if col1.button("Confirm", type="primary"):
        on_confirm()
        st.rerun()
    if col2.button("Cancel"):
        st.rerun()

if st.button("Approve Selected", type="primary"):
    confirm_approve(len(selected_ids), path_label, lambda: run_approval(selected_ids))
```

### Pattern 4: Additive SQLite migration for `template_override` (D-05)
**What:** Follows `db/schema.py`'s existing `DDL` (CREATE TABLE IF NOT EXISTS) + `_NEW_COLUMNS`/`_migrate_columns` idempotent-boot convention exactly — no new migration mechanism invented.
**When to use:** Adding the new template persistence table.
**Example:**
```python
# Source: pattern lifted directly from db/schema.py's existing DDL block
DDL += """
CREATE TABLE IF NOT EXISTS template_override (
    path        TEXT PRIMARY KEY,   -- 'club_sponsorship' | 'productthon' | 'client_sourcing'
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
# No ALTER TABLE needed — this is a brand-new table, so CREATE TABLE IF NOT EXISTS
# alone is idempotent (Pitfall 1 in 01-RESEARCH.md only applies to ALTER TABLE on
# an already-populated table, not a new table).
```
Read-with-seed-fallback logic (D-05: "`PATH_TEMPLATES` becomes the fallback/seed default, not necessarily the sole source of truth once a teammate has edited a path"):
```python
def get_template(path_slug: str, db_path: str = "db/outreach.db") -> tuple[str, str]:
    """Return (subject, body) — override if one exists, else PATH_TEMPLATES default.
    Does NOT write a seed row on read (D-05 says "seeded ... on first read if no
    override exists yet" — interpret conservatively as lazy fallback, not a forced
    write-on-read, to avoid every path silently getting a permanent override row
    the first time anyone just VIEWS the queue)."""
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

### Anti-Patterns to Avoid
- **Treating HTTP 200 as enrollment confirmation:** `add_contact_ids` can return 200 with some/all contacts in `skipped_contact_ids`. D-07 explicitly requires parsing the body. Never short-circuit on `resp.status_code == 200` alone for this endpoint.
- **Matching bulk response entries by list index:** Apollo does not document index-preserving order for `bulk_create` or `add_contact_ids`. Match by `email` (bulk_create) or the Apollo contact `id` you passed in (add_contact_ids skipped map is keyed by the contact_id you sent).
- **Re-inventing a migration runner for `template_override`:** it's a brand-new table — plain `CREATE TABLE IF NOT EXISTS` is sufficient; do not add it to `_NEW_COLUMNS` (that list is for ALTER TABLE additions to the existing `prospect` table only).
- **Using `st.dataframe`'s built-in row-selection (`on_select`) for the checkbox column:** `discovery_page.py`'s existing `st.dataframe(table_rows)` call is explicitly read-only (comment: "read-only — no on_select (D-10)"). Reusing `on_select` here would be a new pattern for this codebase and doesn't cleanly support the per-row expander + dynamic badge-replaces-checkbox requirement (D-12) — see Alternatives Considered above.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry/backoff on 429 for the two new endpoints | A second retry loop | `apollo/client.py`'s existing `_post_with_retry` helper | Already implements the CLAUDE.md-mandated exponential backoff, max 3 attempts; reuse verbatim |
| Batching >10/>100 items | A new chunking helper | `apollo/client.py`'s existing `_chunk(items, size)` | Generic, already used by `enrich_candidates`; `bulk_create` needs `size=100` (its own documented cap), not the `size=10` default used for `bulk_match` |
| Merge-field presence validation (D-06) | A regex scanner from scratch | `str.format_map` with a permissive dict, or a simple `{"{first_name}", "{company}", "{opening_line}"} <= set(re.findall(r"\{(\w+)\}", template_body))` set-containment check | The three merge fields are a fixed, known set — no templating engine needed (matches `personalization/templates.py`'s existing "plain str.format only" convention) |
| Confirmation modal | A custom session-state two-click pattern | `st.dialog` (native, GA in 1.37+, confirmed present in pinned 1.59.2) | Already built into the framework; hand-rolling a modal with session-state flags is exactly the kind of custom UI machinery Streamlit exists to avoid |

**Key insight:** Every "don't hand-roll" item in this phase already has a first-class answer either inside `apollo/client.py` (retry/chunking) or inside Streamlit itself (`st.dialog`) — the phase should extend existing modules, not create parallel infrastructure.

## Common Pitfalls

### Pitfall 1: Treating a 200 from `add_contact_ids` as universal success
**What goes wrong:** Code marks every contact "Enrolled" because the HTTP call succeeded, silently losing the fact that some contacts were skipped (e.g., already active in another campaign).
**Why it happens:** Every other Apollo call in this codebase (search, bulk_match) is single-status pass/fail — this is the first endpoint in the project with per-item mixed outcomes inside a 200.
**How to avoid:** Always iterate `response["contacts"]` (enrolled) and `response["skipped_contact_ids"]` (skipped, dict of id→reason) explicitly; never infer status from the HTTP code alone (D-07).
**Warning signs:** Tests that only assert on `resp.status_code == 200` without asserting per-contact outcome are insufficient for this endpoint.

### Pitfall 2: Confusing override query-param flags with response reason codes
**What goes wrong:** spec.MD documents override *flags* you can pass to force enrollment through certain conditions (e.g., `sequence_active_in_other_campaigns: true` as a request param), named with a `sequence_` prefix. The live response's skip *reason codes* use a similar-but-different `contacts_` prefix (e.g., `contacts_active_in_other_campaigns`, `contacts_finished_in_other_campaigns`). These are two different vocabularies for related concepts — conflating them (e.g., checking `reason == "sequence_active_in_other_campaigns"` against the actual response) will silently fail to match.
**Why it happens:** spec.MD (an internal planning doc, not Apollo's own docs) uses the flag names as shorthand for the concepts; the live API's actual JSON keys differ.
**How to avoid:** Do not hardcode string matching against spec.MD's flag names when parsing `skipped_contact_ids` values. Confirm the exact reason-code strings via a live human-verify call during implementation (this repo's established convention — see the "CONFIRMED (0X-0Y live human-verify...)" comments throughout `apollo/client.py`/`db/prospects.py`) before shipping the reason-display logic. This finding is CITED (single live `docs.apollo.io` fetch), not yet independently re-verified against a real API response in this session — treat the exact reason-code string list as MEDIUM confidence pending that live check.

### Pitfall 3: Assuming `send_email_from_email_account_id` is already available
**What goes wrong:** Implementation reaches the `add_contacts_to_sequence` call and has no value to pass for the required `send_email_from_email_account_id` query param — nothing in `.streamlit/secrets.toml`, `secrets.toml.example`, or any prior phase resolves this ID.
**Why it happens:** CONTEXT.md's D-01/D-02 solved sequence-ID resolution but never mentioned the sending-mailbox ID, which is a separate, also-required parameter on the same endpoint (spec.MD §3.7, confirmed live).
**How to avoid:** Resolve this explicitly before planning tasks — see Open Questions below. The consistent-with-D-01 answer is very likely a new static secret (e.g. `APOLLO_SENDING_EMAIL_ACCOUNT_ID`), resolved once via `GET /api/v1/email_accounts` (CITED, docs.apollo.io) and hardcoded, mirroring the sequence-ID pattern's "zero live API dependency at enrollment time" rationale — but this must be confirmed with the user/planner, not silently assumed.
**Warning signs:** A 422 from Apollo with a message about a missing/invalid `send_email_from_email_account_id`.

### Pitfall 4: `.venv/bin/python3` silently running the wrong Streamlit version
**What goes wrong:** Running `.venv/bin/python3 -c "..."` (or any script invoked via the bare `python3` symlink) imports `streamlit==1.64.0` from a stray `python3.14` site-packages directory instead of the pinned `1.59.2` in `python3.13`'s site-packages — `pip show`/`pip freeze` (which read `python3.13`'s metadata, matching `pyvenv.cfg`) will report `1.59.2` while the code actually executed is `1.64.0`. This was discovered live in this research session by introspecting both paths directly.
**Why it happens:** `.venv/bin/python3` is a symlink to `python3.14` (a Homebrew install), not to the venv's own `python3.13` interpreter that `pyvenv.cfg` declares as `home`. A `python3.14 -m pip install streamlit` (or similar) run at some point wrote packages into `.venv/lib/python3.14/site-packages`, which is picked up whenever something invokes `.venv/bin/python3` or an activated shell's bare `python3` resolves to that symlink.
**How to avoid:** Always invoke `.venv/bin/python3.13` (or activate the venv and confirm `python3 --version`/`python3 -c "import streamlit; print(streamlit.__file__)"` resolves into the `python3.13` site-packages) for any dev/test/verification command in this phase's plan. `pytest` invoked via `.venv/bin/python3.13 -m pytest` correctly picks up the true pinned `1.59.2`.
**Warning signs:** A widget/kwarg that "works" locally but isn't actually present in the pinned `1.59.2` (the inverse of Phase 3's `icon`-on-`st.subheader` finding) — always verify against `python3.13`'s site-packages specifically, not whatever `python3` happens to resolve to.

### Pitfall 5: Skipped contacts silently disappearing from the queue
**What goes wrong:** After a partial-failure batch, code advances every submitted prospect past `status='drafted'` regardless of actual outcome, so a Skipped contact (which D-08 requires to remain re-tryable) vanishes from the `WHERE status='drafted'` queue query.
**Why it happens:** Easy to write `mark_sequenced()` in a blanket loop over "everything submitted" rather than conditionally over "everything the response actually confirmed enrolled."
**How to avoid:** Only call `mark_sequenced(prospect_id)` for prospect IDs whose mapped Apollo contact ID appears in `response["contacts"]`; leave every other submitted prospect's `status` untouched at `'drafted'` (D-08).

## Code Examples

### Full assembled-email preview matching Phase 3's expander convention (D-10)
```python
# Source: pages/discovery_page.py, lines 312-323 (existing, verbatim pattern to reuse)
for draft in draft_result["rows"]:
    with st.expander(
        f"View draft — {draft['name']} ({draft['company']})",
        icon=":material/mail:",
        expanded=False,
    ):
        full_text = f"Subject: {draft['subject']}\n\n{draft['body']}"
        st.code(full_text, language=None)
```

### Merge-field validation before save (D-06)
```python
import re

REQUIRED_FIELDS = {"first_name", "company", "opening_line"}

def validate_template_fields(body: str) -> tuple[bool, str]:
    present = set(re.findall(r"\{(\w+)\}", body))
    missing = REQUIRED_FIELDS - present
    if missing:
        return False, f"Missing merge field(s): {', '.join(sorted(missing))}"
    return True, "OK"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `st.experimental_dialog` | `st.dialog` | Streamlit 1.37.0 (July 2024) | The stable, non-experimental name is what exists in the pinned 1.59.2 — do not reference the old experimental name in any generated code |

**Deprecated/outdated:** None else relevant — the pinned Streamlit (1.59.2) and `requests` (2.34.2) are both well past any deprecation boundary affecting this phase's needed widgets/calls.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `add_contact_ids`'s exact `skipped_contact_ids` reason-code strings (`contacts_active_in_other_campaigns`, etc.) are accurate and stable | Architecture Patterns Pattern 1, Pitfall 2 | If Apollo's actual live response uses different strings, D-07's "Skipped with reason" display would show a raw/garbled reason or fail to categorize known cases distinctly — low severity (the raw string can still be surfaced verbatim as a fallback) but should be live-verified per this repo's established human-verify convention |
| A2 | `bulk_create`'s `created_contacts`/`existing_contacts` split and per-contact `email` field are accurate | Architecture Patterns Pattern 1/2 | If the real shape differs, the email-based reconciliation in Pattern 2 would fail to map contacts back to prospects — should be live-verified the same way Phase 2 verified `bulk_match`'s shape (02-03 human-verify) |
| A3 | The sending-mailbox ID should be resolved as a new static secret (`APOLLO_SENDING_EMAIL_ACCOUNT_ID`), mirroring D-01/D-02 | Open Questions / Pitfall 3 | This is a recommendation, not a locked decision — if the user/planner instead wants a live `GET /email_accounts` lookup at enrollment time, the architecture (and the "no live dependency at enrollment" rationale from D-01) would need revisiting |
| A4 | D-05's "seeded... on first read if no override exists yet" should be implemented as a lazy fallback-on-read (no write), not a forced write-on-first-view | Architecture Patterns Pattern 4 | If the intended behavior was actually "write a permanent override row the first time any teammate views the page," every path would silently get a DB row even without an edit — low risk either way since `PATH_TEMPLATES` stays correct as the code-level source, but worth a one-line confirmation during planning |

## Open Questions

1. **How is `send_email_from_email_account_id` resolved?**
   - What we know: This is a required query param on `add_contact_ids` (CITED, docs.apollo.io + spec.MD §3.7). `GET /api/v1/email_accounts` (CITED, docs.apollo.io) returns each linked mailbox's `id`, `active`, and `default` flags — this is how the value would be obtained.
   - What's unclear: CONTEXT.md's D-01/D-02 only decided sequence-ID resolution; no decision exists for the mailbox-account ID. `.streamlit/secrets.toml.example` has no field for it today.
   - Recommendation: Planner should surface this to the user (or make an explicit Claude's-discretion call, since CONTEXT.md's "Claude's Discretion: None" only covers the four areas actually discussed) before writing enrollment tasks. The lowest-risk default, consistent with D-01's rationale, is a new `APOLLO_SENDING_EMAIL_ACCOUNT_ID` secret resolved once manually (via `GET /email_accounts`) rather than a live per-enrollment lookup.

2. **Exact `skipped_contact_ids` reason-code vocabulary and `bulk_create` response field names — live-verify before shipping.**
   - What we know: CITED from a direct `docs.apollo.io` fetch in this session, cross-corroborated by a second independent search for general shape (arrays split created/existing, skipped as id→reason map) but not for the literal reason-code strings.
   - What's unclear: Whether Apollo's actual live response for this team's account/plan matches the docs exactly (docs can lag behind or have copy errors, same category of risk that Phase 2's `organization_name` vs `organization.name` mismatch fell into).
   - Recommendation: Planner should include a live human-verify checkpoint task (same pattern as 02-03/03-xx) for both new endpoints before the phase's UI logic is finalized, per this repo's established convention of confirming Apollo response shapes against a real call rather than trusting docs alone.

3. **Does the Apollo plan on this team's account support `add_contact_ids`'s override flags (`sequence_active_in_other_campaigns`, etc.) or are they gated by plan tier?**
   - What we know: Nothing plan-tier-specific found; STATE.md's existing "Blockers/Concerns" already flags "Apollo plan tier and rate limits — check /api/v1/usage before assuming documented limits apply" as an open project-level concern.
   - What's unclear: Whether this phase needs to expose any of these override flags in the UI (CONTEXT.md's decisions don't mention them) — D-08 only requires surfacing the reason when a contact is skipped, not necessarily offering a UI toggle to force past it in v1.
   - Recommendation: Treat override flags as out of scope for v1 UI (matches REVIEW-01/CONF-01 deferral spirit) — just surface the reason string; don't add checkboxes to force-enroll skipped contacts unless the user asks.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| streamlit (pinned) | Review Queue UI (`st.dialog`, `st.text_area`, `st.checkbox`) | ✓ (verified via direct introspection of `.venv/lib/python3.13/site-packages`) | 1.59.2 | — |
| requests (pinned) | New Apollo bulk-create/enrollment calls | ✓ | 2.34.2 | — |
| sqlite3 (stdlib) | `template_override` table | ✓ | Python 3.13 stdlib | — |
| Correct venv interpreter (`python3.13`, not the bare `python3` symlink) | All dev/test commands for this phase | ✗ for `.venv/bin/python3` (resolves to a stray 1.64.0 install) — ✓ for `.venv/bin/python3.13` | — | Always invoke `.venv/bin/python3.13` explicitly (see Pitfall 4) |
| Live Apollo account: sending mailbox ID | Sequence enrollment (`send_email_from_email_account_id`) | Unknown — not present anywhere in this repo | — | Must be resolved before enrollment tasks run (see Open Question 1) |

**Missing dependencies with no fallback:**
- Sending mailbox ID (`send_email_from_email_account_id`) — blocks the `add_contacts_to_sequence` call entirely until resolved (Open Question 1).

**Missing dependencies with fallback:**
- `.venv/bin/python3` resolving to the wrong Streamlit version — fallback is simply always using `.venv/bin/python3.13` in commands.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (installed in `.venv`, confirmed via `.venv/bin/python3.13 -m pytest --version`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `addopts = "-q"`) |
| Quick run command | `.venv/bin/python3.13 -m pytest tests/test_apollo_client.py tests/test_prospects.py tests/test_schema.py -q` |
| Full suite command | `.venv/bin/python3.13 -m pytest -q` (equivalently `pytest -q` once the venv is correctly activated — see Pitfall 4 for why the interpreter matters) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUEUE-01 | Every `status='drafted'` prospect appears in the queue query before enrollment | unit | `pytest tests/test_prospects.py::test_get_drafted_by_path -x` | ❌ Wave 0 |
| QUEUE-02 | Queue query/display includes name, company, role, full assembled email | unit | `pytest tests/test_prospects.py::test_get_drafted_by_path -x` (assert returned dict has all fields; UI rendering itself is not unit-testable, covered by manual/human-verify) | ❌ Wave 0 |
| QUEUE-03 | Unchecked/unselected contacts remain `status='drafted'` after an Approve action on a different subset | unit | `pytest tests/test_prospects.py::test_mark_sequenced_only_affects_selected -x` | ❌ Wave 0 |
| QUEUE-04 | `create_contacts_bulk()` sends `run_dedupe: true` and correctly parses `created_contacts`/`existing_contacts`; `add_contacts_to_sequence()` correctly splits `contacts`/`skipped_contact_ids` | unit | `pytest tests/test_apollo_client.py::test_create_contacts_bulk tests/test_apollo_client.py::test_add_contacts_to_sequence -x` | ❌ Wave 0 |
| D-05/D-06 (template override) | Template save validates merge fields; override persists and is read back over `PATH_TEMPLATES` default | unit | `pytest tests/test_schema.py::test_template_override_roundtrip tests/test_templates.py::test_validate_template_fields -x` | ❌ Wave 0 |
| D-07/D-08 (partial-failure handling) | A batch with mixed enrolled/skipped contacts marks only enrolled ones `sequenced`, leaves skipped ones `drafted` | unit | `pytest tests/test_prospects.py::test_partial_enrollment_leaves_skipped_drafted -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Quick run command above.
- **Per wave merge:** Full suite command.
- **Phase gate:** Full suite green before `/gsd:verify-work`, plus a manual human-verify checkpoint confirming the live Apollo response shapes for `bulk_create`/`add_contact_ids` (per Open Question 2 — this repo's established convention for every new Apollo endpoint, e.g. 02-03/03-xx's live-call confirmations) and confirming `send_email_from_email_account_id` actually resolves to a working, active mailbox.

### Wave 0 Gaps
- [ ] `tests/test_apollo_client.py` additions — `test_create_contacts_bulk`, `test_add_contacts_to_sequence` (mock `requests.post` per existing `mock_requests_response` fixture convention)
- [ ] `tests/test_prospects.py` additions — `test_get_drafted_by_path`, `test_mark_contact_created`, `test_mark_sequenced_only_affects_selected`, `test_partial_enrollment_leaves_skipped_drafted`
- [ ] `tests/test_schema.py` addition — `test_template_override_roundtrip` (idempotent `CREATE TABLE IF NOT EXISTS`, plus seed-fallback read)
- [ ] New `tests/test_templates.py` (or extend `tests/test_personalization.py`) — `test_validate_template_fields` for D-06
- [ ] No new framework install needed — pytest already present in `.venv`

## Security Domain

`security_enforcement` is `false` in `.planning/config.json` — this section is omitted per the project's own config (absent-means-enabled rule does not apply; it is explicitly `false`).

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sequence ID resolution**
- D-01: The 3 Apollo sequence IDs (one per path) are hardcoded in `.streamlit/secrets.toml`, the same permanent config file already holding `APOLLO_API_KEY`, `ANTHROPIC_API_KEY`, and `SENDING_DOMAIN` — not looked up dynamically via `emailer_campaigns/search`. Rationale: zero live API dependency at enrollment time, and it won't silently break if a sequence gets renamed in Apollo.
- D-02: Secrets key naming: `APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP`, `APOLLO_SEQUENCE_ID_PRODUCTTHON`, `APOLLO_SEQUENCE_ID_CLIENT_SOURCING` — SCREAMING_SNAKE_CASE matching the existing secrets convention.

**Bulk template editor (scope addition)**
- D-03: The template editor lives on the new Review Queue page, above the list of drafts — not on the existing Discovery page's "Email Drafts" section (that stays Phase 3's read-only preview).
- D-04: Saving an edited template immediately re-assembles (`assemble_email()`) every currently-queued contact on that path with the new template text + their existing AI-generated opening line. No stale previews — what the teammate sees always matches what will send.
- D-05: Edited templates persist permanently as the new default for that path, surviving app restarts — this requires a small new persistence layer (e.g. a `templates` table in SQLite), seeded from `personalization/templates.py`'s current `PATH_TEMPLATES` dict on first read if no override exists yet. `PATH_TEMPLATES` becomes the fallback/seed default, not necessarily the sole source of truth once a teammate has edited a path.
- D-06: Before an edited template can be saved, the app validates that all 3 merge fields (`{first_name}`, `{company}`, `{opening_line}`) are still present and correctly spelled. If one is missing/broken, block the save and show a clear warning — prevents a literal `{first_name}` (or a silently generic email) shipping to a real contact.

**Approve flow & confirmation**
- D-07: "Confirmed enrolled" (success criterion 3) means checking Apollo's `add_contact_ids` response body per contact, not just the HTTP status. Only contact IDs Apollo's response confirms as enrolled are marked `Enrolled`; every other contact in the batch is marked `Skipped` with Apollo's stated reason (spec.MD §3.7 documents `sequence_active_in_other_campaigns` / `sequence_finished_in_other_campaigns` as known 422 causes to surface).
- D-08: Partial failure within a batch does not block the rest — the batch proceeds, and afterward each contact's actual outcome (Enrolled / Skipped + reason) is shown in the queue. Skipped contacts remain in the queue at `status='drafted'` per QUEUE-03 (not discarded), available for a later retry.
- D-09: Both "Approve Selected" and "Approve All" require a confirmation dialog before firing — "Enroll N contacts into the [Path] sequence?" with explicit Confirm/Cancel — since this is an irreversible action that sends real emails to real companies. This is a deliberate exception to the existing Discovery page's immediate-fire button pattern (Find Contacts / Enrich & Continue), justified by consequence and irreversibility.

**Queue page layout**
- D-10: Reuse Phase 3's Discovery-page pattern: `st.dataframe`-style table (Name/Company/Title, checkbox column) with a collapsed "View draft" expander per row showing the full assembled email — not a card-list layout. Keeps the app visually consistent and reuses a proven pattern. *(See Architecture Patterns "Alternatives Considered" above — literal `st.dataframe` with a native checkbox column conflicts with D-12's per-row badge requirement; recommend a manual `st.columns` row loop that visually approximates the same table.)*
- D-11: The queue is scoped to one path at a time via a selector (dropdown/tabs), not all paths mixed in one list — this keeps the template editor (D-03) unambiguous: it always edits the template for whichever path's contacts are currently visible.
- D-12: After Approve fires, a successfully-enrolled row stays visible with a green "Enrolled" status badge in place of its checkbox — gives in-the-moment per-contact confirmation. The row naturally drops out of the queue on the next page load/rerun since it's no longer `status='drafted'`.

### Claude's Discretion
None — all four discussed areas (Sequence ID resolution, Bulk template editor, Approve flow & confirmation, Queue page layout) reached explicit user decisions; no "you decide" items remain open. (Note: the sending-mailbox-ID gap identified in this research — Open Question 1 — was never part of the discussed areas and is therefore not covered by this "None" statement; it needs a fresh decision.)

### Deferred Ideas (OUT OF SCOPE)
None new — discussion stayed within phase scope (the one scope addition, bulk template editing, was deliberately folded in per the Folded Todos entry, not deferred). v2-deferred items from REQUIREMENTS.md remain out of scope: REVIEW-01 (per-contact edit/skip), SEND-01 (auto-send toggle), CONF-01 (fuller per-contact confirmation detail beyond Enrolled/Skipped+reason).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUEUE-01 | All generated email drafts are placed in a review queue before any email is sent | `get_drafted_by_path()` query pattern (Architecture Patterns); reuses `prospect.status='drafted'` rows written by Phase 3's `update_draft()` |
| QUEUE-02 | User sees all drafts in the queue (contact name, company, role, full email preview) | D-10 table+expander pattern, reusing `discovery_page.py`'s exact expander convention (Code Examples) |
| QUEUE-03 | Checkbox per contact (default checked); Approve Selected/All enroll checked contacts; unchecked stay `drafted` | Manual per-row `st.columns`+`st.checkbox` layout (Alternatives Considered); D-08's "leave unselected/skipped at `drafted`" logic (Pitfall 5) |
| QUEUE-04 | Sequence enrollment creates Apollo contacts (`run_dedupe: true`) and enrolls them in the path's sequence | `create_contacts_bulk()` / `add_contacts_to_sequence()` (Architecture Patterns Pattern 1), CITED response shapes from live `docs.apollo.io` fetch |

## Sources

### Primary (HIGH confidence)
- `.venv/lib/python3.13/site-packages/streamlit` (direct `inspect.signature` introspection of the project's actual pinned `streamlit==1.59.2` install) — `st.dialog`, `st.data_editor`, `st.column_config.CheckboxColumn`, `st.text_area`, `st.subheader`, `st.expander`, `st.checkbox`, `st.button`, `st.rerun`
- `/Users/yashpersonal/outreach-agent/apollo/client.py`, `db/schema.py`, `db/prospects.py`, `personalization/templates.py`, `pages/discovery_page.py`, `app.py`, `discovery/logic.py` — existing codebase conventions this phase must extend
- `/Users/yashpersonal/outreach-agent/spec.MD` §3.4, §3.7 — Apollo contact-creation and sequence-enrollment integration spec (project-authored, treated as authoritative project doc)
- `/Users/yashpersonal/outreach-agent/.planning/phases/04-review-queue-and-sequence-enrollment/04-CONTEXT.md` — all 12 locked decisions

### Secondary (MEDIUM confidence)
- https://docs.apollo.io/reference/bulk-create-contacts (WebFetch, live) — `contacts`/`run_dedupe`/`append_label_names` request shape, `created_contacts`/`existing_contacts` response shape, 100-per-call cap — cross-corroborated by a second independent WebSearch for the general created/existing split
- https://docs.apollo.io/reference/add-contacts-to-sequence (WebFetch, live) — full query-param list, `contacts`/`skipped_contact_ids` response shape and reason-code strings — general shape cross-corroborated by WebSearch; exact reason-code strings NOT independently re-confirmed by a second source (flagged in Assumptions Log A1, Pitfall 2, Open Question 2)
- https://docs.apollo.io/reference/get-a-list-of-email-accounts (WebSearch summary) — resolves `send_email_from_email_account_id` via `GET /api/v1/email_accounts`
- https://discuss.streamlit.io/t/version-1-37-0/75769 (WebSearch) — `st.dialog` GA date, cross-confirmed by direct introspection above

### Tertiary (LOW confidence)
- https://docs.apollo.io/reference/rate-limits (WebFetch, live) — could not confirm endpoint-specific numeric limits for `bulk_create`/`add_contact_ids`/`contacts`; falls back to CLAUDE.md's own MEDIUM-confidence figure (600 req/hour, itself sourced from a prior WebSearch, not a live per-endpoint confirmation) — recommend checking `/usage_stats/api_usage_stats` live during implementation, per STATE.md's existing open concern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; existing pinned versions directly verified against the project's own `.venv`
- Architecture: MEDIUM-HIGH — request/response shapes for both new Apollo endpoints are CITED from a direct live-docs fetch this session (more specific than any prior document in this repo), but not yet confirmed against this team's actual live Apollo account/plan (recommend a human-verify checkpoint, consistent with this repo's established pattern for every prior new endpoint)
- Pitfalls: HIGH for the Streamlit/venv-interpreter pitfall (directly reproduced and verified in this session); MEDIUM for the Apollo response-shape pitfalls (CITED, not live-account-verified)

**Research date:** 2026-09-17
**Valid until:** 2026-10-17 (30 days — Apollo API and Streamlit are both moderately stable; the `send_email_from_email_account_id` gap and exact reason-code strings should be re-verified at implementation time regardless of this date, per the human-verify checkpoints noted above)
