# Phase 3: AI Personalization - Research

**Researched:** 2026-09-17
**Domain:** Anthropic Python SDK (Claude Haiku) synchronous per-contact text generation, hallucination-resistant prompt design, Streamlit session-state chaining, SQLite schema evolution on an existing populated table
**Confidence:** HIGH (SDK mechanics, error/retry/timeout behavior, package legitimacy — all CITED from official docs or live-verified). MEDIUM (prompt-design grounding techniques — CITED but inherently probabilistic, not code-enforceable). LOW-flagged where noted (sparse-title heuristic, batch-failure threshold — both explicitly left to planner/implementer discretion by CONTEXT.md).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Generation trigger & draft visibility**
- D-01: Draft generation runs automatically, chained immediately after Discovery's "Enrich & Continue" succeeds — no separate button. Rationale: Haiku cost is negligible (~$0.04/campaign per CLAUDE.md), so there's no spend-gate reason to add a second manual stage like Apollo's Find/Enrich split.
- D-02: Draft visibility lives on the existing Discovery page (`pages/discovery_page.py`) — extend the post-enrichment results table with an expandable "View draft" per row. No new page for Phase 3; the formal multi-contact Review Queue is Phase 4's job (QUEUE-01/02).
- D-03: The draft preview shows the full assembled email as a single combined block (opening line + template body together, as it would actually be sent) — not split into separate "AI part" vs "template part" sections.
- D-04: Generated drafts persist to SQLite immediately with `status='drafted'`, consistent with the existing `found → selected → enriched → drafted → approved → sequenced` status progression from Phase 1's schema. Not session-state-only.

**Opening line style & fallback**
- D-05: Tone is warm-but-professional — conversational, references their role/company, not stiff corporate boilerplate and not casual/slang. Fits a student org emailing real companies.
- D-06: The opening line may reference **only `title` + `company`** from Apollo data — no industry/seniority, even when those fields are present. Lowest hallucination-risk surface, satisfies success criterion 1 (verifiable fields only).
- D-07: The generic safe-fallback opener (success criterion 3) triggers **only when `title` is missing, null, or placeholder-looking** for a contact. Company name is guaranteed present by the time a contact reaches `status='enriched'`, so title is the only field in scope of D-06 that can realistically be sparse. (Explicitly NOT triggered by missing industry/seniority — those fields are never used in the opening line per D-06, so their absence is irrelevant to fallback logic.)
- D-08: Opening line length target: **1 sentence, ~20-30 words** — keeps output tokens low (matches CLAUDE.md's ~50-60 output-token budget) and reads as a natural email opener rather than a paragraph.

**Email template content per path**
- D-09: `{opening_line}` is inserted as its own standalone line immediately after the "Hello [First Name]!" greeting, before the intro paragraph, in **all three** path templates.
- D-10: No email attachments in any template. Apollo sequences are pre-built in the Apollo UI; this app only enrolls contacts, never composes attachments. Productthon and Club Sponsorship templates reference the sponsorship package via a hosted link instead.
- D-11: Both link-referencing templates use a literal `[SPONSORSHIP_LINK]` placeholder for now — a manual user setup step before any real send, not a Phase 3 build blocker.
- D-12: Client Sourcing subject line: `Partner with Product Space UW on Your Next Product Initiative`.
- D-13 (Phase 4 requirement change, recorded here for traceability): `REQUIREMENTS.md` QUEUE-03 updated from single "Approve All" to per-contact checkboxes (default checked) — not implemented in Phase 3.

**Claude API failure handling**
- D-14: Per-contact Haiku failure (timeout, transient API error) uses the **same generic fallback opener** as the sparse-data case (D-07) — one consistent fallback path regardless of cause. The contact still gets a draft and stays in the batch; nothing is silently dropped.
- D-15: One retry before falling back — mirrors Apollo's own 429-backoff pattern but lighter, since Haiku failures are usually transient.
- D-16: If a high fraction of the batch fails (e.g., >50% — exact threshold left to planner), surface a plain-language error banner ("AI personalization is unavailable right now — drafts are using generic openers"), mirroring the existing Apollo error-banner convention. Below that threshold, per-contact fallback is silent.

### Claude's Discretion
- Exact numeric threshold for D-16's "high fraction of batch fails" banner trigger — planner/implementer picks a reasonable value (e.g., >50%) since the user did not specify one.

### Deferred Ideas (OUT OF SCOPE)
- Real hosted link for the sponsorship package/prospectus — currently a `[SPONSORSHIP_LINK]` placeholder (D-11). Manual user action needed before any real campaign send. Flag prominently in the Phase 3 SUMMARY's "User Setup Required" section.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERS-01 | Agent generates one AI-written personalized opening line per contact using Claude Haiku, seeded with Apollo's title/company (industry/seniority explicitly excluded per D-06); assembles the full email draft (AI opening line + path-specific template body) | Pattern 1 (Anthropic SDK call shape), Pattern 2 (grounding prompt with XML tags), Pattern 3 (sparse-data/failure fallback), Pattern 4 (template assembly), Code Examples section, Don't Hand-Roll table (retry via SDK `max_retries`, don't hand-roll a template engine) |
</phase_requirements>

## Summary

This phase is a synchronous, per-contact text-generation step bolted onto the end of Discovery's existing "Enrich & Continue" handler. The Anthropic Python SDK (`anthropic>=0.117.0` per CLAUDE.md; verified current release is 1.6.0, fully satisfying that constraint) exposes a stable, well-documented `client.messages.create()` call with a `system` prompt parameter, a documented error-class hierarchy (`RateLimitError`, `APITimeoutError`, `APIConnectionError`, `APIStatusError`/subclasses), and — critically for this phase's D-15 "one retry before falling back" requirement — a **built-in retry mechanism** (`max_retries`, default 2) that already covers connection errors, 408/409/429/5xx. Setting `max_retries=1` on a dedicated client instance implements D-15 with zero hand-rolled retry code, mirroring this repo's existing philosophy of thin, direct SDK usage over custom abstraction (CLAUDE.md's "5 lines of direct SDK calls" principle, already demonstrated by `apollo/client.py`'s `_post_with_retry`).

