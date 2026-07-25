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
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        count = 0
        for match in rows:
            name = match.get("name")
            organization = match.get("organization") or {}
            company = match.get("organization_name") or organization.get("name")
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
