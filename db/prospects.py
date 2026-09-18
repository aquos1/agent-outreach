"""Dedup query against contacted_registry + enriched-row insert (DEDUP-02).

Follows db/schema.py's connection lifecycle convention exactly: a fresh
sqlite3.connect() per call, wrapped in try/finally so the connection always
closes. All SQL uses `?` placeholders exclusively — never f-string/`.format`/
`%` interpolation of Apollo-derived or user free-text values into SQL
(Phase 1 Security Domain rule, T-02-01).

Phase 4 adds get_drafted_by_path() (the Review Queue's QUEUE-01 source query)
and the two enrollment-engine status transitions, mark_contact_created() and
mark_sequenced() — both must be called only for prospects review/logic.py's
split_enrollment_outcome() confirms Apollo actually enrolled (D-07/D-08); see
each function's own docstring for the exact call-order rule.
"""
from __future__ import annotations

import sqlite3
from urllib.parse import urlparse


def _domain_from_url(url: str | None) -> str | None:
    """Parse a bare, lowercased registrable domain out of a URL.

    Uses urllib.parse (stdlib) rather than a hand-rolled regex (RESEARCH.md
    Don't Hand-Roll table). Returns None on falsy/unparseable input.
    """
    if not url:
        return None
    netloc = urlparse(url).netloc
    if not netloc:
        return None
    return netloc.removeprefix("www.").lower() or None


def _domain_from_email(email: str | None) -> str | None:
    """Fallback domain derivation from an email address, e.g. 'a@acme.com' -> 'acme.com'."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain or None


def dedup_filter(candidates: list[dict], db_path: str = "db/outreach.db") -> list[dict]:
    """Exclude candidates already present in contacted_registry (DEDUP-02).

    Id-level dedup always applies (candidate.get("id") vs known
    apollo_person_id values). Domain-level dedup only applies where the
    registry's dedupable_domain is non-NULL — a free-email domain (e.g.
    gmail.com) never causes a domain-level exclusion, since
    contacted_registry already NULLs dedupable_domain for those rows.

    CONFIRMED (02-03 live human-verify, 2026-09-11): live
    `mixed_people/api_search` results never carry `organization.website_url`
    at this pre-enrichment stage (see apollo/client.py::_domain_from_org),
    so `candidate_domain` below will always evaluate to None against real
    search data — domain-level dedup at this call site only fires in tests
    that seed a synthetic `website_url`. This is the exact degradation
    Assumption A4 predicted: id-level dedup is the one guarantee that holds
    pre-enrichment against live data; domain-level dedup effectively only
    applies post-enrichment (once real `organization.website_url` is present
    on enriched match rows, per insert_enriched below).
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT apollo_person_id, dedupable_domain FROM contacted_registry")
        rows = cur.fetchall()
    finally:
        conn.close()

    known_ids = {row[0] for row in rows if row[0]}
    known_domains = {row[1] for row in rows if row[1]}

    survivors = []
    for candidate in candidates:
        candidate_id = candidate.get("id")
        organization = candidate.get("organization") or {}
        candidate_domain = _domain_from_url(organization.get("website_url"))

        if candidate_id in known_ids:
            continue
        if candidate_domain is not None and candidate_domain in known_domains:
            continue
        survivors.append(candidate)

    return survivors