The harder problem is not calling the API — it's grounding the output. Success criterion 1 ("no hallucinated details") cannot be *guaranteed* by any code-level mechanism; Claude's output is probabilistic. The mitigation is a combination of (a) a tightly scoped system prompt that explicitly enumerates the only two permitted facts (title, company) inside XML tags — Anthropic's own documented technique for reducing hallucination and improving instruction-following — and (b) CONTEXT.md's own risk-reduction decision (D-06) to exclude industry/seniority entirely, which removes two additional fabrication surfaces regardless of prompt quality. This is inherently a MEDIUM-confidence mitigation, not a HIGH-confidence guarantee, and should be flagged to the planner as requiring human spot-check review during execution (a `checkpoint:human-verify` reviewing a sample of generated openers against their source fields), not just automated tests.

The other significant technical risk is SQLite schema evolution against a **live, already-populated** database: `db/outreach.db` currently has 11 real rows with `status='enriched'` and no `opening_line` column. `db/schema.py`'s `ensure_schema()` uses `CREATE TABLE IF NOT EXISTS`, which does **not** retroactively add columns to an existing table — a naive DDL edit would silently no-op against the current dev database. The fix is a small idempotent `ALTER TABLE ... ADD COLUMN` migration guarded by catching SQLite's "duplicate column name" `OperationalError`, run from `ensure_schema()` itself (same idempotent-boot philosophy Phase 1 already established).

**Primary recommendation:** Add a new `personalization/` package (`generator.py` for the Anthropic call + fallback logic, `templates.py` for the three static path templates + assembly function). Extend `db/schema.py` with an idempotent column migration (`opening_line`, `first_name`, `draft_source`) and `db/prospects.py` with an `update_draft()` write function. Extend `pages/discovery_page.py`'s existing "Enrich & Continue" handler to chain draft generation immediately after `insert_enriched()` succeeds, using a `st.progress` bar (not just a spinner, since a 50-contact batch is a distinctly-visible-duration operation) and per-row `st.expander("View draft")`. Add `ANTHROPIC_API_KEY` to the app's boot-time secrets presence gate (`app.py`), mirroring the existing `APOLLO_API_KEY` check.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Opening-line generation (Claude Haiku call) | API / Backend (`personalization/generator.py`) | External Service (Anthropic) | Outbound REST call via SDK, isolated behind a typed-tuple client function exactly like `apollo/client.py` |
| Sparse-data / failure fallback logic | API / Backend (`personalization/generator.py`) | — | Pure decision logic (is title usable? did the call fail?) — no I/O of its own, colocated with the call it guards |
| Email template storage + assembly | API / Backend (`personalization/templates.py`) | — | Static per-path string templates + a pure merge-field substitution function; no external I/O |
| Draft persistence (`opening_line`, `draft_source`, `status='drafted'` write) | Database / Storage (`prospect` table via `db/prospects.py`) | API / Backend (write glue) | Extends the existing `insert_enriched`/status-write pattern; must use parameterized queries per Phase 1's Security Domain rule |
| Draft chaining trigger (auto-run after Enrich succeeds) | Browser / Client (`st.session_state`, inside the existing "Enrich & Continue" button handler) | — | Streamlit's single-process server-rendered model — this is orchestration glue in `pages/discovery_page.py`, not a new tier |
| Draft preview rendering (`st.expander` "View draft" per row) | Browser / Client (Streamlit widget render) | — | Read-only display of already-computed/persisted draft text |
| API key presence gate (`ANTHROPIC_API_KEY`) | API / Backend (`app.py` boot sequence) | — | Same tier as the existing `APOLLO_API_KEY` gate; fails closed before any page renders |

## Project Constraints (from CLAUDE.md)

These directives apply to every task in this phase's plan and must not be contradicted:

