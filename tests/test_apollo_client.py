"""RED tests for Apollo health checks (apollo/client.py, not yet implemented).

Imports are performed inside the test body so `pytest --collect-only` succeeds
before apollo/client.py exists (Plan 01-03 implements it).

Plan 02-02 extends this file with RED tests for search_people, bulk_match_people,
and enrich_candidates (DISC-03) — new functions POST rather than GET, so these
tests monkeypatch requests.post instead of requests.get.
"""
import time

import requests


def test_check_apollo_health(monkeypatch, mock_requests_response):
    from apollo.client import check_apollo_health

    # 401 -> invalid/missing key
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: mock_requests_response(401, {})
    )
    ok, message = check_apollo_health("bad-key")
    assert ok is False
    assert isinstance(message, str) and message

    # 403 -> not a master key
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: mock_requests_response(403, {})
    )
    ok, message = check_apollo_health("non-master-key")
    assert ok is False
    assert isinstance(message, str) and message

    # 200 with is_logged_in: true -> healthy
    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **k: mock_requests_response(200, {"is_logged_in": True}),
    )
    ok, message = check_apollo_health("good-key")
    assert ok is True
    assert isinstance(message, str) and message


def test_search_people_error_codes(monkeypatch, mock_requests_response):
    from apollo.client import search_people

    # never sleep for real during 429 backoff testing
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    # 401 -> (None, msg)
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: mock_requests_response(401, {})
    )
    people, message = search_people("bad-key", ["director"], ["software"])
    assert people is None
    assert isinstance(message, str) and message

    # 403 -> (None, msg)
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: mock_requests_response(403, {})
    )
    people, message = search_people("non-master-key", ["director"], ["software"])
    assert people is None
    assert isinstance(message, str) and message

    # 429 (all retries exhausted) -> (None, msg)
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: mock_requests_response(429, {})
    )
    people, message = search_people("good-key", ["director"], ["software"])
    assert people is None
    assert isinstance(message, str) and message

    # 200 with {"people":[...]} -> (list, "OK"); returns the list defensively
    # even when total_entries is absent from the response.
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: mock_requests_response(
            200, {"people": [{"id": "p1"}, {"id": "p2"}]}
        ),
    )
    people, message = search_people("good-key", ["director"], ["software"])
    assert people == [{"id": "p1"}, {"id": "p2"}]
    assert message == "OK"


def test_search_people_never_raises_on_network(monkeypatch):
    from apollo.client import search_people

    def _raise(*a, **k):
        raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "post", _raise)
    people, message = search_people("good-key", ["director"], ["software"])
    assert people is None
    assert isinstance(message, str) and message


def test_bulk_match_people_error_codes(monkeypatch, mock_requests_response):
    from apollo.client import bulk_match_people

    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    details = [{"id": "p1", "first_name": "Jane", "organization_name": "Acme"}]

    # 401 -> (None, msg)
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: mock_requests_response(401, {})
    )
    matches, message = bulk_match_people("bad-key", details)
    assert matches is None
    assert isinstance(message, str) and message

    # 403 -> (None, msg)
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: mock_requests_response(403, {})
    )
    matches, message = bulk_match_people("non-master-key", details)
    assert matches is None
    assert isinstance(message, str) and message

    # 429 (all retries exhausted) -> (None, msg)
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: mock_requests_response(429, {})
    )
    matches, message = bulk_match_people("good-key", details)
    assert matches is None
    assert isinstance(message, str) and message

    # 422 -> (None, msg) surfacing Apollo's own message text (UI-SPEC "Enrichment
    # failure ... (422)")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: mock_requests_response(
            422, {"message": "organization_name is required"}
        ),
    )
    matches, message = bulk_match_people("good-key", details)
    assert matches is None
    assert isinstance(message, str) and "organization_name is required" in message

    # 200 with {"matches":[...]} -> (list, "OK")
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: mock_requests_response(200, {"matches": [{"id": "p1"}]}),
    )
    matches, message = bulk_match_people("good-key", details)
    assert matches == [{"id": "p1"}]
    assert message == "OK"


