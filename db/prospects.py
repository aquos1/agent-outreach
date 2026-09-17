"""Dedup query against contacted_registry + enriched-row insert (DEDUP-02).

Follows db/schema.py's connection lifecycle convention exactly: a fresh
sqlite3.connect() per call, wrapped in try/finally so the connection always
closes. All SQL uses `?` placeholders exclusively — never f-string/`.format`/
`%` interpolation of Apollo-derived or user free-text values into SQL
(Phase 1 Security Domain rule, T-02-01).
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
    Commits once after all rows are staged; returns the number inserted.

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

            company_domain = _domain_from_url(organization.get("website_url"))
            if not company_domain:
                company_domain = _domain_from_email(email)

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
