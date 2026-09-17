"""RED tests for personalization/generator.py and personalization/templates.py
(not yet implemented -- plans 03-02 and 03-03 implement them).

Imports are performed inside each test body so `pytest --collect-only`
succeeds before those modules exist, matching this repo's established
deferred-import convention (see tests/test_apollo_client.py).

No test in this module makes a live network call: the Anthropic client is
always a hand-built fake object (never a real anthropic.Anthropic()), and
the mock_anthropic_message fixture (tests/conftest.py) stands in for the
SDK's real response shape.

Note: anthropic==1.6.0's error classes (APIConnectionError, APITimeoutError,
RateLimitError) are typed against `httpx2.Request`/`httpx2.Response`, not the
`httpx` package -- confirmed live against the installed SDK and PyPI's
published requires_dist for this exact pin (`httpx2>=2.0.0,<3` is a hard,
non-extra dependency of anthropic 1.6.0). `httpx2` is therefore imported
directly here rather than `httpx`, since that's what the pinned SDK actually
requires to construct these error objects.
"""
from __future__ import annotations

import anthropic
import httpx2


class _FakeMessagesRecorder:
    """Fake `client.messages` namespace that records the kwargs of the last
    `.create(...)` call and returns a canned mock_anthropic_message response.
    """

    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeClient:
    """Minimal stand-in for anthropic.Anthropic -- exposes only `.messages`."""

    def __init__(self, messages):
        self.messages = messages


def test_prompt_excludes_industry_and_seniority(mock_anthropic_message):
    from personalization.generator import generate_opening_line

    response = mock_anthropic_message("A grounded opener.")
    fake_messages = _FakeMessagesRecorder(response)
    fake_client = _FakeClient(fake_messages)

    generate_opening_line(
        fake_client,
        title="Head of Partnerships",
        company="Acme Corp",
        path_slug="club_sponsorship",
    )

    kwargs = fake_messages.last_kwargs
    assert kwargs is not None
    assert kwargs["model"] == "claude-haiku-4-5-20251001"

    system_text = kwargs.get("system", "")
    user_text = "".join(
        block.get("content", "") if isinstance(block, dict) else str(block)
        for block in kwargs.get("messages", [])
    )
    combined = (system_text + user_text).lower()

    assert "head of partnerships" in combined
    assert "acme corp" in combined
    assert "industry" not in combined
    assert "seniority" not in combined


def test_sparse_title_triggers_fallback():
    from personalization.generator import build_opening_line

    def _raise_if_called(**kwargs):
        raise AssertionError("API must not be called for a sparse title")

    fake_messages = _FakeMessagesRecorder(response=None)
    fake_messages.create = _raise_if_called
    fake_client = _FakeClient(fake_messages)

    for title in (None, "", "   ", "N/A", "unknown", "-"):
        line, source = build_opening_line(
            fake_client, title, company="Acme Corp", path_slug="club_sponsorship"
        )
        assert source == "fallback"
        assert isinstance(line, str) and line
        assert "Acme Corp" in line


def test_api_failure_triggers_fallback():
    from personalization.generator import build_opening_line

    def _make_connection_error():
        return anthropic.APIConnectionError(
            request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        )

    def _make_rate_limit_error():
        return anthropic.RateLimitError(
            message="rate limited",
            response=httpx2.Response(
                429,
                request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"),
            ),
            body=None,
        )

    def _make_timeout_error():
        return anthropic.APITimeoutError(
            request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        )

    for make_error in (_make_connection_error, _make_rate_limit_error, _make_timeout_error):
        error = make_error()

        def _raise(**kwargs):
            raise error

        fake_messages = _FakeMessagesRecorder(response=None)
        fake_messages.create = _raise
        fake_client = _FakeClient(fake_messages)

        line, source = build_opening_line(
            fake_client,
            title="Head of Partnerships",
            company="Acme Corp",
            path_slug="club_sponsorship",
        )

        assert source == "fallback"
        assert isinstance(line, str) and line


def test_generate_opening_line_strips_quotes_and_whitespace(mock_anthropic_message):
    from personalization.generator import generate_opening_line

    response = mock_anthropic_message('  "Congrats on the new role at Acme Corp."  ')
    fake_messages = _FakeMessagesRecorder(response)
    fake_client = _FakeClient(fake_messages)

    line, message = generate_opening_line(
        fake_client,
        title="Head of Partnerships",
        company="Acme Corp",
        path_slug="club_sponsorship",
    )

    assert line is not None
    assert not line.startswith('"')
    assert not line.endswith('"')
    assert line == line.strip()

    whitespace_response = mock_anthropic_message("   ")
    fake_messages_ws = _FakeMessagesRecorder(whitespace_response)
    fake_client_ws = _FakeClient(fake_messages_ws)

    empty_line, empty_message = generate_opening_line(
        fake_client_ws,
        title="Head of Partnerships",
        company="Acme Corp",
        path_slug="club_sponsorship",
    )
    assert empty_line is None
    assert isinstance(empty_message, str) and empty_message


