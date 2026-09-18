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


def test_update_draft_writes_status_drafted(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched, update_draft

    rows = [
        {
            "id": "apollo-1",
            "name": "Jamie Smith",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
        {
            "id": "apollo-2",
            "name": "Robin Lee",
            "organization_name": "Newcorp",
            "email": "robin@newcorp.com",
        },
    ]
    insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)

    update_draft(
        "apollo-1",
        "A grounded opener.",
        "ai",
        first_name="Jamie",
        db_path=tmp_db_path,
    )

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT opening_line, draft_source, first_name, status "
            "FROM prospect WHERE apollo_person_id = ?",
            ("apollo-1",),
        )
        opening_line, draft_source, first_name, status = cur.fetchone()

        cur.execute(
            "SELECT opening_line, draft_source, first_name, status "
            "FROM prospect WHERE apollo_person_id = ?",
            ("apollo-2",),
        )
        untouched = cur.fetchone()
    finally:
        conn.close()

    assert opening_line == "A grounded opener."
    assert draft_source == "ai"
    assert first_name == "Jamie"
    assert status == "drafted"

    untouched_opening_line, untouched_draft_source, untouched_first_name, untouched_status = untouched
    assert untouched_opening_line is None
    assert untouched_draft_source is None
    assert untouched_status == "enriched"