def insert_enriched(
    rows: list[dict], path: str, db_path: str = "db/outreach.db"
) -> int:
    """Insert enriched match rows into prospect with status='enriched'.

    Every field access on Apollo-derived match dicts uses `.get()`
    defensively. company_domain is derived from the match's organization
    website_url when present, falling back to the email domain otherwise.
    Also persists title, first_name, and last_name (Phase 4: title backs
    QUEUE-02's role column, last_name backs Apollo contact-creation;
    update_draft later overwrites first_name with the same value, which is
    harmless). Commits once after all rows are staged; returns the number
    inserted.

    CONFIRMED (02-03 live human-verify, 2026-09-11): a real `bulk_match`
    match's `organization.website_url` is present and populated (unlike the
    pre-enrichment search-stage organization — see dedup_filter above), so
    the company_domain derivation below is confirmed correct as written. The
    `organization_name` flat-string field assumed in RESEARCH.md A2 does NOT
    exist live — the real shape nests the name under `organization.name`
    (a dict), same as the search response. `company` below is reconciled to
    try the confirmed-real `organization.name` first, keeping
    `match.get("organization_name")` only as a defensive fallback in case
    Apollo ever adds that flat field.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        count = 0
        for match in rows:
            name = match.get("name")
            organization = match.get("organization") or {}
            company = organization.get("name") or match.get("organization_name")
            email = match.get("email")
            apollo_person_id = match.get("id")
            title = match.get("title")
            first_name = match.get("first_name")
            last_name = match.get("last_name")

            company_domain = _domain_from_url(organization.get("website_url"))
            if not company_domain:
                company_domain = _domain_from_email(email)

            cur.execute(
                "INSERT INTO prospect "
                "(name, company, company_domain, apollo_person_id, email, path, "
                "status, title, first_name, last_name) "
                "VALUES (?, ?, ?, ?, ?, ?, 'enriched', ?, ?, ?)",
                (
                    name,
                    company,
                    company_domain,
                    apollo_person_id,
                    email,
                    path,
                    title,
                    first_name,
                    last_name,
                ),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


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


def get_drafted_by_path(
    path_slug: str, db_path: str = "db/outreach.db"
) -> list[dict]:
    """Return every status='drafted' prospect for path_slug, as plain dicts.

    This is the Review Queue's source query (QUEUE-01): a teammate must see
    every drafted contact for the selected path, with nothing withheld.
    Skipped contacts (Phase 4's later Approve flow, D-08) intentionally stay
    visible here too, since they remain at status='drafted' and this query
    has no awareness of "skipped" as a separate state.

    Follows dedup_filter's connection lifecycle exactly: connect -> execute
    -> fetchall inside try/finally, transform into plain dicts outside the
    connection block.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, first_name, last_name, company, company_domain, "
            "email, title, path, opening_line FROM prospect "
            "WHERE status = 'drafted' AND path = ? ORDER BY id",
            (path_slug,),
        )
        rows = cur.fetchall()
        columns = [description[0] for description in cur.description]
    finally:
        conn.close()

    return [dict(zip(columns, row)) for row in rows]


def mark_contact_created(
    prospect_id: int, apollo_contact_id: str, db_path: str = "db/outreach.db"
) -> None:
    """Record a newly-created (or matched-existing) Apollo contact id and
    advance the prospect to status='contact_created'.

    Writing apollo_contact_id here is what adds the row to
    contacted_registry — the view filters on apollo_contact_id IS NOT NULL —
    satisfying the phase's dedup-registry success criterion. Keys on the
    internal `id` primary key (not apollo_person_id) because the caller
    already holds the internal id from map_created_contacts.

    CALL-ORDER RULE (D-08): invoke this ONLY for prospects that
    split_enrollment_outcome confirmed as enrolled, never for the whole
    submitted batch. Advancing a skipped contact past 'drafted' would drop it
    out of get_drafted_by_path (breaking the retry guarantee) and would
    wrongly add an un-contacted person to the dedup registry.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prospect SET "
            "apollo_contact_id = ?, status = 'contact_created', "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (apollo_contact_id, prospect_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_sequenced(prospect_id: int, db_path: str = "db/outreach.db") -> None:
    """Advance a prospect to status='sequenced' after confirmed Apollo enrollment.

    CALLERS MAY ONLY INVOKE THIS for prospect ids returned in
    split_enrollment_outcome's enrolled list — NEVER in a blanket loop over
    everything submitted in a batch. Calling this for a skipped contact
    silently removes it from the retryable `status='drafted'` queue,
    violating D-08 (04-RESEARCH.md Pitfall 5).
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prospect SET status = 'sequenced', "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (prospect_id,),
        )
        conn.commit()
    finally:
        conn.close()
