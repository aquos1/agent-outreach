"""Idempotent SQLite schema bootstrap for the dedup registry (DEDUP-01).

ensure_schema() creates the prospect, email_events, and free_email_domains
tables (if they don't already exist), seeds the free-email-domain exclusion
list, and can be called on every app boot without raising on a pre-existing
database file.
"""
from __future__ import annotations

import os
import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS prospect (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    company             TEXT,
    company_domain      TEXT,               -- lowercased registrable domain, e.g. "acme.com"
    apollo_person_id    TEXT,                -- id from mixed_people/api_search (pre-enrichment)
    apollo_contact_id   TEXT,                -- id from /contacts, set only once converted
    email               TEXT,
    path                TEXT,                -- 'club_sponsorship' | 'productthon' | 'client_sourcing'
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
    event_type          TEXT NOT NULL,       -- 'sent' | 'opened' | 'replied' | 'bounced' | 'unsubscribed'
    occurred_at         TIMESTAMP,
    raw_payload         TEXT,                -- JSON blob; Apollo stats schema is under-documented -
                                              -- store raw response for forward-compat
    polled_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS free_email_domains (
    domain TEXT PRIMARY KEY
);
INSERT OR IGNORE INTO free_email_domains (domain) VALUES
    ('gmail.com'), ('outlook.com'), ('yahoo.com'), ('hotmail.com'), ('icloud.com');
"""

# Views must be dropped and recreated explicitly on every boot — SQLite's
# CREATE VIEW IF NOT EXISTS support is inconsistent for views over schema
# objects that may evolve (RESEARCH.md Pitfall 3).
VIEW_DDL = """
DROP VIEW IF EXISTS contacted_registry;
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
WHERE p.apollo_contact_id IS NOT NULL;   -- only rows that reached "contact_created" or later
"""


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