- **Model is locked:** `claude-haiku-4-5-20251001` via `anthropic>=0.117.0` — no substituting GPT-4o-mini/Gemini Flash, no upgrading to Sonnet/Opus for this task.
- **Token budget:** ~500 input / ~50-60 output tokens per contact (~$0.04/campaign total) — the prompt design must stay within this budget; do not add few-shot examples or verbose system prompts that blow past ~500 input tokens.
- **`st.secrets["ANTHROPIC_API_KEY"]`** is the only place the key is read from — never log or print it (same rule as `APOLLO_API_KEY`, T-02-04/T-04-02 precedent).
- **No agent framework** (LangChain/LangGraph/CrewAI) — a single direct `client.messages.create()` call per contact, consistent with the deterministic-pipeline philosophy already used for Apollo.
- **No parallel email delivery / no external template CMS** — templates are static Python strings owned by this app, consistent with "Apollo is the only sequencing/delivery layer."
- **SQLite via stdlib `sqlite3` only, no ORM** — schema changes are raw DDL in `db/schema.py`, consistent with Phase 1/2.
- **Error codes (Apollo pattern, applied analogously to Anthropic):** surface plain-language banners, never a raw traceback; this repo's established convention (`apollo/client.py`, `pages/discovery_page.py`) of "never raise, return a typed tuple" should extend to the new Anthropic-calling function.
- **GSD workflow enforcement (repo-level CLAUDE.md):** file edits happen through `/gsd-execute-phase` — not a constraint on research content, but the planner should be aware plans execute via that flow.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.117.0` per CLAUDE.md; latest available on PyPI is **1.6.0** [VERIFIED: PyPI registry, `pip index versions anthropic`, checked 2026-09-17] — satisfies the CLAUDE.md constraint | Claude API client for opening-line generation | Official Anthropic SDK; the only supported way to call Claude from Python. `>=0.117.0` intentionally allows the 1.x line — no reason to pin below current. |
| `streamlit` | 1.59.2 (already pinned/installed) [VERIFIED: local environment, matches `requirements.txt`] | Draft preview UI (`st.expander`, `st.progress`) | Already the project's UI framework; this phase's only new usage surface is `st.progress` and `st.expander` — both stable, long-standing APIs |
| `sqlite3` (stdlib) | Python 3.13.2 installed locally (project targets 3.12 per CLAUDE.md; stdlib API stable across both) [VERIFIED: local environment] | Draft persistence, schema migration | Already the project's persistence layer |

**No other new external packages are required.** Template assembly is plain Python `str.format`/f-strings — no templating engine (Jinja2, etc.) is justified for 3 static, hand-written templates with 3 merge fields each.

### Supporting
None — no supporting libraries beyond the `anthropic` SDK itself.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A dedicated `Anthropic(max_retries=1)` client for D-15's "one retry" | A hand-rolled retry loop (like `apollo/client.py`'s `_post_with_retry`) | The SDK already implements exactly this behavior (documented default `max_retries=2`, configurable) — hand-rolling would duplicate logic the SDK provides natively. Not recommended; see Don't Hand-Roll. |
| Plain f-string/`str.format` template assembly | Jinja2 | 3 static templates, 3 merge fields (`first_name`, `company`, `opening_line`), no loops/conditionals needed inside template bodies — a full templating engine is unjustified complexity for this phase. Not recommended. |
| Synchronous sequential loop (1 Haiku call per contact, in order) | `AsyncAnthropic` + `asyncio.gather` for concurrent calls | Would cut wall-clock time for a 50-contact batch roughly proportionally, but CLAUDE.md explicitly favors the simplest deterministic-pipeline approach ("no agent frameworks," implicit preference against added async/orchestration complexity), and Streamlit's execution model already blocks the UI thread during any long operation regardless of concurrency inside it — the user is already waiting through `st.spinner`/`st.progress` for the Apollo enrichment call before this step runs. At ≤50 contacts and sub-2-second typical Haiku latency, sequential is ~30-100s total, an acceptable extension of the wait the user already experiences. Recommended: sequential for v1; revisit only if real-world latency proves unacceptable. |

**Installation:**
```bash
pip install anthropic
```
Add `anthropic>=0.117.0` to `requirements.txt` alongside the existing `streamlit==1.59.2`, `requests==2.34.2`, `dnspython==2.8.0` pins. Given the project pins exact versions elsewhere, pin `anthropic==1.6.0` (the verified-current release) rather than leaving it unpinned, for reproducibility consistent with the rest of `requirements.txt`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `anthropic` | PyPI | Multi-year, actively maintained (0.x → 1.6.0 over 100+ releases) [VERIFIED: PyPI registry version history] | ~31.8M/week [MEDIUM confidence: WebSearch of pypistats.org, not independently re-verified against the live pypistats API in this session] | `github.com/anthropics/anthropic-sdk-python` — official Anthropic organization repo | `[OK]` — verified via `slopcheck install anthropic` (scanned and reported "1 OK" against the PyPI index before the local sandbox's `pip` binary-name resolution issue interrupted the actual install step; the scan verdict itself completed successfully) [VERIFIED: slopcheck 0.6.1 output, run 2026-09-17] | Approved |

**Packages removed due to slopcheck `[SLOP]` verdict:** none
**Packages flagged as suspicious `[SUS]`:** none

This is the project's own official first-party SDK per CLAUDE.md's explicit "AI / LLM Layer" table — not a package discovered via open-ended search — and slopcheck's scan independently confirms a clean, legitimate PyPI listing. No `checkpoint:human-verify` gate is required before this specific install, though the planner may still choose to add one as a matter of course for any new dependency.

## Architecture Patterns

### System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│  pages/discovery_page.py — "Enrich & Continue" handler (extended)         │
│                                                                             │
│  [existing] enrich_candidates() ──────────► Apollo /people/bulk_match      │
│  [existing] insert_enriched(rows) ──► prospect table, status='enriched'   │
│           │                                                                │
│           ▼ (NEW, chained automatically per D-01 — no extra button)       │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ For each enriched match row (st.progress "Personalizing N/50..."): │    │
│  │                                                                     │    │
│  │  1. title = match.get("title")                                     │    │
│  │  2. is_sparse = _is_sparse_title(title)         (D-07 heuristic)   │    │
│  │  3. if is_sparse:                                                  │    │
│  │        opening_line, source = FALLBACK_LINE, "fallback"            │    │
│  │     else:                                                          │    │
│  │        try:                                                        │    │
│  │          opening_line = generate_opening_line(                     │    │
│  │              client, title, company)  ───────► Anthropic API       │    │
│  │              POST /v1/messages  (claude-haiku-4-5-20251001)        │    │
│  │              <──────────────────────────────── (SDK auto-retries   │    │
│  │                                                  once, D-15)       │    │
│  │          source = "ai"                                             │    │
│  │        except anthropic errors:                                    │    │
│  │          opening_line, source = FALLBACK_LINE, "fallback"  (D-14)  │    │
│  │  4. subject, body = assemble_email(path_slug, first_name,          │    │
│  │        company, opening_line)          (personalization/templates) │    │
│  │  5. db.prospects.update_draft(prospect_id, opening_line, source)   │    │
│  │        -> UPDATE prospect SET opening_line=?, draft_source=?,      │    │
│  │           status='drafted' WHERE id=?           (D-04)             │    │
│  │  6. accumulate {subject, body, source} into draft_result list      │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│           │                                                                │
│           ▼ fallback_fraction = fallback_count / total                    │
│           ▼ if fallback_fraction > THRESHOLD (D-16, e.g. 0.5):            │
│               st.warning("AI personalization is unavailable right now —   │
│                            drafts are using generic openers.")            │
│           │                                                                │
│           ▼ render st.dataframe (existing Name/Company/Title/Email table) │
│           ▼ render st.expander("View draft") per row -> subject + body    │
│              as a single combined block                       (D-03)      │
└───────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
personalization/
├── __init__.py
├── generator.py         # NEW: generate_opening_line(), _is_sparse_title(), FALLBACK_LINE, typed-tuple never-raise pattern
├── templates.py          # NEW: PATH_TEMPLATES dict (subject + body per slug), assemble_email()
db/
├── schema.py              # EXTEND: idempotent ALTER TABLE migration for opening_line/first_name/draft_source columns
├── prospects.py            # EXTEND: add update_draft()
pages/
├── discovery_page.py        # EXTEND: chain draft generation after insert_enriched(), render st.progress + st.expander
app.py                     # EXTEND: add ANTHROPIC_API_KEY to boot-time secrets presence gate
tests/
├── test_personalization.py  # NEW: RED tests for generator.py + templates.py
├── test_prospects.py         # EXTEND: add update_draft() tests
├── test_schema.py             # EXTEND: add column-migration idempotency test
requirements.txt          # EXTEND: add anthropic==1.6.0
.streamlit/secrets.toml.example  # EXTEND: add ANTHROPIC_API_KEY placeholder
```