def test_create_contacts_bulk_error_codes(monkeypatch, mock_requests_response):
    from apollo.client import create_contacts_bulk

    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    contacts = [{"first_name": "Jane", "last_name": "Doe", "email": "jane@acme.com"}]

    for status in (401, 403, 429, 500):
        monkeypatch.setattr(
            requests,
            "post",
            lambda *a, _status=status, **k: mock_requests_response(_status, {}),
        )
        result, message = create_contacts_bulk("key", contacts, ["club_sponsorship"])
        assert result is None
        assert isinstance(message, str) and message

    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: mock_requests_response(422, {"message": "bad param"}),
    )
    result, message = create_contacts_bulk("key", contacts, ["club_sponsorship"])
    assert result is None
    assert "bad param" in message


def test_create_contacts_bulk_success_shape(monkeypatch, mock_requests_response):
    from apollo.client import create_contacts_bulk

    body = {
        "created_contacts": [{"id": "c1", "email": "a@x.com"}],
        "existing_contacts": [{"id": "c2", "email": "b@x.com"}],
    }
    monkeypatch.setattr(requests, "post", lambda *a, **k: mock_requests_response(200, body))

    contacts = [{"first_name": "Jane", "email": "jane@acme.com"}]
    result, message = create_contacts_bulk("key", contacts, ["club_sponsorship"])

    assert result == body
    assert message == "OK"


def test_create_contacts_bulk_sends_run_dedupe(monkeypatch, mock_requests_response):
    from apollo.client import create_contacts_bulk

    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured["body"] = json
        return mock_requests_response(200, {"created_contacts": [], "existing_contacts": []})

    monkeypatch.setattr(requests, "post", _fake_post)

    contacts = [{"first_name": "Jane", "email": "jane@acme.com"}]
    create_contacts_bulk("key", contacts, ["club_sponsorship"])

    assert captured["body"]["run_dedupe"] is True
    assert captured["body"]["append_label_names"] == ["club_sponsorship"]


def test_create_contacts_bulk_chunks_at_100(monkeypatch, mock_requests_response):
    from apollo.client import create_contacts_bulk

    calls = []

    def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append(json)
        created = [{"id": f"c{i}", "email": c["email"]} for i, c in enumerate(json["contacts"])]
        return mock_requests_response(200, {"created_contacts": created, "existing_contacts": []})

    monkeypatch.setattr(requests, "post", _fake_post)

    contacts = [{"first_name": f"P{i}", "email": f"p{i}@acme.com"} for i in range(150)]
    result, message = create_contacts_bulk("key", contacts, ["club_sponsorship"])

    assert message == "OK"
    assert len(calls) == 2
    assert len(calls[0]["contacts"]) == 100
    assert len(calls[1]["contacts"]) == 50
    assert len(result["created_contacts"]) == 150


def test_create_contacts_bulk_never_raises_on_network(monkeypatch):
    from apollo.client import create_contacts_bulk

    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    def _raise(*a, **k):
        raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "post", _raise)
    contacts = [{"first_name": "Jane", "email": "jane@acme.com"}]
    result, message = create_contacts_bulk("key", contacts, ["club_sponsorship"])
    assert result is None
    assert isinstance(message, str) and message


def test_create_contacts_bulk_attaches_typed_custom_fields(monkeypatch, mock_requests_response):
    from apollo.client import create_contacts_bulk

    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured["body"] = json
        return mock_requests_response(200, {"created_contacts": [], "existing_contacts": []})

    monkeypatch.setattr(requests, "post", _fake_post)

    contacts = [
        {"first_name": "Jane", "email": "jane@acme.com", "opening_line": "Loved your launch."}
    ]
    create_contacts_bulk(
        "key", contacts, ["club_sponsorship"], opening_line_field_id="60c39ed82bd02f01154c470a"
    )

    entry = captured["body"]["contacts"][0]
    assert entry["typed_custom_fields"] == {"60c39ed82bd02f01154c470a": "Loved your launch."}
    assert "opening_line" not in entry


