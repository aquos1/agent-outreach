"""RED tests for Apollo health checks (apollo/client.py, not yet implemented).

Imports are performed inside the test body so `pytest --collect-only` succeeds
before apollo/client.py exists (Plan 01-03 implements it).
"""
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
