"""RED tests for merge-field validation, override-aware assembly, and the
template_override store (db/templates_store.py, not yet implemented;
personalization/templates.py's validate_template_fields, not yet added).

Imports are performed inside each test body so `pytest --collect-only`
succeeds before these functions exist, matching every other RED-test file's
stated convention in this repo (tests/test_apollo_client.py,
tests/test_prospects.py).

Pure-function tests (validate_template_fields, assemble_email) take no
fixtures; store tests use the tmp_db_path fixture from tests/conftest.py.
"""


def test_validate_template_fields_all_present():
    from personalization.templates import validate_template_fields

    ok, message = validate_template_fields(
        "{company}", "Hi {first_name}! {opening_line} About {company}."
    )
    assert ok is True
    assert message == "OK"


def test_validate_template_fields_missing_field():
    from personalization.templates import validate_template_fields

    ok, message = validate_template_fields(
        "Hi from {company}", "Hi {first_name}, thanks for your time. {company}."
    )
    assert ok is False
    assert "opening_line" in message


def test_validate_template_fields_counts_subject_and_body_together():
    from personalization.templates import validate_template_fields

    ok, message = validate_template_fields(
        "Hi {opening_line}", "Hi {first_name}! About {company}."
    )
    assert ok is True
    assert message == "OK"


def test_validate_template_fields_rejects_unknown_field():
    from personalization.templates import validate_template_fields

    ok, message = validate_template_fields(
        "{company}",
        "Hi {first_name}! {opening_line} About {company}, {last_name}.",
    )
    assert ok is False
    assert "last_name" in message


def test_assemble_email_uses_override_templates():
    from personalization.templates import assemble_email

    subject, body = assemble_email(
        "club_sponsorship",
        "Jamie",
        "Acme",
        "Opener.",
        subject_template="Hi from {company}",
        body_template="Hey {first_name}! {opening_line} — about {company}.",
    )
    assert subject == "Hi from Acme"
    assert body == "Hey Jamie! Opener. — about Acme."


def test_assemble_email_default_unchanged():
    from personalization.templates import PATH_TEMPLATES, assemble_email

    subject, body = assemble_email("club_sponsorship", "Jamie", "Acme", "Opener.")
    assert subject == PATH_TEMPLATES["club_sponsorship"]["subject"].format(
        first_name="Jamie", company="Acme", opening_line="Opener."
    )


def test_get_template_falls_back_to_path_templates(tmp_db_path):
    import sqlite3

    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.templates_store import get_template
    from personalization.templates import PATH_TEMPLATES

    subject, body = get_template("productthon", db_path=tmp_db_path)
    assert subject == PATH_TEMPLATES["productthon"]["subject"]
    assert body == PATH_TEMPLATES["productthon"]["body"]

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM template_override")
        count = cur.fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_save_template_override_roundtrip_and_upsert(tmp_db_path):
    import sqlite3

    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.templates_store import get_template, save_template_override

    save_template_override("club_sponsorship", "S1", "B1", db_path=tmp_db_path)
    subject, body = get_template("club_sponsorship", db_path=tmp_db_path)
    assert (subject, body) == ("S1", "B1")

    save_template_override("club_sponsorship", "S2", "B2", db_path=tmp_db_path)
    subject, body = get_template("club_sponsorship", db_path=tmp_db_path)
    assert (subject, body) == ("S2", "B2")

    conn = sqlite3.connect(tmp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM template_override WHERE path = ?",
            ("club_sponsorship",),
        )
        count = cur.fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_save_template_override_is_path_scoped(tmp_db_path):
    from db.schema import ensure_schema

    ensure_schema(tmp_db_path)

    from db.templates_store import get_template, save_template_override
    from personalization.templates import PATH_TEMPLATES

    save_template_override("club_sponsorship", "S1", "B1", db_path=tmp_db_path)

    subject, body = get_template("client_sourcing", db_path=tmp_db_path)
    assert subject == PATH_TEMPLATES["client_sourcing"]["subject"]
    assert body == PATH_TEMPLATES["client_sourcing"]["body"]
