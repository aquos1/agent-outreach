"""RED tests for SPF/DMARC/DKIM checks (mailbox/dns_checks.py, not yet implemented).

Imports are performed inside the test body so `pytest --collect-only` succeeds
before mailbox/dns_checks.py exists (Plan 01-03 implements it).
"""


def test_check_spf_dmarc_dkim(mock_dns_txt):
    from mailbox.dns_checks import check_spf, check_dmarc, check_dkim

    domain = "example.com"

    # SPF present
    mock_dns_txt({domain: ["v=spf1 include:_spf.example.com ~all"]})
    ok, message = check_spf(domain)
    assert ok is True
    assert isinstance(message, str) and message

    # SPF absent
    mock_dns_txt({}, raise_for=[domain])
    ok, message = check_spf(domain)
    assert ok is False
    assert isinstance(message, str) and message

    # DMARC present
    mock_dns_txt({f"_dmarc.{domain}": ["v=DMARC1; p=reject;"]})
    ok, message = check_dmarc(domain)
    assert ok is True
    assert isinstance(message, str) and message

    # DMARC absent
    mock_dns_txt({}, raise_for=[f"_dmarc.{domain}"])
    ok, message = check_dmarc(domain)
    assert ok is False
    assert isinstance(message, str) and message

    # DKIM: no common selector resolves -> 'unknown', never a hard fail
    mock_dns_txt({})
    status, message = check_dkim(domain)
    assert status == "unknown"
    assert isinstance(message, str) and message
