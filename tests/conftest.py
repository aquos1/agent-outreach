"""Shared pytest fixtures for the Foundation phase test suite.

Provides:
- tmp_db_path: a per-test temp SQLite file path (auto-cleaned via pytest's tmp_path)
- mock_requests_response: a factory fixture that builds a fake requests.Response-like
  object with .status_code and .json(), for monkeypatching requests.get/requests.post
- mock_dns_txt: a fixture that returns a helper for monkeypatching
  dns.resolver.resolve to return canned TXT answers or raise NXDOMAIN/NoAnswer
- mock_anthropic_message: a factory fixture that builds a fake anthropic Message-like
  object with .content, for monkeypatching a fake client's messages.create()
"""
from __future__ import annotations

import types

import pytest
import dns.resolver
import dns.exception


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a per-test temp SQLite file path. Cleaned up automatically by pytest."""
    return str(tmp_path / "outreach.db")


class _FakeResponse:
    """Minimal stand-in for requests.Response used in unit tests."""

    def __init__(self, status_code: int, json_data: dict | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


@pytest.fixture
def mock_requests_response():
    """Factory fixture: mock_requests_response(status_code, json_data) -> _FakeResponse."""

    def _make(status_code: int, json_data: dict | None = None) -> _FakeResponse:
        return _FakeResponse(status_code, json_data)

    return _make


class _FakeTXTRecord:
    """Minimal stand-in for a dnspython TXT resource record."""

    def __init__(self, text: str):
        # dnspython TXT answers expose a `.strings` list of bytes chunks
        self.strings = [text.encode()]


class _FakeAnthropicMessage:
    """Minimal stand-in for anthropic.types.Message used in unit tests.

    Not the real SDK response class (RESEARCH.md Pattern 1 / conftest
    convention: minimal stand-in, not the real SDK object) -- exposes only
    the `.content` list-of-content-blocks shape that
    personalization/generator.py's text-extraction line consumes:
    `[b.text for b in message.content if b.type == "text"]`.
    """

    def __init__(self, text: str):
        self.content = [types.SimpleNamespace(type="text", text=text)]


@pytest.fixture
def mock_anthropic_message():
    """Factory fixture: mock_anthropic_message(text) -> _FakeAnthropicMessage.

    Usage: monkeypatch a fake client's `messages.create` to return
    `mock_anthropic_message("some text")`, so tests never construct a real
    anthropic.Anthropic() or hit the network.
    """

    def _make(text: str) -> _FakeAnthropicMessage:
        return _FakeAnthropicMessage(text)

    return _make


@pytest.fixture
def mock_dns_txt(monkeypatch):
    """Helper fixture for monkeypatching dns.resolver.resolve.

    Usage:
        mock_dns_txt(monkeypatch, {"example.com": ["v=spf1 include:_spf.example.com ~all"]})
        mock_dns_txt(monkeypatch, {}, raise_for=["example.com"])  # -> NXDOMAIN
    """

    def _apply(records: dict[str, list[str]] | None = None, raise_for: list[str] | None = None,
               exc: type[Exception] = dns.resolver.NXDOMAIN):
        records = records or {}
        raise_for = raise_for or []

        def _resolve(name, rdtype="TXT", *args, **kwargs):
            name_str = str(name).rstrip(".")
            if name_str in raise_for:
                raise exc()
            if name_str in records:
                return [_FakeTXTRecord(text) for text in records[name_str]]
            raise dns.resolver.NXDOMAIN()

        monkeypatch.setattr(dns.resolver, "resolve", _resolve)

    return _apply
