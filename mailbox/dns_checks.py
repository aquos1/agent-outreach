"""SPF/DMARC/DKIM mailbox deliverability checks via public DNS TXT records.

Uses dnspython's dns.resolver.resolve (NOT raw sockets — Don't Hand-Roll,
01-RESEARCH.md line 246) so NXDOMAIN / no-record / timeout are distinguished
correctly.

DKIM has no selector-enumeration mechanism in DNS (RFC 6376) — a brute-force
list of common selectors can only confirm a *pass*, never a hard failure.
An undetected selector always degrades to 'unknown' (Pitfall 2).
"""
from __future__ import annotations

import dns.exception
import dns.resolver

COMMON_DKIM_SELECTORS = [
    "google", "selector1", "selector2", "k1", "s1", "s2",
    "default", "dkim", "mail", "m1",
]


def _valid_domain(domain: str | None) -> bool:
    """Reject None/empty/whitespace/malformed domains before any DNS query.

    Guards against admin-misconfigured SENDING_DOMAIN producing malformed
    query names (V5 input validation, RESEARCH.md line 582 / T-03-03).
    """
    if not domain or not domain.strip():
        return False
    domain = domain.strip()
    if " " in domain:
        return False
    if "://" in domain:
        return False
    if "." not in domain:
        return False
    return True


def _txt_records(name: str) -> list[str]:
    """Resolve TXT records for name, returning [] on no-record/error (not exception)."""
    try:
        answers = dns.resolver.resolve(name, "TXT")
        return [
            "".join(part.decode() for part in r.strings) if hasattr(r, "strings") else str(r)
            for r in answers
        ]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
        return []


def check_spf(domain: str) -> tuple[bool, str]:
    """Return (True, msg) when a v=spf1 TXT record exists on the root domain."""
    if not _valid_domain(domain):
        return False, "No SPF record found (invalid or missing sending domain)"
    records = _txt_records(domain)
    for r in records:
        if r.startswith("v=spf1"):
            return True, f"SPF record found: {r}"
    return False, "No SPF record found (expected v=spf1 ... TXT record on the root domain)"


def check_dmarc(domain: str) -> tuple[bool, str]:
    """Return (True, msg) when a v=DMARC1 TXT record exists at _dmarc.<domain>."""
    if not _valid_domain(domain):
        return False, "No DMARC record found (invalid or missing sending domain)"
    records = _txt_records(f"_dmarc.{domain}")
    for r in records:
        if r.startswith("v=DMARC1"):
            return True, f"DMARC record found: {r}"
    return False, "No DMARC record found (expected v=DMARC1 ... TXT record at _dmarc.<domain>)"


def check_dkim(domain: str) -> tuple[str, str]:
    """Return ('pass' | 'unknown', msg). Never returns a hard-fail status — see Pitfall 2.

    DNS has no DKIM selector enumeration (RFC 6376); an undetected common
    selector does not prove misconfiguration, only that auto-detection was
    inconclusive.
    """
    if not _valid_domain(domain):
        return "unknown", (
            "Could not auto-detect a DKIM record (invalid or missing sending domain). "
            "Please confirm manually."
        )
    for selector in COMMON_DKIM_SELECTORS:
        records = _txt_records(f"{selector}._domainkey.{domain}")
        for r in records:
            if "p=" in r:
                return "pass", f"DKIM record found under selector '{selector}'"
    return "unknown", (
        "Could not auto-detect a DKIM record under common selectors "
        f"({', '.join(COMMON_DKIM_SELECTORS)}). This does not necessarily mean DKIM is "
        "misconfigured — some providers use custom selectors. Please confirm manually."
    )