### Pattern 1: Typed-tuple, never-raise Anthropic client call (mirrors `apollo/client.py`)
**What:** `generate_opening_line()` returns `(line: str, source: Literal["ai","fallback"])` and never lets an Anthropic SDK exception escape to the caller — identical philosophy to `check_apollo_health`/`search_people`.
**When to use:** The one new function in `personalization/generator.py` that calls the Anthropic API.
**Example:**
```python
# Source: platform.claude.com/docs/en/cli-sdks-libraries/sdks/python (CITED, fetched live 2026-09-17)
# + this repo's apollo/client.py typed-tuple convention
from __future__ import annotations

import anthropic

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "You write a single opening sentence for a cold outreach email from a "
    "student organization to a business contact. Tone: warm but professional "
    "-- conversational, not stiff corporate boilerplate, not casual or slang.\n\n"
    "You will be given the contact's title and company inside <contact> tags. "
    "You may reference ONLY the exact title and company text given -- do not "
    "infer, assume, or add any detail (industry, seniority, achievements, "
    "location, or anything else) that is not literally present in the tags. "
    "If you are unsure whether something is grounded in the given data, leave "
    "it out.\n\n"
    "Output ONLY the single sentence itself -- no quotation marks, no preamble "
    "like 'Here's an opening line:', no labels. One sentence, 20-30 words."
)


def generate_opening_line(
    client: "anthropic.Anthropic", title: str, company: str
) -> tuple[str | None, str]:
    """Call Claude Haiku for one grounded opening sentence. Never raises.

    Returns (line_or_None, message). Caller applies D-14 fallback on None.
    """
    user_prompt = f"<contact><title>{title}</title><company>{company}</company></contact>"
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIConnectionError:
        return None, "Personalization request failed — connection error."
    except anthropic.RateLimitError:
        return None, "Personalization rate-limited."
    except anthropic.APIStatusError as e:
        return None, f"Personalization failed — status {e.status_code}."

    text_blocks = [b.text for b in message.content if b.type == "text"]
    line = "".join(text_blocks).strip().strip('"').strip()
    if not line:
        return None, "Personalization returned empty output."
    return line, "OK"
```
**Note on D-15 (one retry before falling back):** Construct the client with `max_retries=1` (see Pattern 2) rather than wrapping this function in a manual retry loop — the SDK's built-in retry already covers connection errors, `RateLimitError` (429), and `>=500` `APIStatusError`s per the official retry table.

### Pattern 2: Configure the client once for D-15 (retry) and a bounded synchronous-batch timeout
**What:** The SDK's default timeout is **10 minutes** and default `max_retries` is **2** [CITED: platform.claude.com/docs/en/cli-sdks-libraries/sdks/python, "Retries" and "Timeouts" sections, fetched live 2026-09-17]. Both defaults are wrong for this phase's use case: a 10-minute per-call timeout inside a 50-iteration synchronous Streamlit loop could hang the entire batch for hours in a worst case; and D-15 explicitly wants exactly *one* retry, not two.
**When to use:** Once, at the top of the draft-generation flow (e.g., in `pages/discovery_page.py` or a small `personalization/generator.py`-level factory), before the per-contact loop begins.
**Example:**
```python
# Source: platform.claude.com/docs/en/cli-sdks-libraries/sdks/python (CITED)
import anthropic

client = anthropic.Anthropic(
    api_key=st.secrets.get("ANTHROPIC_API_KEY"),
    max_retries=1,     # D-15: exactly one retry before the caller's fallback kicks in
    timeout=20.0,       # bounded per-call timeout; default 10 min is unacceptable in a
                        # 50-iteration synchronous loop (mirrors apollo/client.py's timeout=15
                        # pattern for the same reason)
)
```

### Pattern 3: Sparse-title detection + shared fallback (D-07/D-14)
**What:** A single deterministic fallback opener is used both when `title` is missing/null/placeholder-looking (D-07) AND when the Haiku call fails after its one retry (D-14) — one fallback path, two triggers.
**When to use:** `personalization/generator.py`, called from the per-contact loop in `pages/discovery_page.py`.
**Example:**
```python
# Fallback references ONLY company (D-06's other allowed field), never title,
# since title is by definition the unreliable/absent field in this branch.
FALLBACK_LINE = (
    "I hope this reaches you at a good time -- I wanted to reach out to "
    "{company} directly."
)

_PLACEHOLDER_TITLES = {"", "n/a", "na", "unknown", "-", "none", "tbd"}


def _is_sparse_title(title: str | None) -> bool:
    """D-07: title missing, null, or placeholder-looking.

    [ASSUMED] The exact set of placeholder strings Apollo may return for a
    missing title is not documented anywhere in Apollo's API reference --
    this heuristic (blank/whitespace-only or a small common-placeholder
    blocklist) is a reasonable default, not a verified Apollo behavior.
    Flag for adjustment if real Apollo data surfaces other placeholder
    patterns during execution.
    """
    if not title or not title.strip():
        return True
    return title.strip().lower() in _PLACEHOLDER_TITLES
```

