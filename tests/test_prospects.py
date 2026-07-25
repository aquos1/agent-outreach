"""RED tests for dedup + insert logic (db/prospects.py, not yet implemented).

Imports are performed inside each test body so `pytest --collect-only` succeeds
before db/prospects.py exists (Plan 02-01 implements it). Every test seeds a
real schema via ensure_schema(tmp_db_path) rather than mocking the database.
"""
import sqlite3


def test_dedup_filter_excludes_known_contacts(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        # A previously-contacted person, dedupable by Apollo person id.
        conn.execute(
            "INSERT INTO prospect (name, company_domain, apollo_person_id, "
            "apollo_contact_id, status) VALUES (?, ?, ?, ?, 'contact_created')",
            ("Known Person", "othercorp.com", "known-person-id", "apollo-contact-1"),
        )
        # A previously-contacted company, dedupable by company domain (acme.com).
        conn.execute(
            "INSERT INTO prospect (name, company_domain, apollo_person_id, "
            "apollo_contact_id, status) VALUES (?, ?, ?, ?, 'contact_created')",
            ("Known Domain Contact", "acme.com", "some-other-id", "apollo-contact-2"),
        )
        # A previously-contacted person at a free-email domain — must NEVER
        # cause domain-level exclusion (dedupable_domain is NULL for gmail.com).
        conn.execute(
            "INSERT INTO prospect (name, company_domain, apollo_person_id, "
            "apollo_contact_id, status) VALUES (?, ?, ?, ?, 'contact_created')",
            ("Free Domain Contact", "gmail.com", "free-domain-id", "apollo-contact-3"),
        )
        conn.commit()
    finally:
        conn.close()

    from db.prospects import dedup_filter

    candidates = [
        # Excluded: known apollo person id.
        {
            "id": "known-person-id",
            "organization": {"website_url": "https://newcorp.com"},
        },
        # Excluded: known company domain (acme.com), different person id.
        {
            "id": "brand-new-id-1",
            "organization": {"website_url": "https://www.acme.com"},
        },
        # NOT excluded: shares a "known" domain that is actually a free-email
        # domain (gmail.com never dedups on domain, only by id).
        {
            "id": "brand-new-id-2",
            "organization": {"website_url": "https://gmail.com"},
        },
        # Genuinely new candidate — must survive.
        {
            "id": "genuinely-new-id",
            "organization": {"website_url": "https://newventure.io"},
        },
    ]

    result = dedup_filter(candidates, db_path=tmp_db_path)
    result_ids = {c["id"] for c in result}

    assert "known-person-id" not in result_ids
    assert "brand-new-id-1" not in result_ids
    assert "brand-new-id-2" in result_ids
    assert "genuinely-new-id" in result_ids
    assert result_ids == {"brand-new-id-2", "genuinely-new-id"}


def test_insert_enriched_writes_enriched_status(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched

    rows = [
        {
            "id": "match-1",
            "name": "Jamie Smith",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
        {
            "id": "match-2",
            "name": "Robin Lee",
            "organization_name": "Newcorp",
            "email": "robin@newcorp.com",
        },
    ]

    count = insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)
    assert count == 2

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name, email, apollo_person_id, company_domain, path, status "
            "FROM prospect ORDER BY name"
        )
        inserted = cur.fetchall()
    finally:
        conn.close()

    assert len(inserted) == 2
    for name, email, apollo_person_id, company_domain, path, status in inserted:
        assert status == "enriched"
        assert email
        assert apollo_person_id
        assert company_domain
        assert path == "club_sponsorship"