def test_create_contacts_bulk_omits_custom_fields_when_no_field_id(monkeypatch, mock_requests_response):
    from apollo.client import create_contacts_bulk

    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured["body"] = json
        return mock_requests_response(200, {"created_contacts": [], "existing_contacts": []})

    monkeypatch.setattr(requests, "post", _fake_post)

    contacts = [
        {"first_name": "Jane", "email": "jane@acme.com", "opening_line": "Loved your launch."}
    ]
    create_contacts_bulk("key", contacts, ["club_sponsorship"], opening_line_field_id=None)

    entry = captured["body"]["contacts"][0]
    assert "typed_custom_fields" not in entry
    assert "opening_line" not in entry


def test_add_contacts_to_sequence_error_codes(monkeypatch, mock_requests_response):
    from apollo.client import add_contacts_to_sequence

    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    for status in (401, 403, 429, 500):
        monkeypatch.setattr(
            requests,
            "post",
            lambda *a, _status=status, **k: mock_requests_response(_status, {}),
        )
        result, message = add_contacts_to_sequence("key", "seq-1", ["c1"], "mailbox-1")
        assert result is None
        assert isinstance(message, str) and message

    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: mock_requests_response(422, {"message": "bad param"}),
    )
    result, message = add_contacts_to_sequence("key", "seq-1", ["c1"], "mailbox-1")
    assert result is None
    assert "bad param" in message


def test_add_contacts_to_sequence_sends_required_params(monkeypatch, mock_requests_response):
    from apollo.client import add_contacts_to_sequence

    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None, params=None, **kwargs):
        captured["params"] = params
        return mock_requests_response(200, {"contacts": [], "skipped_contact_ids": {}})

    monkeypatch.setattr(requests, "post", _fake_post)

    add_contacts_to_sequence("key", "seq-1", ["c1", "c2"], "mailbox-1")

    assert captured["params"]["emailer_campaign_id"] == "seq-1"
    assert captured["params"]["send_email_from_email_account_id"] == "mailbox-1"
    assert captured["params"]["contact_ids[]"] == ["c1", "c2"]


def test_add_contacts_to_sequence_returns_body_on_200(monkeypatch, mock_requests_response):
    from apollo.client import add_contacts_to_sequence

    body = {
        "contacts": [{"id": "c1"}],
        "skipped_contact_ids": {"c2": "contacts_active_in_other_campaigns"},
    }
    monkeypatch.setattr(requests, "post", lambda *a, **k: mock_requests_response(200, body))

    result, message = add_contacts_to_sequence("key", "seq-1", ["c1", "c2"], "mailbox-1")

    assert result == body
    assert message == "OK"


def test_bulk_match_people_batches_of_ten(monkeypatch, mock_requests_response):
    from apollo.client import enrich_candidates

    calls = []

    def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append(json)
        matched = [{"id": d["id"], "email": f"{d['id']}@example.com"} for d in json["details"]]
        return mock_requests_response(200, {"matches": matched})

    monkeypatch.setattr(requests, "post", _fake_post)

    candidates = [
        {
            "id": f"p{i}",
            "first_name": f"First{i}",
            "last_name_obfuscated": "X.",
            "title": "Director",
            "has_email": True,
            "organization": {"name": f"Org{i}", "website_url": f"https://org{i}.com"},
        }
        for i in range(25)
    ]

    matches, message = enrich_candidates("good-key", candidates)

    assert message == "OK"
    assert len(matches) == 25
    assert len(calls) == 3
    for call_body in calls:
        details = call_body["details"]
        assert len(details) <= 10
        for detail in details:
            assert "id" in detail
            assert detail.get("first_name") or detail.get("organization_name")