def test_insert_enriched_persists_title_and_names(tmp_db_path):
    """insert_enriched must persist title/first_name/last_name from a real
    bulk_match match dict shape (Phase 4 QUEUE-02 role column, Apollo
    contact-creation payload)."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched

    rows = [
        {
            "id": "match-1",
            "name": "Jamie Smith",
            "first_name": "Jamie",
            "last_name": "Smith",
            "title": "Head of Partnerships",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
    ]

    insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, first_name, last_name FROM prospect WHERE apollo_person_id = ?",
            ("match-1",),
        )
        title, first_name, last_name = cur.fetchone()
    finally:
        conn.close()

    assert title == "Head of Partnerships"
    assert first_name == "Jamie"
    assert last_name == "Smith"


def test_get_drafted_by_path(tmp_db_path):
    """get_drafted_by_path returns only the selected path's drafted rows,
    with all fields the Review Queue needs (Phase 4 QUEUE-01/QUEUE-02)."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import get_drafted_by_path, insert_enriched, update_draft

    club_rows = [
        {
            "id": "club-1",
            "name": "Jamie Smith",
            "first_name": "Jamie",
            "last_name": "Smith",
            "title": "Head of Partnerships",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
        {
            "id": "club-2",
            "name": "Robin Lee",
            "first_name": "Robin",
            "last_name": "Lee",
            "title": "Director",
            "organization_name": "Newcorp",
            "email": "robin@newcorp.com",
        },
        {
            "id": "club-3",
            "name": "Left Enriched",
            "first_name": "Left",
            "last_name": "Enriched",
            "title": "Manager",
            "organization_name": "Otherco",
            "email": "left@otherco.com",
        },
    ]
    productthon_rows = [
        {
            "id": "prod-1",
            "name": "Taylor Kim",
            "first_name": "Taylor",
            "last_name": "Kim",
            "title": "VP",
            "organization_name": "Prodco",
            "email": "taylor@prodco.com",
        },
    ]

    insert_enriched(club_rows, path="club_sponsorship", db_path=tmp_db_path)
    insert_enriched(productthon_rows, path="productthon", db_path=tmp_db_path)

    update_draft("club-1", "A grounded opener.", "ai", first_name="Jamie", db_path=tmp_db_path)
    update_draft("club-2", "Another opener.", "ai", first_name="Robin", db_path=tmp_db_path)
    update_draft("prod-1", "Productthon opener.", "ai", first_name="Taylor", db_path=tmp_db_path)
    # club-3 intentionally left at status='enriched' (not advanced to drafted).

    result = get_drafted_by_path("club_sponsorship", db_path=tmp_db_path)

    assert len(result) == 2
    names = {row["name"] for row in result}
    assert names == {"Jamie Smith", "Robin Lee"}

    expected_keys = {
        "id",
        "name",
        "first_name",
        "last_name",
        "company",
        "company_domain",
        "email",
        "title",
        "path",
        "opening_line",
    }
    for row in result:
        assert expected_keys <= set(row.keys())
        assert row["path"] == "club_sponsorship"


def test_get_drafted_by_path_empty(tmp_db_path):
    """A path with no drafted rows returns an empty list, never None/raises."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import get_drafted_by_path

    result = get_drafted_by_path("client_sourcing", db_path=tmp_db_path)

    assert result == []


def test_mark_contact_created(tmp_db_path):
    """mark_contact_created writes apollo_contact_id + status='contact_created'
    and the row becomes visible in contacted_registry (Phase 4 dedup-registry
    success criterion)."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched, mark_contact_created

    rows = [
        {
            "id": "match-1",
            "name": "Jamie Smith",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
    ]
    insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM prospect WHERE apollo_person_id = ?", ("match-1",))
        prospect_id = cur.fetchone()[0]
    finally:
        conn.close()

    mark_contact_created(prospect_id, "apollo-contact-123", db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, apollo_contact_id FROM prospect WHERE id = ?", (prospect_id,)
        )
        status, apollo_contact_id = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM contacted_registry WHERE id = ?", (prospect_id,))
        registry_count = cur.fetchone()[0]
    finally:
        conn.close()

    assert status == "contact_created"
    assert apollo_contact_id == "apollo-contact-123"
    assert registry_count == 1


def test_mark_sequenced_only_affects_selected(tmp_db_path):
    """mark_sequenced advances only the targeted prospect id; every other
    submitted prospect stays untouched at its prior status."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import insert_enriched, mark_sequenced, update_draft

    rows = [
        {
            "id": "apollo-1",
            "name": "Jamie Smith",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
        {
            "id": "apollo-2",
            "name": "Robin Lee",
            "organization_name": "Newcorp",
            "email": "robin@newcorp.com",
        },
    ]
    insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)
    update_draft("apollo-1", "Opener one.", "ai", db_path=tmp_db_path)
    update_draft("apollo-2", "Opener two.", "ai", db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM prospect WHERE apollo_person_id = ?", ("apollo-1",))
        prospect_id_1 = cur.fetchone()[0]
        cur.execute("SELECT id FROM prospect WHERE apollo_person_id = ?", ("apollo-2",))
        prospect_id_2 = cur.fetchone()[0]
    finally:
        conn.close()

    mark_sequenced(prospect_id_1, db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM prospect WHERE id = ?", (prospect_id_1,))
        status_1 = cur.fetchone()[0]
        cur.execute("SELECT status FROM prospect WHERE id = ?", (prospect_id_2,))
        status_2 = cur.fetchone()[0]
    finally:
        conn.close()

    assert status_1 == "sequenced"
    assert status_2 == "drafted"


def test_partial_enrollment_leaves_skipped_drafted(tmp_db_path):
    """D-08 retry guarantee: applying mark_contact_created + mark_sequenced
    only for the enrolled prospect leaves the skipped prospect at 'drafted'
    with no apollo_contact_id, absent from contacted_registry, and still
    returned by get_drafted_by_path."""
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.prospects import (
        get_drafted_by_path,
        insert_enriched,
        mark_contact_created,
        mark_sequenced,
        update_draft,
    )

    rows = [
        {
            "id": "apollo-1",
            "name": "Jamie Smith",
            "organization_name": "Acme Co",
            "email": "jamie@acme.com",
        },
        {
            "id": "apollo-2",
            "name": "Robin Lee",
            "organization_name": "Newcorp",
            "email": "robin@newcorp.com",
        },
    ]
    insert_enriched(rows, path="club_sponsorship", db_path=tmp_db_path)
    update_draft("apollo-1", "Opener one.", "ai", db_path=tmp_db_path)
    update_draft("apollo-2", "Opener two.", "ai", db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM prospect WHERE apollo_person_id = ?", ("apollo-1",))
        enrolled_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM prospect WHERE apollo_person_id = ?", ("apollo-2",))
        skipped_id = cur.fetchone()[0]
    finally:
        conn.close()

    # Confirmed-only write order: mark_contact_created + mark_sequenced for
    # the ENROLLED prospect id only; no DB call at all for the skipped one.
    mark_contact_created(enrolled_id, "apollo-contact-enrolled", db_path=tmp_db_path)
    mark_sequenced(enrolled_id, db_path=tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, apollo_contact_id FROM prospect WHERE id = ?", (enrolled_id,)
        )
        enrolled_status, enrolled_contact_id = cur.fetchone()
        cur.execute(
            "SELECT status, apollo_contact_id FROM prospect WHERE id = ?", (skipped_id,)
        )
        skipped_status, skipped_contact_id = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM contacted_registry WHERE id = ?", (enrolled_id,))
        enrolled_in_registry = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM contacted_registry WHERE id = ?", (skipped_id,))
        skipped_in_registry = cur.fetchone()[0]
    finally:
        conn.close()

    assert enrolled_status == "sequenced"
    assert enrolled_contact_id == "apollo-contact-enrolled"
    assert enrolled_in_registry == 1

    assert skipped_status == "drafted"
    assert skipped_contact_id is None
    assert skipped_in_registry == 0

    remaining_drafted = get_drafted_by_path("club_sponsorship", db_path=tmp_db_path)
    remaining_ids = {row["id"] for row in remaining_drafted}
    assert skipped_id in remaining_ids
    assert enrolled_id not in remaining_ids