### Pattern 4: Template assembly without a templating engine (D-09/D-10/D-11/D-12)
**What:** Three static path templates (verbatim text locked in CONTEXT.md's `<specifics>` section) with plain `str.format`-style merge fields: `{first_name}`, `{company}`, `{opening_line}`. `{opening_line}` is inserted as its own line after the greeting, per D-09, in all three templates.
**When to use:** `personalization/templates.py`.
**Example:**
```python
# Source: CONTEXT.md <specifics> section (verbatim template text, user-approved)
PATH_TEMPLATES = {
    "club_sponsorship": {
        "subject": "Partner with Product Space UW — {company} Annual Sponsorship",
        "body": (
            "Hello {first_name}!\n\n"
            "{opening_line}\n\n"
            "I hope this email finds you well! ...\n\n"  # full body per CONTEXT.md
            "Here's our sponsorship prospectus with our full tier breakdown: "
            "[SPONSORSHIP_LINK]. ...\n\n"
            "Best regards,\nYash Kulkarni\n"
            "Director of Internal, Product Space at the University of Washington"
        ),
    },
    "productthon": {"subject": "...", "body": "..."},
    "client_sourcing": {"subject": "...", "body": "..."},
}


def assemble_email(
    path_slug: str, first_name: str, company: str, opening_line: str
) -> tuple[str, str]:
    """Returns (subject, body) with merge fields substituted. Pure function."""
    template = PATH_TEMPLATES[path_slug]
    subject = template["subject"].format(company=company)
    body = template["body"].format(
        first_name=first_name, company=company, opening_line=opening_line
    )
    return subject, body
```
**Important — `first_name` source:** `db.prospects.insert_enriched` (Phase 2) only stores the combined `name` field on the `prospect` row, never a separate `first_name` column. The raw Apollo match dict passed into the "Enrich & Continue" handler *does* carry `first_name` directly (used by `apollo/client.py`'s own `enrich_candidates` batching). Use that raw in-memory field for template assembly at generation time — do not derive `first_name` by splitting the stored `name` string (lossy for multi-word first/last names). Recommend also persisting `first_name` as a new `prospect` column in this phase's schema migration (see Common Pitfalls) so a later page load / Phase 4 re-render doesn't need to guess it.

### Anti-Patterns to Avoid
- **Hand-rolling a retry loop for the Anthropic call:** The SDK already retries connection errors, 408/409/429, and 5xx twice by default — set `max_retries=1` (Pattern 2) instead of writing a second `_post_with_retry`-style helper.
- **Leaving the client at its 10-minute default timeout inside a 50-iteration synchronous loop:** A single hung call could stall the whole batch far longer than any user will wait. Always override `timeout`.
- **Passing `industry`/`seniority` fields into the prompt "just in case":** D-06 explicitly excludes them from the opening line even when present — don't pass fields to the model that it's instructed not to use; this only increases hallucination surface area for no benefit.
- **Trusting the model to never wrap output in quotes or add a preamble despite instructions:** Defensively `.strip()` surrounding quotes/whitespace on the returned text (Pattern 1) rather than assuming 100% instruction-following.
- **Re-creating the DB file or dropping the `prospect` table to add new columns:** `db/outreach.db` already has real enriched rows (11 as of this research session) — schema changes must be additive `ALTER TABLE` migrations, never a drop/recreate.
- **F-string interpolating Apollo-derived or AI-generated text into raw SQL:** Use `?` placeholders exclusively in `update_draft()`, per Phase 1's Security Domain rule (still in force).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| "One retry before falling back" (D-15) | A custom `_post_with_retry`-style loop around `client.messages.create()` | `anthropic.Anthropic(max_retries=1)` | The SDK's documented default retry behavior already covers exactly the failure modes D-15 cares about (connection errors, 429, 5xx, 408/409) — configuring the built-in mechanism is strictly less code and less risk than duplicating it |
| Email template rendering (3 static templates, 3 merge fields) | Jinja2 or another templating engine | Plain `str.format()` (Pattern 4) | No loops, conditionals, or template inheritance needed — a full templating engine adds a dependency for a problem `str.format` solves in one line per field |
| Sparse-title / hallucination-risk detection | An ML classifier or a call to Claude asking "is this data sufficient?" | A simple `.strip()` + blocklist check (Pattern 3) | The condition space (blank, whitespace, or a small closed set of placeholder strings) is small and deterministic; an extra LLM call to decide whether to make an LLM call adds cost, latency, and its own failure mode for no accuracy gain |
| Idempotent SQLite column addition | A migration framework (Alembic, etc.) | A `try/except sqlite3.OperationalError` guarded `ALTER TABLE ADD COLUMN` (see Common Pitfalls) | 3 new columns, one time, on a stdlib-`sqlite3`-only project with no ORM — a migration framework is disproportionate; the existing `ensure_schema()` idempotent-boot pattern already handles this class of problem for table creation and extends naturally to column addition |

**Key insight:** Every genuinely novel piece of this phase (grounding the LLM output, detecting sparse data, retrying transient failures) has either an SDK-native solution (retries) or is small enough to be a pure function with no external dependency (sparse-title check, template assembly). The only place where more engineering effort is justified than a first instinct suggests is the *prompt itself* — that's genuinely hard to get fully right and is not a "don't hand-roll" problem, it's the one part of this phase that deserves the most iteration and human review.

## Common Pitfalls

### Pitfall 1: `ensure_schema()`'s `CREATE TABLE IF NOT EXISTS` will not add new columns to the existing populated database
**What goes wrong:** Editing `db/schema.py`'s `DDL` string to add `opening_line TEXT` to the `CREATE TABLE prospect (...)` statement has **no effect** on `db/outreach.db` if that file already exists — `CREATE TABLE IF NOT EXISTS` is a no-op against an existing table, columns and all. The 11 real rows currently in this dev database (confirmed live, `status='enriched'`) would silently never get an `opening_line` column, and every `INSERT`/`UPDATE` referencing it would raise `sqlite3.OperationalError: no such column`.
**Why it happens:** SQLite's `CREATE TABLE IF NOT EXISTS` checks table existence only, not column-level schema drift — unlike some ORMs' auto-migration behavior, there is no automatic column reconciliation.
**How to avoid:** Add an idempotent migration step to `ensure_schema()`, run after the existing `DDL`/`VIEW_DDL` execution:
```python
_NEW_COLUMNS = [
    ("opening_line", "TEXT"),
    ("first_name", "TEXT"),
    ("draft_source", "TEXT"),  # 'ai' | 'fallback'
]

def _migrate_columns(conn: sqlite3.Connection) -> None:
    for name, coltype in _NEW_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE prospect ADD COLUMN {name} {coltype}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise  # only swallow the expected "already exists" case
```
Call `_migrate_columns(conn)` from `ensure_schema()` before `conn.commit()`. This preserves the 11 existing rows (new columns default to `NULL`) and is safe to run on every boot, consistent with the existing idempotent-boot philosophy.
**Warning signs:** A test or manual run that raises `no such column: opening_line` the first time draft-writing code runs against the real (non-test) `db/outreach.db`; a plan task that edits the `DDL` string but has no separate migration step.

### Pitfall 2: Deriving `first_name` by splitting the stored `name` column instead of using the raw match's `first_name` field
**What goes wrong:** `db.prospects.insert_enriched` only writes a combined `name` string (e.g., "Jamie Van Der Berg") to the `prospect` table — there is no `first_name` column today. A tempting shortcut is `name.split()[0]` when assembling the template's `{first_name}` merge field, which breaks for compound first names, titles-with-name ("Dr. Jamie Smith"), or any name Apollo formats differently than "First Last".
**Why it happens:** The `prospect` table's existing schema wasn't designed with template merge-fields in mind — it only needed a display name for Phase 2's `st.dataframe`.
**How to avoid:** Draft generation runs in the same request/handler as `insert_enriched` (D-01, chained immediately) — the raw Apollo match dict with its real `first_name` field is still in scope in Python memory at that point. Use it directly for template assembly, and additionally persist it into the new `first_name` column (Pitfall 1's migration) so any future re-render (e.g., Phase 4's Review Queue re-querying from SQLite after a fresh session) has a reliable source instead of re-deriving it.
**Warning signs:** Any code path that computes `first_name` via string splitting on the `name` column rather than reading it from the original match dict or the new dedicated column.

### Pitfall 3: Trusting Anthropic's default 10-minute timeout inside a 50-iteration synchronous Streamlit loop
**What goes wrong:** If even one Haiku call in a 50-contact batch hangs (network stall, provider-side slowness) and the client is left at its documented default `timeout` of 10 minutes [CITED: platform.claude.com/docs/en/cli-sdks-libraries/sdks/python, "Timeouts" section], the entire Streamlit page — and the teammate's browser tab — appears frozen for up to 10 minutes on that single contact, with 49 more still to go if it eventually resolves.
**Why it happens:** The SDK's default is tuned for general-purpose single-request usage, not a tight synchronous batch loop with 50 sequential calls.
**How to avoid:** Construct the client with an explicit, much shorter `timeout` (Pattern 2 recommends 20 seconds, matching the existing `apollo/client.py` convention of `timeout=15` for Apollo calls). On `APITimeoutError`, treat it exactly like any other per-contact failure — apply the D-14 fallback and continue the loop.
**Warning signs:** A `personalization/generator.py` that constructs `anthropic.Anthropic()` with no `timeout=` argument, or a plan task that doesn't mention overriding SDK defaults.

### Pitfall 4: Assuming Claude will always output exactly one bare sentence with no formatting artifacts
**What goes wrong:** Despite an explicit "output ONLY the sentence, no quotes, no preamble" instruction, LLM outputs occasionally include a leading/trailing quotation mark, a trailing period doubled up with the template's own punctuation, or an unexpected "Sure, here's an opening line:" preamble — especially as prompt wording drifts during iteration.
**Why it happens:** Instruction-following is probabilistic, not guaranteed, even with well-structured prompts (this is the same underlying limitation that makes hallucination-prevention MEDIUM confidence, not HIGH).
**How to avoid:** Always `.strip()` the returned text and strip a leading/trailing `"` defensively (Pattern 1's example already does this). Do not add complex regex-based "clean up the model's output" logic beyond this — if the model routinely misbehaves beyond quote-wrapping, that's a signal to revise the system prompt, not to build an increasingly elaborate output-sanitization layer.
**Warning signs:** A rendered draft preview showing a quoted opening line ("...") or a stray "Here's your opening line:" fragment in the assembled email.

## Code Examples

### Full Anthropic call + fallback wiring inside the Discovery page's existing handler
```python
# Source: this repo's pages/discovery_page.py (existing pattern) + Pattern 1-3 above
import anthropic

anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=anthropic_key, max_retries=1, timeout=20.0)

draft_rows = []
fallback_count = 0
total = len(matches)
progress = st.progress(0, text=f"Personalizing drafts... 0/{total}")

for i, match in enumerate(matches):
    title = match.get("title")
    company = (match.get("organization") or {}).get("name") or ""
    first_name = match.get("first_name") or ""

    if _is_sparse_title(title):
        opening_line, source = FALLBACK_LINE.format(company=company), "fallback"
    else:
        line, msg = generate_opening_line(client, title, company)
        if line is None:
            opening_line, source = FALLBACK_LINE.format(company=company), "fallback"
        else:
            opening_line, source = line, "ai"

    if source == "fallback":
        fallback_count += 1

    subject, body = assemble_email(path_slug, first_name, company, opening_line)
    update_draft(match.get("id"), opening_line, source)  # -> status='drafted' (D-04)
    draft_rows.append({"subject": subject, "body": body, "source": source})
    progress.progress((i + 1) / total, text=f"Personalizing drafts... {i + 1}/{total}")

if total > 0 and fallback_count / total > 0.5:  # D-16 threshold, planner-set
    st.warning(
        "AI personalization is unavailable right now — drafts are using generic openers.",
        icon=":material/error:",
    )
```

### `db/prospects.py` draft-write function (extends existing patterns)
```python
# Source: this repo's db/prospects.py insert_enriched (existing pattern, parameterized SQL)
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| N/A — Phase 3 of a greenfield project; no prior AI-personalization approach in this repo | Direct `anthropic.Anthropic().messages.create()` call, typed-tuple never-raise client pattern (established Phase 1-2 for Apollo) | This phase, 2026-09 | Continues the established repo pattern rather than introducing a new one |

Nothing deprecated/outdated to flag — `claude-haiku-4-5-20251001` is Anthropic's current-generation Haiku model as of this research date, and the `anthropic` SDK's `messages.create()` interface is stable (the SDK's own docs state the signature "is stable and not expected to break in future 0.94.x releases," and the 1.x line preserves the same core interface).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The set of "placeholder-looking" title strings Apollo might return (blank, `"N/A"`, `"Unknown"`, `"-"`, etc.) matches the small blocklist proposed in Pattern 3 | Pattern 3, Common Pitfalls | If Apollo returns other placeholder patterns not in the blocklist, a genuinely-sparse title could be sent to Claude anyway, producing a lower-quality (but not necessarily hallucinated, since D-06 only allows title+company regardless) opening line. Low severity — does not violate success criterion 1, only opener quality. Fix by expanding the blocklist if observed during execution. |
| A2 | `~500 input / ~50-60 output tokens per contact` (CLAUDE.md's own budget) is achievable with the system+user prompt sizes in Pattern 1/2 | Standard Stack, Project Constraints | If actual token usage runs meaningfully higher (e.g., a verbose system prompt), the $0.04/campaign cost estimate in CLAUDE.md would be understated — still trivially cheap in absolute terms (Haiku pricing), so risk is informational only, not a blocker |
| A3 | A 20-second per-call timeout (Pattern 2) is long enough for normal Haiku latency but short enough to bound worst-case batch stall time | Pattern 2, Pitfall 3 | If Haiku's real-world p99 latency for this prompt size exceeds 20s under normal (non-failure) conditions, legitimate slow-but-successful calls could be misclassified as failures and fall back unnecessarily. This is a tunable constant, not a structural risk — safe to adjust based on observed latency during execution. |
| A4 | Persisting `first_name` as a new dedicated `prospect` column (beyond what CONTEXT.md's decisions explicitly required) is a low-risk, in-scope addition for this phase rather than scope creep | Pattern 4, Pitfall 2 | If the planner judges this out of scope for Phase 3, Phase 4's Review Queue would need a separate first-name-derivation strategy (or a small follow-up migration) when re-rendering drafts from a fresh session — worth flagging to the planner as a discretionary but recommended addition, not a hard requirement |

**None of the above are compliance, security, or retention-policy claims** — all four are implementation-detail heuristics explicitly flagged for adjustment if real data or real latency contradicts them.

## Open Questions

1. **Does Apollo ever return a title value that looks plausible but is stale/wrong (not blank/placeholder), which D-07's fallback trigger wouldn't catch?**
   - What we know: D-07 explicitly scopes the fallback trigger to "missing, null, or placeholder-looking" only — a present-but-inaccurate title is out of scope by design (CONTEXT.md's own explicit decision, not a gap this research introduces).
   - What's unclear: How often Apollo's title data is stale in practice (a title from months/years ago) is unknown and unmeasurable from this research session.
   - Recommendation: Accept as designed per D-07 — this is a data-quality question about Apollo itself, not a Phase 3 implementation gap. No action needed beyond what CONTEXT.md already decided.

2. **Exact numeric threshold for D-16's batch-failure banner**
   - What we know: CONTEXT.md explicitly defers this to planner/implementer discretion, suggesting >50% as an example.
   - What's unclear: No usage data exists yet to calibrate a more precise threshold.
   - Recommendation: Use `> 0.5` (a strict majority) as the default, exactly as CONTEXT.md's own example suggests — it's an unambiguous, easy-to-reason-about threshold and matches the "high fraction" framing in D-16's banner copy.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` (PyPI package) | Claude Haiku calls | Not yet installed in this repo [VERIFIED: local environment, `pip show anthropic` → not found] | Latest verified: 1.6.0 | Add to `requirements.txt` and install — no code fallback needed, this is a required new dependency per CLAUDE.md |
| `ANTHROPIC_API_KEY` (Streamlit secret) | All Claude Haiku calls | Not yet present in `.streamlit/secrets.toml` [VERIFIED: local environment, `secrets.toml` currently only has `APOLLO_API_KEY`/`SENDING_DOMAIN`] | — | Manual setup step: teammate/user must add the key to `.streamlit/secrets.toml` (local) and the Community Cloud secrets console (production) before this phase's functionality works end-to-end. Mirrors the existing `APOLLO_API_KEY` requirement — no code fallback exists for a missing LLM key; the app should fail closed with a plain-language banner (mirroring `app.py`'s existing `APOLLO_API_KEY` gate), not attempt to run without personalization. |
| `slopcheck` | Package legitimacy audit (this research session only) | Yes, installed during this session [VERIFIED: local environment, `slopcheck 0.6.1`] | 0.6.1 | — |
| `pytest` | Test suite | Yes [VERIFIED: local environment, matches Phase 2's research] | 9.0.2 (per Phase 2 research; not re-verified this session) | — |

**Missing dependencies with no fallback:**
- `ANTHROPIC_API_KEY` must be manually added to secrets before this phase can be exercised end-to-end against the real Anthropic API. This is a user setup step, not a code gap — the plan should include a task to update `.streamlit/secrets.toml.example` and document this requirement, and `app.py`'s boot gate should fail closed (plain banner) exactly like the existing `APOLLO_API_KEY` check if the key is absent.

**Missing dependencies with fallback:**
- `anthropic` package itself has no fallback — it is simply not yet installed and must be added as part of this phase's first task (no alternative library is appropriate given CLAUDE.md's explicit model/SDK lock).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (already installed and configured, per Phase 2 research; not independently re-verified this session) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) [VERIFIED: local environment, read directly] |
| Quick run command | `pytest tests/test_personalization.py tests/test_prospects.py tests/test_schema.py -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-01 (grounding) | Opening line generation call only sends title+company to the model (no industry/seniority passed) | unit (assert on the constructed prompt string, mocked `client.messages.create`) | `pytest tests/test_personalization.py::test_prompt_excludes_industry_and_seniority -x` | ❌ Wave 0 |
| PERS-01 (sparse fallback) | Missing/null/placeholder title triggers the shared fallback opener without calling the API | unit | `pytest tests/test_personalization.py::test_sparse_title_triggers_fallback -x` | ❌ Wave 0 |
| PERS-01 (API-failure fallback) | A simulated `anthropic.APIConnectionError`/`RateLimitError`/`APITimeoutError` after the SDK's own retry triggers the same fallback opener (D-14) | unit (mocked client raising the error) | `pytest tests/test_personalization.py::test_api_failure_triggers_fallback -x` | ❌ Wave 0 |
| PERS-01 (assembly) | `assemble_email()` produces the correct subject + body per path, with `{opening_line}` inserted immediately after the greeting (D-09) | unit | `pytest tests/test_personalization.py::test_assemble_email_per_path -x` | ❌ Wave 0 |
| PERS-01 (persistence) | `update_draft()` writes `opening_line`, `draft_source`, and `status='drafted'` correctly, using parameterized SQL | unit (uses `tmp_db_path` fixture + real `ensure_schema()`) | `pytest tests/test_prospects.py::test_update_draft_writes_status_drafted -x` | ❌ Wave 0 |
| PERS-01 (schema migration) | `ensure_schema()` is idempotent against a pre-existing `prospect` table missing the new columns — does not raise, adds columns exactly once | unit (create table without new columns, then call `ensure_schema()` twice) | `pytest tests/test_schema.py::test_column_migration_idempotent -x` | ❌ Wave 0 |
| PERS-01 (batch-failure banner threshold, D-16) | Fallback fraction > threshold triggers the banner condition; below threshold does not | unit (pure function, no Streamlit/network) | `pytest tests/test_personalization.py::test_fallback_fraction_threshold -x` | ❌ Wave 0 |
| PERS-01 (no-hallucination guarantee) | N/A — cannot be asserted by an automated test against a live/mocked LLM call; probabilistic output | manual-only, human review | — (sample-review a batch of real generated openers against source `title`/`company` during execution, before marking the phase done) | N/A — inherent limitation, not a test gap |

### Sampling Rate
- **Per task commit:** `pytest tests/test_personalization.py tests/test_prospects.py tests/test_schema.py -q`
- **Per wave merge:** `pytest -q` (full suite, guards against regressions in Phase 1/2 tests)
- **Phase gate:** Full suite green before `/gsd:verify-work`, plus a manual human-review sample of real (or realistically-mocked) generated opening lines checked against their source title/company fields — this is the one success criterion (no hallucination) that automated tests structurally cannot verify.

### Wave 0 Gaps
- [ ] `tests/test_personalization.py` — new file: covers prompt construction (grounding), sparse-title fallback, API-failure fallback, template assembly, fallback-fraction threshold (pure functions + mocked `anthropic` client, no live network calls)
- [ ] `tests/test_prospects.py` — extend existing file: add `update_draft()` tests reusing the existing `tmp_db_path` fixture
- [ ] `tests/test_schema.py` — extend existing file: add the column-migration idempotency test (create a pre-migration table, call `ensure_schema()` twice, assert no error and columns present)
- [ ] `tests/conftest.py` — add a `mock_anthropic_message` factory fixture (mirrors the existing `mock_requests_response` fixture) that builds a fake SDK response object with `.content = [SimpleNamespace(type="text", text="...")]`, so tests can monkeypatch `client.messages.create` without a real API key
- [ ] Framework install: `pip install anthropic==1.6.0` and add to `requirements.txt` — required before any of the above tests can import `personalization/generator.py`

## Security Domain

`security_enforcement` is set to `false` in `.planning/config.json` — this section is omitted per the workflow configuration. One note carried over regardless, since it is already an established repo-wide convention rather than a new ASVS-driven control: never log or print `ANTHROPIC_API_KEY`, mirroring the existing `APOLLO_API_KEY` rule (T-02-04/T-04-02 precedent).

## Sources

### Primary (HIGH confidence)
- `apollo/client.py`, `db/prospects.py`, `db/schema.py`, `pages/discovery_page.py`, `pages/health_page.py`, `app.py`, `tests/conftest.py`, `tests/test_apollo_client.py`, `tests/test_prospects.py` (this repo, Phases 1-2) — existing patterns extended directly
- `db/outreach.db` (this repo, live query, 2026-09-17) — confirmed 11 real rows at `status='enriched'`, no `opening_line`/`first_name`/`draft_source` columns present, directly informing Pitfall 1
- `.streamlit/secrets.toml` (existence/key-names only, values never read or printed, 2026-09-17) — confirmed `ANTHROPIC_API_KEY` is not yet present
- platform.claude.com/docs/en/cli-sdks-libraries/sdks/python — fetched live 2026-09-17: `system` parameter usage, full error-class table (400→`BadRequestError` through 429→`RateLimitError`, `APIConnectionError`), default `max_retries=2` and which errors are auto-retried, default `timeout` of 10 minutes and `APITimeoutError` behavior, sync vs. `AsyncAnthropic` usage
- `.planning/config.json` — `nyquist_validation: true` (Validation Architecture section included), `security_enforcement: false` (Security Domain section omitted)
- `.planning/phases/03-ai-personalization/03-CONTEXT.md` — D-01 through D-16, exact template text, locked decisions
- CLAUDE.md "AI / LLM Layer" — model/SDK version lock, token budget, cost estimate

### Secondary (MEDIUM confidence)
- WebSearch, cross-referenced against the official docs page above: Claude Haiku 4.5 release date, 200K context window, 64K max completion tokens, $1.00/$5.00 per MTok input/output pricing (matches CLAUDE.md's own stated pricing exactly, corroborating both sources)
- WebSearch (pypistats.org via search snippet, not independently re-queried against the live API): ~31.8M/week download count for the `anthropic` PyPI package — directionally consistent with it being a major, actively-used official SDK, but the exact figure is not independently re-verified in this session
- WebSearch, theneuralbase.com / realpython.com excerpts on the `system` parameter as a top-level `messages.create()` argument (corroborates the official docs' own `system=` usage shown in the primary source)
- WebSearch on Anthropic's documented hallucination-reduction techniques (XML tag structuring, explicit "only use given facts" instructions) — general prompt-engineering guidance, not a phase-specific numeric guarantee; informs Pattern 1/2's prompt design as a best-effort mitigation, not a certainty

### Tertiary (LOW confidence)
- None used as load-bearing claims in this document — all LOW-confidence findings from WebSearch were either corroborated against the official docs fetch or explicitly flagged in the Assumptions Log rather than stated as fact.

## Metadata

**Confidence breakdown:**
- Standard stack (Anthropic SDK version, error/retry/timeout mechanics): HIGH — directly fetched from official current documentation, cross-checked against a live `pip index versions` call
- Package legitimacy: HIGH — official first-party Anthropic package, slopcheck scan clean, matches CLAUDE.md's explicit pin
- Architecture (typed-tuple pattern, schema migration, template assembly): HIGH — direct extension of this repo's own established, working Phase 1-2 patterns, plus live-verified facts about the actual current state of `db/outreach.db` and `.streamlit/secrets.toml`
- Prompt design / hallucination mitigation: MEDIUM — grounded in Anthropic's own documented best practices (XML tags, explicit fact-scoping), but inherently probabilistic; cannot be elevated to HIGH because no test can prove an LLM will never hallucinate, only that the mitigations recommended are the current state-of-the-art approach
- Sparse-title heuristic (Pattern 3) and D-16 threshold: LOW-to-MEDIUM, explicitly flagged in the Assumptions Log as planner/implementer-adjustable defaults, consistent with CONTEXT.md's own explicit deferral of these specifics to discretion

**Research date:** 2026-09-17
**Valid until:** 30 days for the SDK mechanics/error-handling sections (Anthropic's SDK interface is documented as stable across the 0.94.x→1.x line); re-verify sooner (7 days) if actual execution reveals prompt-grounding quality issues, since that portion of this research is inherently the least certain and most likely to need iteration during implementation.
