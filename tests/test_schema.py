"""RED tests for DEDUP-01 schema behavior (db/schema.py, not yet implemented).

Imports are performed inside each test body so `pytest --collect-only` succeeds
before db/schema.py exists (Plan 01-02 implements it).
"""
import sqlite3


def test_ensure_schema_idempotent(tmp_db_path):
    """ensure_schema() creates prospect, email_events, free_email_domains tables
    and the contacted_registry view, and can be called twice without error."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)
    # Second call must not raise (idempotent bootstrap — see Pitfall 3 in RESEARCH.md)
    ensure_schema(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('prospect', 'email_events', 'free_email_domains', 'template_override')"
        )
        table_names = {row[0] for row in cur.fetchall()}
        assert table_names == {
            "prospect",
            "email_events",
            "free_email_domains",
            "template_override",
        }

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name='contacted_registry'"
        )
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_template_override_roundtrip(tmp_db_path):
    """template_override rows survive a reconnect, and a second ensure_schema()
    call neither raises nor drops existing rows (Phase 4 D-05, brand-new table)."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        conn.execute(
            "INSERT INTO template_override (path, subject, body) VALUES (?, ?, ?)",
            ("club_sponsorship", "S", "B"),
        )
        conn.commit()
    finally:
        conn.close()

    # Second ensure_schema() call must not raise and must not drop the row.
    ensure_schema(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT subject, body FROM template_override WHERE path = ?",
            ("club_sponsorship",),
        )
        row = cur.fetchone()
        assert row == ("S", "B")
    finally:
        conn.close()


def test_registry_excludes_free_domains(tmp_db_path):
    """contacted_registry view nulls dedupable_domain for seeded free-email domains
    and passes through company-owned domains."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prospect (name, company_domain, apollo_contact_id, status) "
            "VALUES (?, ?, ?, 'contact_created')",
            ("Free Domain Contact", "gmail.com", "apollo-contact-1"),
        )
        cur.execute(
            "INSERT INTO prospect (name, company_domain, apollo_contact_id, status) "
            "VALUES (?, ?, ?, 'contact_created')",
            ("Company Domain Contact", "acme.com", "apollo-contact-2"),
        )
        conn.commit()

        cur.execute(
            "SELECT company_domain, dedupable_domain FROM contacted_registry "
            "WHERE apollo_contact_id = ?",
            ("apollo-contact-1",),
        )
        row = cur.fetchone()
        assert row[0] == "gmail.com"
        assert row[1] is None

        cur.execute(
            "SELECT company_domain, dedupable_domain FROM contacted_registry "
            "WHERE apollo_contact_id = ?",
            ("apollo-contact-2",),
        )
        row = cur.fetchone()
        assert row[0] == "acme.com"
        assert row[1] == "acme.com"
    finally:
        conn.close()


def test_persistence_across_reconnect(tmp_db_path):
    """Prospect rows written before an app 'restart' (fresh sqlite3.connect() to the
    same file) are still queryable afterward."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    conn1 = sqlite3.connect(tmp_db_path)
    try:
        conn1.execute(
            "INSERT INTO prospect (name, company_domain, status) VALUES (?, ?, 'found')",
            ("Reconnect Test Contact", "example.com"),
        )
        conn1.commit()
    finally:
        conn1.close()

    # Simulate an app restart: brand-new connection to the same file.
    conn2 = sqlite3.connect(tmp_db_path)
    try:
        cur = conn2.cursor()
        cur.execute("SELECT name FROM prospect WHERE name = ?", ("Reconnect Test Contact",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Reconnect Test Contact"
    finally:
        conn2.close()


def test_column_migration_idempotent(tmp_db_path):
    """ensure_schema() must retroactively add opening_line/first_name/draft_source
    columns onto a pre-existing prospect table that predates Phase 3 (RESEARCH.md
    Pitfall 1) -- CREATE TABLE IF NOT EXISTS alone would silently no-op."""
    conn = sqlite3.connect(tmp_db_path)
    try:
        conn.execute(
            """
            CREATE TABLE prospect (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                company             TEXT,
                company_domain      TEXT,
                apollo_person_id    TEXT,
                apollo_contact_id   TEXT,
                email               TEXT,
                path                TEXT,
                status              TEXT NOT NULL DEFAULT 'found'
                                    CHECK (status IN (
                                        'found','selected','enriched',
                                        'contact_created','drafted','approved','sequenced'
                                    )),
                sequence_id         TEXT,
                created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO prospect (name, company_domain, status) VALUES (?, ?, 'enriched')",
            ("Pre-Migration Contact", "acme.com"),
        )
        conn.commit()
    finally:
        conn.close()

    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)
    ensure_schema(tmp_db_path)  # second call must not raise

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(prospect)")
        column_names = {row[1] for row in cur.fetchall()}
        assert {
            "opening_line",
            "first_name",
            "draft_source",
            "title",
            "last_name",
        } <= column_names

        cur.execute("SELECT COUNT(*) FROM prospect")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()
