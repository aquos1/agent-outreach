"""RED tests for review/logic.py (not yet implemented).

Pure-function test style matching tests/test_discovery_logic.py's convention —
no requests, no sqlite3, no streamlit; every function is a deterministic
transform over plain dicts (Phase 4 QUEUE-04, D-07, D-08, D-16).
"""


def test_build_contact_payloads_maps_fields():
    from review.logic import build_contact_payloads

    rows = [
        {
            "id": 1,
            "first_name": "Jamie",
            "last_name": "Smith",
            "name": "Jamie Smith",
            "email": "jamie@acme.com",
            "company": "Acme Co",
            "title": "Head of Partnerships",
            "opening_line": "Loved your launch.",
        }
    ]

    payloads = build_contact_payloads(rows)

    assert len(payloads) == 1
    entry = payloads[0]
    assert entry["first_name"] == "Jamie"
    assert entry["last_name"] == "Smith"
    assert entry["email"] == "jamie@acme.com"
    assert entry["organization_name"] == "Acme Co"
    assert entry["title"] == "Head of Partnerships"
    assert entry["opening_line"] == "Loved your launch."
    assert set(entry.keys()) == {
        "first_name",
        "last_name",
        "email",
        "organization_name",
        "title",
        "opening_line",
    }


def test_build_contact_payloads_null_opening_line_yields_empty_string():
    from review.logic import build_contact_payloads

    rows = [
        {
            "id": 1,
            "first_name": "Jamie",
            "last_name": "Smith",
            "name": "Jamie Smith",
            "email": "jamie@acme.com",
            "company": "Acme Co",
            "title": "Head",
            "opening_line": None,
        }
    ]

    payloads = build_contact_payloads(rows)

    assert payloads[0]["opening_line"] == ""


def test_build_contact_payloads_derives_missing_names():
    from review.logic import build_contact_payloads

    rows = [
        {
            "id": 1,
            "first_name": None,
            "last_name": None,
            "name": "Jamie Smith",
            "email": "jamie@acme.com",
            "company": "Acme Co",
            "title": "Head",
            "opening_line": "Hi.",
        },
        {
            "id": 2,
            "first_name": None,
            "last_name": None,
            "name": "Cher",
            "email": "cher@acme.com",
            "company": "Acme Co",
            "title": "Lead",
            "opening_line": "Hi.",
        },
    ]

    payloads = build_contact_payloads(rows)

    assert payloads[0]["first_name"] == "Jamie"
    assert payloads[0]["last_name"] == "Smith"
    assert payloads[1]["first_name"] == "Cher"
    assert payloads[1]["last_name"] == ""


def test_build_contact_payloads_skips_rows_without_email():
    from review.logic import build_contact_payloads

    rows = [
        {
            "id": 1,
            "first_name": "Jamie",
            "last_name": "Smith",
            "name": "Jamie Smith",
            "email": None,
            "company": "Acme Co",
            "title": "Head",
            "opening_line": "Hi.",
        },
        {
            "id": 2,
            "first_name": "Cher",
            "last_name": "Lee",
            "name": "Cher Lee",
            "email": "cher@acme.com",
            "company": "Acme Co",
            "title": "Lead",
            "opening_line": "Hi.",
        },
    ]

    payloads = build_contact_payloads(rows)

    assert len(payloads) == 1
    assert payloads[0]["email"] == "cher@acme.com"


def test_map_created_contacts_matches_by_email_not_position():
    from review.logic import map_created_contacts

    rows = [
        {"id": 1, "email": "jamie@acme.com"},
        {"id": 2, "email": "cher@acme.com"},
    ]
    # Response entries are in REVERSE order vs. the input rows.
    response = {
        "created_contacts": [{"id": "c2", "email": "CHER@acme.com"}],
        "existing_contacts": [{"id": "c1", "email": "jamie@acme.com"}],
    }

    result = map_created_contacts(response, rows)

    assert result == {1: "c1", 2: "c2"}


def test_map_created_contacts_ignores_unknown_emails():
    from review.logic import map_created_contacts

    rows = [{"id": 1, "email": "jamie@acme.com"}]
    response = {
        "created_contacts": [{"id": "c1", "email": "jamie@acme.com"}],
        "existing_contacts": [{"id": "c9", "email": "unknown@nowhere.com"}],
    }

    result = map_created_contacts(response, rows)

    assert result == {1: "c1"}


def test_split_enrollment_outcome_enrolled_and_skipped():
    from review.logic import split_enrollment_outcome

    response = {
        "contacts": [{"id": "c1"}],
        "skipped_contact_ids": {"c2": "contacts_active_in_other_campaigns"},
    }
    contact_to_prospect = {"c1": 1, "c2": 2}

    enrolled, skipped = split_enrollment_outcome(response, contact_to_prospect)

    assert enrolled == [1]
    assert skipped == [(2, "contacts_active_in_other_campaigns")]


def test_split_enrollment_outcome_unconfirmed_counts_as_skipped():
    from review.logic import split_enrollment_outcome

    response = {"contacts": [], "skipped_contact_ids": {}}
    contact_to_prospect = {"c1": 1}

    enrolled, skipped = split_enrollment_outcome(response, contact_to_prospect)

    assert enrolled == []
    assert len(skipped) == 1
    prospect_id, reason = skipped[0]
    assert prospect_id == 1
    assert isinstance(reason, str) and reason


def test_split_enrollment_outcome_empty_body_enrolls_nobody():
    from review.logic import split_enrollment_outcome

    response = {"contacts": [], "skipped_contact_ids": {}}
    contact_to_prospect = {"c1": 1, "c2": 2}

    enrolled, skipped = split_enrollment_outcome(response, contact_to_prospect)

    assert enrolled == []
    assert len(skipped) == 2
    assert {p_id for p_id, _reason in skipped} == {1, 2}


def test_split_enrollment_outcome_tolerates_list_skipped():
    from review.logic import split_enrollment_outcome

    response = {"contacts": [], "skipped_contact_ids": ["c1"]}
    contact_to_prospect = {"c1": 1}

    enrolled, skipped = split_enrollment_outcome(response, contact_to_prospect)

    assert enrolled == []
    assert len(skipped) == 1
    prospect_id, reason = skipped[0]
    assert prospect_id == 1
    assert isinstance(reason, str) and reason
