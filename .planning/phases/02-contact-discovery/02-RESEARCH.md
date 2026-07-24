# Phase 2: Contact Discovery - Research

**Researched:** 2026-07-24
**Domain:** Apollo.io People Search + Bulk Enrichment REST integration, Streamlit two-stage session-state flow, SQLite dedup querying
**Confidence:** MEDIUM (Apollo request param names and rate-limit tiers are HIGH; exact Apollo response field names are MEDIUM — official docs' interactive schema viewer could not be executed non-interactively, see Open Questions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Path → Apollo filter translation**
- D-01: All 3 paths use identical search logic — free text (company type + role) is the ONLY thing that drives Apollo search filters. Path selection changes ONLY the downstream Apollo sequence ID and email template, never the search filters themselves. No per-path baked-in filters (company size, location, etc.).
- D-02: Free-text "target role" maps directly to Apollo's `person_titles` keyword field (literal title-keyword search) — not an AI-inferred seniority tag.
- D-03: Free-text "company type / industry" maps directly to Apollo's organization keyword-tag field (literal keyword search) — not a structured industry-taxonomy lookup.
- D-04: Free text is passed straight through to Apollo with no AI normalization step. Rationale discussed explicitly: Apollo search is 0 credits regardless of query quality, the 50-contact cap bounds spend either way, and DISC-04's cost-preview gate already prevents blind commitment — so normalization would only be a match-relevance lever, not a cost-savings one. Revisit only if relevance turns out to be a real problem once the app is in use.

**Credit cost gate (DISC-04)**
- D-05 (IMPORTANT, changes DISC-04's literal wording): Apollo has no API endpoint that returns credit balance (confirmed via a live authenticated call to `usage_stats/api_usage_stats` during Phase 1's checkpoint — that endpoint returns only per-endpoint rate-limit consumption; Apollo's own docs confirm balance is dashboard-only, Settings → Billing and credits). DISC-04 must be implemented as a cost estimate, not a balance display: "This will use up to N credits" where N = `min(matched-and-deduped candidates, 50)`, computed entirely locally with no Apollo call needed. Do not attempt to show remaining balance. If the teammate is actually out of credits, that surfaces naturally via Apollo's own API error at enrichment time, using the existing Phase 1 error-banner pattern (401/403/429 → plain-language banner, no traceback).
- D-06: Two distinct stages, not one combined action: (1) "Find Contacts" button — free, runs search + `has_email` pre-filter (DISC-02) + dedup exclusion (DEDUP-02), shows matched count and the cost estimate from D-05; (2) a separate "Enrich & Continue" button that actually spends credits. This is what makes DISC-04's "see cost before committing" literally true.

**Search-to-enrichment funnel**
- D-07: At the "Find Contacts" (pre-enrichment) stage, show count + cost estimate only — no contact table yet. Apollo's search response doesn't include real emails (only a `has_email` indicator), so a Name/Company/Title/Email table would have to fake or omit the Email column. The real table only appears after enrichment succeeds.
- D-08: When more than 50 eligible (post-dedup, has-email) candidates match, take Apollo's own result order for the first 50 — no additional ranking/tie-break logic. Trust Apollo's relevance ordering.
- D-09 (SEND-02, already locked pre-discussion): Hardcoded cap of 50 contacts per campaign for v1 — not user-configurable.

**Results list display**
- D-10: The post-enrichment contact list is read-only — the full enriched batch proceeds automatically to Phase 3 personalization. No per-contact removal/deselection in Phase 2; that capability is deferred to the Phase 4 bulk-approve review queue (QUEUE-03), consistent with REVIEW-01 being explicitly v2 scope.
- D-11: Table columns: Name, Company, Title, Email — the essentials for a non-technical teammate to sanity-check relevance. No industry/company-size columns (kept simple).
- D-12: Empty state (zero contacts after search + pre-filter + dedup): plain message — "No new contacts found — try different search terms" — with the free-text inputs still editable in place so the teammate can immediately retry. No credits were spent getting to this state (search + dedup filtering are both free), so retrying costs nothing.
- D-13 (already settled by CLAUDE.md, not re-discussed): Table renders via `st.dataframe`, per the project's existing tech-stack doc ("st.dataframe for search results").

### Claude's Discretion
None — all four discussed areas reached explicit user decisions; no "you decide" items remain open.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Per-contact removal in the discovery list, and AI-driven query normalization, were both considered and explicitly deferred as future possibilities rather than new capabilities — see D-04 and D-10 above.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|--------------------|
| PATH-01 | User sees exactly three outreach path options — Club Sponsorship, Productthon Sponsorship, Client Sourcing | UI-SPEC.md already locks exact copy/order; no Apollo research needed — pure Streamlit `st.selectbox` render, covered under Architecture Patterns / Project Structure |
| PATH-02 | Selecting a path determines all downstream search filters, sequence ID, and email template (user configures nothing else about targeting) | D-01 locks path selection to affect only sequence ID/template, never search filters — see Architectural Responsibility Map row "Free-text -> Apollo filter translation"; Pattern 4 shows the filter translation is path-independent |
| PATH-03 | User enters a company type / industry and target role as free-text inputs to guide contact discovery within the selected path | UI-SPEC.md locks exact field labels/placeholders; Pattern 2 shows the form-field wiring |
| DISC-01 | Agent translates user's company type and role inputs into Apollo People Search filters (no raw filter UI shown to user) | Pattern 4 (`to_filter_list`) + Code Examples' request body shape for `mixed_people/api_search` (`person_titles`, `q_organization_keyword_tags`) |
| DISC-02 | Apollo search results are pre-filtered to contacts with `has_email: true` before enrichment (no credits spent on un-emailable contacts) | Confirmed `has_email` boolean field exists in search response (Code Examples, Sources: docs.apollo.io/docs/find-people-using-filters); Pitfall 4 documents correct pipeline ordering |
| DISC-03 | Agent runs Apollo bulk enrichment to retrieve verified email addresses for discovered contacts | Pattern 1 (`search_people`) + Pattern 3 (batching into groups of <=10 for `bulk_match_people`) + Code Examples' `people/bulk_match` request/response shape |
| DISC-04 | Credit balance is displayed to the user before any enrichment begins so they can see cost impact before committing | D-05 (verbatim above) reframes this as a local cost estimate, not a balance display — Pitfall 4 documents the exact computation order required |
| DEDUP-02 | Contacts already present in the registry are excluded before enrichment (no credit waste on repeat contacts) | Architectural Responsibility Map row "Dedup exclusion query"; Assumptions A4 documents the domain-level dedup dependency on `organization.website_url`; `db/prospects.py` recommended in Project Structure queries the existing `contacted_registry` view (Phase 1) |
</phase_requirements>

## Summary

Phase 2 is almost entirely an extension of two files that already exist (`apollo/client.py`, `db/schema.py`'s `contacted_registry` view) plus one new Streamlit page. There is no new external dependency to add — `requests`, `streamlit`, and `sqlite3` (stdlib) already cover everything this phase needs. The core technical risk is not "what library to use" but "does the exact Apollo request/response shape match what CONTEXT.md's decisions assume" — this is MEDIUM confidence because Apollo's public docs pages return interactive "Try It" schema viewers that cannot be scraped for a literal example JSON body, so several field names below are corroborated by a third-party OpenAPI mirror (mindcloud.co) rather than a first-party JSON example. This mirrors exactly the situation Phase 1 hit with the credit-balance field (01-RESEARCH.md Open Question #1) — that was resolved with a Wave 0 human-verify checkpoint making one real authenticated call. This research recommends the same pattern here: build the client functions against the field names documented below, but gate the first real search + first real bulk_match call behind a `checkpoint:human-verify` task before building the full parsing/table-rendering logic on top of assumed field names.

The two-stage Find→Enrich flow (D-06/UI-SPEC) is a textbook `st.session_state` persistence problem: `st.button` only returns `True` on the exact rerun it was clicked, so the "Enrich & Continue" button's visibility and the results table must be driven by session-state-stored results, not by the button's return value directly. This is a well-documented, common Streamlit pattern (CITED below) and not a novel problem — no library needed, ~15 lines of state management.

**Primary recommendation:** Extend `apollo/client.py` with two new functions (`search_people`, `bulk_match_people`) following the exact `tuple[bool|list|None, str]` never-raises pattern already established by `check_apollo_health`; add a new `db/prospects.py` module for dedup-query and insert logic (keep `db/schema.py` DDL-only, per Phase 1's existing separation); add `pages/discovery_page.py` driven entirely by `st.session_state`. Gate the exact Apollo field-name assumptions behind one live-verify checkpoint task early in the plan, exactly as Phase 1 did for credit balance.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Path selection + free-text input UI | Browser / Client (Streamlit widget render) | Frontend Server (Streamlit is server-rendered) | Streamlit runs the whole app server-side per session; "client" here means the rendered widget, but all logic executes in the single Python process — no separate client/server split exists in this stack |
| Free-text → Apollo filter translation (DISC-01) | API / Backend (Python function in `apollo/client.py` or a small translation helper) | — | Pure data transformation, no I/O — belongs next to the client that consumes its output |
| Apollo search call (0 credits) | API / Backend (`apollo/client.py`) | External Service (Apollo) | Outbound REST call, must be isolated behind the typed-tuple client pattern already established |
| `has_email` pre-filter (DISC-02) | API / Backend | — | Client-side filter on the search response before any enrichment call is made — must happen before DEDUP-02 filtering and before the cost estimate is computed, so credits are never spent on unemailable contacts |
| Dedup exclusion query (DEDUP-02) | Database / Storage (`contacted_registry` view) + API/Backend (query + filter glue code) | — | The view already computes `dedupable_domain`; new code only needs to SELECT known IDs/domains and filter the in-memory search results against them — no new schema needed |
| Cost estimate computation (DISC-04/D-05) | API / Backend (pure local computation, `min(matched, 50)`) | — | Explicitly locked as a local computation with **no Apollo call** — CONTEXT.md D-05 |
| Apollo bulk enrichment call (1 credit/match) | API / Backend (`apollo/client.py`) | External Service (Apollo) | Same client pattern; must batch into groups of ≤10 per `/people/bulk_match` call |
| Enriched-contact persistence (`prospect` table writes) | Database / Storage | API / Backend (write glue) | New rows written with `status='enriched'`; must use parameterized queries per Phase 1's Security Domain rule |
| Two-stage flow state (Find result → Enrich button visibility → results table) | Browser / Client (`st.session_state`, scoped per browser session) | — | Streamlit session state is the only mechanism to persist data across the two independent button reruns within one user's session |

## Project Constraints (from CLAUDE.md)

These directives apply to every task in this phase's plan and must not be contradicted:

- **Apollo is the only contact/sequencing layer.** No parallel email delivery, no external contact store — this phase writes discovered contacts to local SQLite only for pipeline state tracking, never as a substitute system of record.
- **AI personalization is out of scope for this phase.** Claude Haiku / opening-line generation belongs to Phase 3 — do not call the Anthropic SDK from any file this phase touches.
- **`st.secrets["APOLLO_API_KEY"]`** is the only place the key is read from — never log or print it (T-04-02, restated in CONTEXT.md's Existing Code Insights).
- **Do not request `reveal_phone_number`.** Costs +8 credits/person and is explicitly out of scope for v1 (email-only).
- **Error codes:** 401/403 → banner, never retry. 422 → surface `response.json()["message"]` directly, don't swallow. 429 → exponential backoff, max 3 retries, log and surface if all retries fail. This table is already implemented for `check_apollo_health`; the new search/enrichment functions must extend it, especially the 429 backoff (not yet implemented anywhere in the codebase — Phase 1's two endpoints don't hit real rate limits in normal use).
- **`st.dataframe`** is locked for the results table (CLAUDE.md's UI table + D-13) — do not introduce a custom HTML table or `st.table`.
- **No new database engine** — SQLite via stdlib `sqlite3` only; no ORM.
- **No agent framework** (LangChain/CrewAI/etc.) — this is a deterministic, synchronous pipeline of direct `requests` calls, consistent with Phase 1's implementation.
- **GSD workflow enforcement (repo-level CLAUDE.md):** file edits must happen through the GSD execute-phase flow — not a constraint on research content, but the planner should be aware plans will be executed via `/gsd-execute-phase`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `requests` | 2.34.2 (already pinned, installed, verified via `python3 -c "import requests"`) [VERIFIED: local environment] | Apollo REST calls | Already the project's HTTP client (Phase 1); no reason to introduce `httpx` for a synchronous 2-endpoint extension |
| `streamlit` | 1.59.2 (already pinned, installed) [VERIFIED: local environment] | UI + session state | Already the project's UI framework; this phase's only new usage surface is `st.session_state`, `st.dataframe`, `st.selectbox`, `st.text_input` — all stable, long-standing Streamlit APIs |
| `sqlite3` (stdlib) | Python 3.13.2 installed locally (project targets 3.12 per CLAUDE.md; stdlib `sqlite3` API is stable across both) [VERIFIED: local environment] | Dedup query + prospect row writes | Already the project's persistence layer (Phase 1's `db/schema.py`) |

**No new packages are required for this phase.** Every capability (HTTP calls, retry/backoff, session state, table rendering, SQL query) is covered by libraries already in `requirements.txt`.

### Supporting
None — this phase adds no supporting libraries.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled `time.sleep`-based exponential backoff (≤10 lines) | `tenacity` (retry library) | CLAUDE.md's stated philosophy is "5 lines of direct SDK calls" over added abstraction; a 3-attempt exponential backoff for 2 endpoints is small enough that a dependency adds more surface area (supply-chain, version pinning) than it saves. Not recommended. |
| In-memory dedup filtering (query registry once, filter Python list) | A SQL `NOT IN` subquery against `contacted_registry` per search result | In-memory filtering is simpler to test (pure function, no DB round-trip per candidate) and the candidate set is capped at ≤100 per search page — no performance reason to push filtering into SQL. Recommended: in-memory. |

**Installation:** None required — no `pip install` step needed for this phase.

## Package Legitimacy Audit

**Not applicable — this phase introduces zero new external packages.** All functionality is built on `requests`, `streamlit`, and stdlib `sqlite3`, all of which were already vetted and installed during Phase 1. No `slopcheck`/registry verification is needed; skip the Package Legitimacy Gate for this phase's planning.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  pages/discovery_page.py  (Streamlit, single page, st.session_state) │
│                                                                       │
│  [path selectbox] [company-type text] [target-role text]             │
│           │                                                          │
│           ▼ (click "Find Contacts")                                  │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ 1. translate free text -> Apollo filters (DISC-01, in-process)│    │
│  │ 2. apollo.client.search_people(...)  ──────────────► Apollo   │    │
│  │    POST /mixed_people/api_search   (0 credits)      People    │    │
│  │    <───────────────────────────────────────────────  Search   │    │
│  │ 3. filter: has_email == true          (DISC-02)               │    │
│  │ 4. db.prospects.dedup_filter(candidates) (DEDUP-02, SQLite    │    │
│  │    query against contacted_registry view, in-memory filter)   │    │
│  │ 5. cap to 50 (D-08/D-09)                                       │    │
│  │ 6. cost = min(len(candidates), 50)     (D-05, local, no call) │    │
│  │ 7. store {candidates, cost} in st.session_state                │    │
│  └──────────────────────────────────────────────────────────────┘    │
│           │                                                          │
│           ▼ render st.info(count/cost) or st.info(empty state, D-12) │
│           │                                                          │
│           ▼ (click "Enrich & Continue" — only rendered if candidates>0)│
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ 8. chunk candidates into groups of ≤10        (bulk_match cap)│    │
│  │ 9. apollo.client.bulk_match_people(chunk) x N ────────► Apollo│    │
│  │    POST /people/bulk_match  (1 credit/match)          Bulk    │    │
│  │    <──────────────────────────────────────────────── Enrich   │    │
│  │ 10. merge chunk responses, drop non-matches                   │    │
│  │ 11. db.prospects.insert_enriched(rows)  -> prospect table,    │    │
│  │     status='enriched'                    (SQLite write)       │    │
│  │ 12. store enriched rows in st.session_state                   │    │
│  └──────────────────────────────────────────────────────────────┘    │
│           │                                                          │
│           ▼ render st.dataframe(Name, Company, Title, Email)  (D-11) │
└─────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
apollo/
├── client.py              # EXTEND: add search_people(), bulk_match_people()
db/
├── schema.py               # UNCHANGED — DDL/bootstrap only, per Phase 1 separation
├── prospects.py             # NEW: dedup query + prospect row insert/select (CRUD, parameterized SQL)
pages/
├── health_page.py           # UNCHANGED
├── discovery_page.py         # NEW: the Contact Discovery page, session-state driven
app.py                      # EXTEND: register discovery_page in the pages dict (comment placeholder already exists)
tests/
├── test_apollo_client.py    # EXTEND: add RED tests for search_people/bulk_match_people
├── test_prospects.py         # NEW: dedup query + insert tests
```

### Pattern 1: Extend the typed-tuple client, never raise
**What:** Every new Apollo call returns a typed tuple `(data_or_None, message)` and never lets an exception escape — identical shape to `check_apollo_health`/`get_credit_balance` in `apollo/client.py`.
**When to use:** Any new function added to `apollo/client.py` in this phase.
**Example:**
```python
# Source: apollo/client.py (existing code, Phase 1) — extend this exact shape
def search_people(
    api_key: str,
    person_titles: list[str],
    org_keyword_tags: list[str],
    per_page: int = 100,
    page: int = 1,
) -> tuple[list[dict] | None, str]:
    """Returns (people_or_None, message). Never raises. 0 credits."""
    payload = {
        "person_titles": person_titles,
        "q_organization_keyword_tags": org_keyword_tags,
        "per_page": per_page,
        "page": page,
    }
    try:
        resp = requests.post(
            f"{APOLLO_BASE}/mixed_people/api_search",
            headers={"x-api-key": api_key},
            json=payload,
            timeout=15,
        )
    except requests.RequestException:
        return None, "Contact search failed — check your internet connection and try again."

    if resp.status_code == 401:
        return None, "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."
    if resp.status_code == 403:
        return None, "Apollo connection failed — this key is not a Master API key. Check Apollo Settings → Integrations → API Keys."
    if resp.status_code == 429:
        return None, "Apollo is rate-limiting search requests right now — please wait a moment and try again."
    if resp.status_code != 200:
        return None, f"Contact search failed — unexpected status {resp.status_code}."

    data = resp.json()
    return data.get("people", []), "OK"
```

### Pattern 2: Session-state-driven two-stage flow (Find → Enrich)
**What:** Store the outcome of stage 1 (Find) in `st.session_state`; gate stage 2's button and the results table on that stored state, not on `st.button`'s own return value across reruns.
**When to use:** `pages/discovery_page.py`, exactly per D-06/D-07/UI-SPEC's Layout & Discovery Flow State System table.
**Example:**
```python
# Source: docs.streamlit.io/develop/concepts/architecture/session-state (official pattern, CITED)
import streamlit as st

if "find_result" not in st.session_state:
    st.session_state.find_result = None   # None = not yet searched this session
if "enrich_result" not in st.session_state:
    st.session_state.enrich_result = None

path = st.selectbox("Outreach path", PATH_OPTIONS, index=None, placeholder="Select an outreach path...")
company_type = st.text_input("Company type or industry", placeholder="e.g. software startups, nonprofits, apparel brands")
target_role = st.text_input("Target role", placeholder="e.g. Marketing Director, Head of Partnerships")

find_disabled = not path or not (company_type.strip() or target_role.strip())
if st.button("Find Contacts", type="primary", icon=":material/manage_search:", disabled=find_disabled):
    st.session_state.enrich_result = None  # discard any prior enrichment (per UI-SPEC: re-search always resets)
    with st.spinner("Searching Apollo for matching contacts..."):
        st.session_state.find_result = run_find(path, company_type, target_role)  # returns dict or error

if st.session_state.find_result and st.session_state.find_result.get("candidates"):
    n = len(st.session_state.find_result["candidates"])
    cost = min(n, 50)
    st.info(f"Found {n} new contact{'s' if n != 1 else ''} — enriching will use up to {cost} credit{'s' if cost != 1 else ''}.")
    if st.button("Enrich & Continue", type="primary", icon=":material/bolt:"):
        with st.spinner("Enriching contacts with verified emails..."):
            st.session_state.enrich_result = run_enrich(st.session_state.find_result["candidates"][:50])

if st.session_state.enrich_result and st.session_state.enrich_result.get("rows"):
    st.success(f"Enrichment complete — {len(st.session_state.enrich_result['rows'])} contacts ready.")
    st.dataframe(st.session_state.enrich_result["rows"])
```

### Pattern 3: Batching bulk_match into groups of ≤10
**What:** `/people/bulk_match` accepts a max of 10 objects in its `details[]` array per call — chunk the ≤50-contact candidate list into ≤5 sequential calls.
**When to use:** `apollo/client.py`'s `bulk_match_people` orchestration, or a thin wrapper that calls it per chunk.
**Example:**
```python
# Source: apollo.MD / spec.MD §3.3 (project's own confirmed reference) + docs.apollo.io/reference/bulk-people-enrichment
def _chunk(items: list, size: int = 10):
    for i in range(0, len(items), size):
        yield items[i : i + size]

def enrich_candidates(api_key: str, candidates: list[dict]) -> tuple[list[dict] | None, str]:
    """Batches candidates into groups of <=10 and calls bulk_match_people per batch."""
    all_matches: list[dict] = []
    for batch in _chunk(candidates, 10):
        details = [
            {
                "id": c["id"],                          # search-result person id
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "organization_name": c.get("organization", {}).get("name"),
                "domain": c.get("organization_domain"),   # see Open Questions — exact field TBD
            }
            for c in batch
        ]
        matches, msg = bulk_match_people(api_key, details)
        if matches is None:
            return None, msg  # surface the first failure immediately, per D-06 (error banner, retry both buttons)
        all_matches.extend(matches)
    return all_matches, "OK"
```
**Note (redundant matching fields):** Pass `id` AND `first_name`/`last_name`/`organization_name`/`domain` together in each `details[]` object rather than `id` alone. There is unresolved, conflicting third-party commentary (see Common Pitfalls, Pitfall 3) about whether Apollo's bulk match reliably resolves on `id` alone for records sourced from a prior search call — passing the redundant name/org fields costs nothing and improves match reliability regardless of which behavior is true.

### Pattern 4: Free-text to Apollo filter list translation (DISC-01/D-02/D-03)
**What:** Apollo's `person_titles` and `q_organization_keyword_tags` are both arrays of strings, not single strings. Split the user's free text on commas into a list; a single-phrase input becomes a one-element list.
**When to use:** The translation step between the Streamlit form and `search_people()`.
**Example:**
```python
# Source: docs.apollo.io/docs/find-people-using-filters — official example shows title
# variants as separate array elements (e.g. ["sales director", "director sales", "director, sales"])
def to_filter_list(free_text: str) -> list[str]:
    """Split comma-separated free text into a list of literal keyword strings.
    No AI normalization (D-04) — a straight split-and-strip only."""
    if not free_text or not free_text.strip():
        return []
    return [part.strip() for part in free_text.split(",") if part.strip()]
```

### Anti-Patterns to Avoid
- **Gating the results table on `st.button`'s return value alone:** `st.button` is `True` only on the exact rerun it fires — every later rerun (e.g. triggered by widget interaction elsewhere on the page) it returns `False` again. Always persist the result in `st.session_state` (Pattern 2).
- **Calling Apollo inside a loop with no batching for enrichment:** `/people/bulk_match` explicitly supports up to 10 people per call — looping single-person calls burns 5x the rate-limit budget for the same result.
- **Building a credit-balance API check for DISC-04:** Already ruled out by CONTEXT.md D-05 and Phase 1's confirmed finding — Apollo has no balance endpoint. Do not resurrect this.
- **Re-implementing the free-email-domain exclusion list inline:** It already exists in `db/schema.py`'s `free_email_domains` table, exposed via `contacted_registry.dedupable_domain`. Query the view, don't hardcode a second list (Phase 1's Pitfall 4, still applicable).
- **F-string interpolating user free text or Apollo-derived values into SQL:** Use `?` placeholders exclusively in `db/prospects.py`, per Phase 1's Security Domain rule (still in force, restated in CONTEXT.md's code_context).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| HTTP retries with backoff | A custom retry framework/decorator library | A small local `_post_with_retry()` helper (≤15 lines: try, catch 429, `time.sleep(backoff)`, max 3 attempts) inside `apollo/client.py` | CLAUDE.md's stated philosophy explicitly favors direct, minimal code over abstraction for this project; 3-attempt backoff for 2 endpoints doesn't justify a new dependency |
| Domain extraction from a URL (`organization.website_url` → `"acme.com"`) | A regex-based ad hoc parser | `urllib.parse.urlparse` (stdlib) — `urlparse(url).netloc.removeprefix("www.").lower()` | stdlib already handles scheme-optional URLs, ports, and edge cases (e.g. `http://www.acme.com/` vs `acme.com`) correctly; a hand-rolled regex will miss edge cases the dedup logic silently depends on being correct |
| Free/personal email domain exclusion list | A second hardcoded list inside the discovery page or query helper | The existing `free_email_domains` table + `contacted_registry.dedupable_domain` view column (Phase 1) | Single source of truth already exists — duplicating it risks drift between Phase 1's health/dedup logic and Phase 2's discovery logic |
| Session-state-gated multi-step UI flow | A custom "wizard" state machine class | `st.session_state` dict keys directly (Pattern 2 above) | Streamlit's own recommended pattern for exactly this problem; a custom state machine adds abstraction with no functional benefit at 2 stages |

**Key insight:** Nothing in this phase is genuinely novel-complexity — every "don't hand-roll" item above is either already solved in this repo (Phase 1's dedup view) or solved by 10-20 lines of stdlib usage. The temptation to over-engineer (a generic retry decorator, a state-machine class, a second dedup list) should be resisted in favor of the minimal, already-established patterns.

## Common Pitfalls

### Pitfall 1: Assuming `mixed_people/api_search` returns a usable "Name" for the pre-enrichment stage
**What goes wrong:** Building a results table (or even a name list) at the "Find Contacts" stage, before enrichment.
**Why it happens:** It's tempting to show *something* concrete to reassure the teammate a search worked.
**How to avoid:** The search response's `last_name_obfuscated` field [CITED: builtbyjoey.com's field summary, corroborated by mindcloud.co's OpenAPI mirror] means full names are not reliably available pre-enrichment — this independently reinforces CONTEXT.md D-07's decision to show count + cost only at this stage, not a table. Do not build a partial-name table as a "nice to have."
**Warning signs:** A task in the plan proposing to render `st.dataframe` before the Enrich step, or a column showing a truncated/obfuscated name.

### Pitfall 2: Treating Apollo `429` responses as fatal on the first hit
**What goes wrong:** Surfacing a rate-limit error to the teammate on the very first retry-able 429, when 3 retries with backoff would likely succeed.
**Why it happens:** No retry logic exists yet anywhere in the codebase — Phase 1's two endpoints (`auth/health`, `usage_stats`) don't hit real limits during normal use, so this is genuinely new code, not a copy-paste extension.
**How to avoid:** Implement the CLAUDE.md-mandated "exponential backoff, max 3 retries" for both new client functions before wiring them into the page. Only surface the rate-limit banner after all 3 retries are exhausted (per D-06/UI-SPEC's exact copy: "Apollo is rate-limiting search/enrichment requests... please wait a moment and try again").
**Warning signs:** A client function with no `for attempt in range(...)` loop around the request, or a test that doesn't cover the 429-then-200-on-retry case.

### Pitfall 3: Assuming `id` alone in `bulk_match`'s `details[]` reliably resolves search-result people
**What goes wrong:** Passing only `{"id": "<search_result_id>"}` per person in the enrichment batch and getting a much higher no-match rate than expected, silently burning API calls (though not credits, since unmatched records cost 0) and confusing the teammate with a smaller-than-expected enriched batch.
**Why it happens:** Official Apollo docs [CITED: docs.apollo.io/reference/people-enrichment] document `id` as a valid, unique-identifier field "retrieve via People API Search endpoint" for the single-person People Enrichment endpoint, implying it should also work for bulk. However, at least one independent third-party integration guide [LOW confidence, single source: builtbyjoey.com] specifically claims IDs sourced from `mixed_people/api_search` do not reliably resolve when passed into `bulk_match`'s `details[]`, and recommends `first_name` + `last_name` + `organization_name` instead, or falling back to the single-person `people/match` endpoint (same 1-credit cost). This is an unresolved contradiction between an official docs page and a third-party field report — genuinely uncertain, not just under-documented.
**How to avoid:** Per Pattern 3 above, always pass `id` together with `first_name`/`last_name`/`organization_name`/`domain` in every `details[]` object — this costs nothing and hedges against either behavior being true. Additionally, treat this as a Wave 0 human-verify checkpoint: make one real `bulk_match` call with a small real batch and confirm the match rate is reasonable (not near-zero) before building the full enrichment pipeline around field-name assumptions.
**Warning signs:** A plan/task that passes only `id` with no fallback fields, or a live test showing most/all of a batch coming back unmatched despite `has_email: true` at search time.

### Pitfall 4: Computing the cost estimate from the raw search result count instead of the post-filter count
**What goes wrong:** Showing "Found 100 contacts — up to 100 credits" when in fact only 37 have `has_email: true` and pass dedup, or under-showing when a `per_page` of 100 returns fewer usable candidates than the cap.
**Why it happens:** DISC-04's cost formula (`min(matched-and-deduped candidates, 50)`, D-05/D-08) must run strictly *after* both the `has_email` filter (DISC-02) and the dedup filter (DEDUP-02) — computing it against the raw Apollo response count instead would overstate cost and could also cause an off-by-N mismatch between the number shown and the number actually enriched.
**How to avoid:** Order the pipeline exactly as CONTEXT.md's D-06 states: search → has_email filter → dedup filter → cap at 50 → *then* compute `matched = len(final_candidates)`, `cost = matched` (already capped). Do not compute cost from an intermediate list.
**Warning signs:** A task that computes `cost` before the dedup-filter step, or a test asserting `cost == raw_search_result_count`.

### Pitfall 5: Re-querying Apollo on every Streamlit rerun instead of only on button click
**What goes wrong:** Every widget interaction on the page (e.g. typing in the text input, which triggers a rerun on each keystroke by default unless debounced) re-triggers a live Apollo search, burning rate-limit budget and producing a laggy UI.
**Why it happens:** Streamlit reruns the whole script top-to-bottom on every interaction; without explicit `if st.button(...):` gating, any code placed unconditionally at module level runs on every rerun.
**How to avoid:** Only call `search_people`/`bulk_match_people` inside the `if st.button("Find Contacts"):` / `if st.button("Enrich & Continue"):` blocks (Pattern 2) — never at module level or inside an unconditional render path.
**Warning signs:** A `search_people(...)` call that isn't nested directly under an `if st.button(...):` guard.

## Code Examples

### Full request/response shape reference (best available — verify live, see Open Questions)

**`POST /api/v1/mixed_people/api_search`** — request body [CITED: docs.apollo.io/reference/people-api-search + spec.MD's own prior confirmed reference]:
```json
{
  "person_titles": ["Marketing Director", "Head of Partnerships"],
  "q_organization_keyword_tags": ["software startups", "nonprofits"],
  "per_page": 100,
  "page": 1
}
```
Response (per person) [MEDIUM confidence — corroborated across two independent sources, not a first-party JSON example]:
```json
{
  "people": [
    {
      "id": "5f9...",
      "first_name": "Jamie",
      "last_name_obfuscated": "S***",
      "title": "Marketing Director",
      "has_email": true,
      "organization": { "name": "Acme Co", "website_url": "https://acme.com" }
    }
  ],
  "total_entries": 1
}
```
Explicitly does **not** contain a real email address or full last name — enrichment is required for both (Pitfall 1).

**`POST /api/v1/people/bulk_match`** — request body [CITED: docs.apollo.io/reference/bulk-people-enrichment + mindcloud.co field mirror]:
```json
{
  "details": [
    { "id": "5f9...", "first_name": "Jamie", "last_name": "Smith", "organization_name": "Acme Co", "domain": "acme.com" }
  ]
}
```
Response (per matched person) [MEDIUM confidence — field list sourced from a third-party OpenAPI mirror, not a first-party JSON example — verify live]:
```json
{
  "matches": [
    {
      "id": "5f9...",
      "first_name": "Jamie",
      "last_name": "Smith",
      "name": "Jamie Smith",
      "email": "jamie@acme.com",
      "email_status": "verified",
      "title": "Marketing Director",
      "organization_name": "Acme Co",
      "credits_consumed": 1
    }
  ]
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---------------|-------------------|----------------|--------|
| N/A — this is Phase 2 of a greenfield project; no prior Apollo integration approach to compare against within this repo | Direct REST calls via `requests`, typed-tuple never-raise client functions (established Phase 1) | Phase 1, 2026-07-20/22 | This phase continues the established pattern rather than introducing a new one — no state-of-the-art shift to document |

Nothing deprecated/outdated to flag — Apollo's REST API surface used here (`mixed_people/api_search`, `people/bulk_match`) is the currently documented, non-deprecated endpoint set per `docs.apollo.io` as of this research date.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|-----------------|
| A1 | Exact response field names for `mixed_people/api_search` (`id`, `first_name`, `last_name_obfuscated`, `has_email`, `organization.name`, `organization.website_url`, `total_entries`) | Code Examples, Architecture Patterns | If field names differ, the `has_email` pre-filter (DISC-02) and dedup-by-domain (DEDUP-02) logic will silently no-op (defensive `.get()` returns `None`/falsy) rather than crash — matches Phase 1's established defensive-degradation pattern, but should be confirmed live before shipping, not just assumed to "fail safe" forever |
| A2 | Exact response field names for `people/bulk_match` (`matches[]`, `email`, `email_status`, `name`/`first_name`/`last_name`, `organization_name`, `credits_consumed`) | Code Examples, Architecture Patterns | Same defensive-degradation risk as A1, but higher stakes — this is the step that actually spends credits, so a silent field-name mismatch could spend credits and then fail to populate the results table, confusing the teammate about whether credits were wasted |
| A3 | `id` from a search result reliably resolves a match when passed into `bulk_match`'s `details[]`, especially when combined with `first_name`/`last_name`/`organization_name`/`domain` | Pitfall 3, Pattern 3 | If unreliable even with redundant fields, match rate could be lower than the cost estimate implied — teammate sees "up to 50 credits" but gets far fewer enriched contacts back for the credits spent. Mitigation already built into Pattern 3 (pass all fields, not id-only) |
| A4 | `organization.website_url` (or equivalent) is present on search results and can be parsed into a bare domain for pre-enrichment domain-level dedup (DEDUP-02) | Pitfall 4, Don't Hand-Roll table | If the field is absent or named differently, domain-level dedup can only run post-enrichment (using the enriched `organization_name`/email domain), which would mean DEDUP-02's "no credit waste on repeat contacts" guarantee only partially holds — contact-ID-level dedup would still work regardless (person IDs are present in search results with HIGH confidence) |
| A5 | `person_titles` and `q_organization_keyword_tags` match literally/keyword-style on comma-split free text (not requiring exact full-title match or AI-normalized phrasing) | Pattern 4 | If matching is stricter than expected, search relevance may be poor for oddly-phrased free text — this is explicitly a relevance concern only (not a cost concern, per D-04's own reasoning), and CONTEXT.md already accepts this risk and defers any fix to "revisit only if relevance turns out to be a real problem" |

**Resolution path for A1-A4:** Add a Wave 0 `checkpoint:human-verify` task — one real `search_people()` call and one real `bulk_match_people()` call against a live Apollo account, inspecting the raw JSON response and adjusting field-name lookups if they differ from the assumptions above. This exactly mirrors Phase 1's Task 3 resolution of the credit-balance field-name question (01-04-SUMMARY.md).

## Open Questions

1. **Exact field names in `mixed_people/api_search` and `people/bulk_match` responses (A1/A2 above)**
   - What we know: Field names corroborated across 2+ independent secondary sources (a third-party blog, a third-party OpenAPI mirror) and partially confirmed by official docs' parameter-only pages.
   - What's unclear: Apollo's official interactive reference pages could not be scraped for a literal example JSON response in this research session (they render via a JS "Try It" widget, not static HTML).
   - Recommendation: Wave 0 human-verify checkpoint task (see Assumptions Log resolution path). Build the client functions with defensive `.get()` lookups (never a bare `data["field"]` that could `KeyError`) so a field-name mismatch degrades gracefully rather than crashing, consistent with Phase 1's established defensive pattern.

2. **Does `id`-only resolution work in `bulk_match`, or must name/org fields always accompany it? (A3 above, Pitfall 3)**
   - What we know: Official docs list `id` as a valid enrichment field, sourced from People API Search. A third-party guide claims practical failures using search-sourced IDs in bulk_match specifically.
   - What's unclear: Whether this is a genuine API behavior gap, a mistake in that third-party guide, or a plan-tier-specific limitation.
   - Recommendation: Always send redundant fields (Pattern 3) regardless of which is true — zero cost to do so. Confirm actual match rate during the Wave 0 human-verify checkpoint.

3. **Is `contact_email_status` a usable server-side filter on `mixed_people/api_search` to reduce reliance on the client-side `has_email` filter?**
   - What we know: One official docs excerpt mentioned a `contact_email_status[]` param accepting `verified`/`unverified`/`likely to engage`/`unavailable` in the context of a people-search-adjacent page.
   - What's unclear: Whether this param applies to net-new People Search results or only to an account's already-created Apollo Contacts (a different object type) — the two concepts are easy to conflate and this research could not fully disambiguate them from available doc excerpts.
   - Recommendation: **Do not use this param for v1.** CONTEXT.md D-02 already locks the mechanism to a client-side `has_email` boolean filter, which is independently confirmed (HIGH confidence) to exist on search results. Treat `contact_email_status` as a possible future optimization, not a v1 requirement — using an unconfirmed server-side filter risks silently returning zero results if misapplied to the wrong object type.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|------------|---------|----------|
| `requests` | Apollo REST calls | Yes [VERIFIED: local environment] | 2.34.2 | — |
| `streamlit` | UI + session state | Yes [VERIFIED: local environment] | 1.59.2 | — |
| `sqlite3` (stdlib) | Dedup query + prospect writes | Yes [VERIFIED: local environment, Python 3.13.2] | stdlib | — |
| `pytest` | Test suite | Yes [VERIFIED: local environment] | 9.0.2 | — |
| Apollo.io Master API key + live account | All Apollo calls, Wave 0 human-verify checkpoint | Unknown at research time — requires `.streamlit/secrets.toml` with a real `APOLLO_API_KEY`, not something this research session has access to or should probe without explicit human involvement | — | If no live key is available when the plan reaches its human-verify checkpoint task, that task blocks until one is provided — same precedent as Phase 1's Task 3 (session paused, resumed once real credentials were available) |

**Missing dependencies with no fallback:**
- None among local libraries — everything needed is already installed and pinned.

**Missing dependencies with fallback:**
- Live Apollo credentials for the Wave 0 verify step — no code fallback exists (verifying against a mock only re-confirms the assumptions in this document, not reality), but the *process* fallback is the same pause/resume pattern Phase 1 already used successfully.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (already installed and configured) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Quick run command | `pytest tests/test_apollo_client.py tests/test_prospects.py -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|----------------|
| PATH-01 | Exactly 3 path options rendered, in order | manual-only (UI render, no Streamlit component test harness in this project) | — (visual check against UI-SPEC's exact copy table) | N/A — manual per project convention (no `streamlit.testing` harness set up in Phase 1) |
| PATH-02 | Path selection changes only sequence ID/template, never search filters | unit | `pytest tests/test_discovery_logic.py::test_path_does_not_affect_filters -x` | ❌ Wave 0 |
| PATH-03 | Free text company type + role accepted as inputs | manual-only (UI form) | — | N/A — manual |
| DISC-01 | Free text translated into Apollo filters correctly (comma-split, no AI) | unit | `pytest tests/test_discovery_logic.py::test_to_filter_list -x` | ❌ Wave 0 |
| DISC-02 | `has_email:false` candidates excluded before enrichment | unit | `pytest tests/test_discovery_logic.py::test_has_email_prefilter -x` | ❌ Wave 0 |
| DISC-03 | Bulk enrichment retrieves emails, batches ≤10 per call | unit (mocked `requests`) | `pytest tests/test_apollo_client.py::test_bulk_match_people_batches_of_ten -x` | ❌ Wave 0 |
| DISC-04 | Cost estimate = `min(matched-and-deduped, 50)`, computed with no Apollo call | unit | `pytest tests/test_discovery_logic.py::test_cost_estimate_no_apollo_call -x` | ❌ Wave 0 |
| DEDUP-02 | Candidates already in `contacted_registry` excluded pre-enrichment | unit (uses `tmp_db_path` fixture + real `ensure_schema()`) | `pytest tests/test_prospects.py::test_dedup_filter_excludes_known_contacts -x` | ❌ Wave 0 |
| Error handling (429/401/403/422) | Client functions return correct typed-tuple + message per code | unit (mocked `requests`, extends Phase 1's `mock_requests_response` fixture) | `pytest tests/test_apollo_client.py::test_search_people_error_codes tests/test_apollo_client.py::test_bulk_match_people_error_codes -x` | ❌ Wave 0 |
| Session-state flow (two-stage Find/Enrich) | Manual (no Streamlit component test harness configured) | manual-only | — | N/A — manual, same as PATH-01/PATH-03 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_apollo_client.py tests/test_prospects.py tests/test_discovery_logic.py -q`
- **Per wave merge:** `pytest -q` (full suite, includes Phase 1's existing tests to guard against regressions)
- **Phase gate:** Full suite green before `/gsd:verify-work`, plus the Wave 0 human-verify checkpoint (live search + live bulk_match call) completed and any field-name mismatches from the Assumptions Log resolved

### Wave 0 Gaps
- [ ] `tests/test_discovery_logic.py` — new file: covers PATH-02, DISC-01, DISC-02, DISC-04 (pure functions, no network — filter translation, has_email pre-filter, cost estimate)
- [ ] `tests/test_prospects.py` — new file: covers DEDUP-02 (dedup query against `contacted_registry`, insert enriched rows), reuses `tmp_db_path` fixture from `tests/conftest.py`
- [ ] `tests/test_apollo_client.py` — extend existing file: add RED tests for `search_people()` and `bulk_match_people()` (success, 401/403/422/429, batching of ≤10 per call), reusing the existing `mock_requests_response` fixture
- [ ] No new fixtures needed in `conftest.py` — `tmp_db_path` and `mock_requests_response` already cover this phase's needs; may need a small `mock_apollo_search_response(n, has_email_count)` / `mock_apollo_bulk_match_response(n)` factory helper for readability, but this is a nice-to-have, not a gap

*(Framework itself: no install needed — pytest 9.0.2 already present and configured.)*

## Sources

### Primary (HIGH confidence)
- `apollo/client.py`, `db/schema.py`, `tests/conftest.py`, `tests/test_apollo_client.py`, `app.py` (this repo, Phase 1) — existing patterns extended directly
- `.planning/phases/02-contact-discovery/02-CONTEXT.md` (D-01 through D-13, live-verified during discuss-phase) — locked decisions
- `.planning/phases/02-contact-discovery/02-UI-SPEC.md` — locked UI contract
- `.planning/phases/01-foundation/01-04-SUMMARY.md` — confirmed no Apollo credit-balance endpoint exists; establishes the human-verify checkpoint precedent this research recommends repeating
- `spec.MD` §3.1-3.3 (project's own confirmed Apollo reference) — search/enrichment endpoint order, credit cost, batch size
- CLAUDE.md "Key API Notes (Apollo.io)" — rate limits, error-code handling table, credit costs
- docs.streamlit.io/develop/concepts/architecture/session-state — session-state pattern for sequential buttons (fetched live)
- docs.apollo.io/docs/api-pricing — confirmed search = free, bulk enrichment = 1-9 credits/person depending on fields requested (fetched live)
- docs.apollo.io/reference/people-enrichment — confirmed `id` as a documented enrichment input field, sourced from People API Search (fetched live)

### Secondary (MEDIUM confidence)
- docs.apollo.io/reference/people-api-search — confirmed `has_email` boolean field, `contact_email_status` param existence (ambiguous scope), `person_titles`/`organization_num_employees_ranges`/`per_page` param names (fetched live, partial excerpt only)
- docs.apollo.io/docs/find-people-using-filters — confirmed `person_titles` array format with multi-phrasing example, response field names `id`/`first_name`/`last_name_obfuscated`/`title`/`has_email`/`organization.*` (fetched live)
- docs.apollo.io/reference/bulk-people-enrichment — confirmed `details[]` array, max 10 per call, `reveal_personal_emails`/`reveal_phone_number`/`webhook_url` query params (fetched live)
- mindcloud.co/docs/universal/rest/apollo/latest/actions/bulk-people-enrichment — third-party OpenAPI mirror providing the fuller `bulk_match` request/response field list used in Code Examples (fetched live, not first-party)

### Tertiary (LOW confidence)
- builtbyjoey.com/blog/apollo-api-lead-generation-guide — claim that search-sourced `id` values don't reliably resolve in `bulk_match` (Pitfall 3) — single third-party source, contradicts an official docs implication, flagged for live verification rather than trusted outright

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, everything already installed/verified locally
- Architecture (session-state flow, client pattern, file structure): HIGH — direct extension of Phase 1's established, working patterns; session-state pattern is CITED from official Streamlit docs
- Apollo request/response field names: MEDIUM — official docs pages could not be scraped for literal example JSON (interactive-only), corroborated instead via secondary/tertiary sources; mitigated by a recommended Wave 0 human-verify checkpoint (same pattern Phase 1 used successfully)
- Pitfalls: MEDIUM-HIGH — most are logically derived from confirmed constraints (rate limits, batch size, D-05/D-06/D-07 ordering); Pitfall 3 specifically is LOW-confidence-sourced but hedged with a zero-cost mitigation (Pattern 3)

**Research date:** 2026-07-24
**Valid until:** 30 days (Apollo API surface is stable per official docs; re-verify sooner if the Wave 0 human-verify checkpoint reveals field-name mismatches, as that would indicate more active API drift than assumed)