def test_client_sourcing_framing_reaches_prompt(mock_anthropic_message):
    """The client_sourcing path must pitch the org offering to help the
    company, never a "we want to learn from you" framing -- that framing is
    nonsensical for client_sourcing's actual ask (a free consulting team
    solving a problem FOR the company, not the org asking to be mentored).
    Asserts the right instruction reached the prompt sent to the model --
    not a specific model output, which can't be asserted deterministically.
    """
    from personalization.generator import PATH_FRAMING, generate_opening_line

    response = mock_anthropic_message("A grounded opener.")
    fake_messages = _FakeMessagesRecorder(response)
    fake_client = _FakeClient(fake_messages)

    generate_opening_line(
        fake_client,
        title="Head of Partnerships",
        company="Acme Corp",
        path_slug="client_sourcing",
    )

    kwargs = fake_messages.last_kwargs
    assert kwargs is not None
    system_text = kwargs.get("system", "")
    user_text = "".join(
        block.get("content", "") if isinstance(block, dict) else str(block)
        for block in kwargs.get("messages", [])
    )
    combined = system_text + user_text

    assert PATH_FRAMING["client_sourcing"] in combined
    assert "offering to help" in combined.lower() or "help them" in combined.lower()
    assert "learn about their approach" in combined.lower()  # the negative instruction is present...
    assert "do not frame" in combined.lower()  # ...as an explicit prohibition, not a suggestion

    # Different path -> different framing sentence reaches the prompt.
    fake_messages_club = _FakeMessagesRecorder(mock_anthropic_message("Another opener."))
    fake_client_club = _FakeClient(fake_messages_club)
    generate_opening_line(
        fake_client_club,
        title="Head of Partnerships",
        company="Acme Corp",
        path_slug="club_sponsorship",
    )
    club_kwargs = fake_messages_club.last_kwargs
    club_user_text = "".join(
        block.get("content", "") if isinstance(block, dict) else str(block)
        for block in club_kwargs.get("messages", [])
    )
    assert PATH_FRAMING["client_sourcing"] not in club_user_text
    assert PATH_FRAMING["club_sponsorship"] in (club_kwargs.get("system", "") + club_user_text)


def test_assemble_email_per_path():
    from personalization.templates import assemble_email

    for slug in ("club_sponsorship", "productthon", "client_sourcing"):
        subject, body = assemble_email(
            slug, first_name="Jamie", company="Acme Corp", opening_line="OPENER_SENTINEL"
        )

        assert isinstance(subject, str) and subject
        assert isinstance(body, str) and body
        assert "OPENER_SENTINEL" in body

        paragraphs = body.split("\n\n")
        assert paragraphs[1] == "OPENER_SENTINEL"

        assert "Jamie" in body
        assert "Acme Corp" in body
        assert "{" not in subject
        assert "{" not in body
        assert "[First Name]" not in body
        assert "[Company]" not in body
        assert "Best regards," in body
        assert "Yash Kulkarni" in body

    club_subject, club_body = assemble_email(
        "club_sponsorship", first_name="Jamie", company="Acme Corp", opening_line="OPENER_SENTINEL"
    )
    productthon_subject, productthon_body = assemble_email(
        "productthon", first_name="Jamie", company="Acme Corp", opening_line="OPENER_SENTINEL"
    )
    client_subject, client_body = assemble_email(
        "client_sourcing", first_name="Jamie", company="Acme Corp", opening_line="OPENER_SENTINEL"
    )

    assert "[SPONSORSHIP_LINK]" in club_body
    assert "[SPONSORSHIP_LINK]" in productthon_body
    assert "[SPONSORSHIP_LINK]" not in client_body
    assert client_subject == "Partner with Product Space UW on Your Next Product Initiative"


def test_fallback_fraction_threshold():
    from personalization.generator import should_warn_fallback_rate

    assert should_warn_fallback_rate(6, 10) is True
    assert should_warn_fallback_rate(5, 10) is False
    assert should_warn_fallback_rate(0, 10) is False
    assert should_warn_fallback_rate(10, 10) is True
    assert should_warn_fallback_rate(0, 0) is False
