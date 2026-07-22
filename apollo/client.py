"""Apollo.io connectivity client: key-validity gate and informational credit balance.

Two separate calls per Pitfall 1 (01-RESEARCH.md):
- GET /auth/health           -> key validity (D-01 gate)
- POST /usage_stats/api_usage_stats -> credit/usage info (D-03 informational)

Every function returns a typed tuple and never raises — network failures and
unexpected response shapes degrade to a plain-language banner message instead
of propagating a stack trace to the (non-technical) user (SC-2, T-03-02).

NEVER log or print the api_key (T-03-01).
"""
from __future__ import annotations

import requests

APOLLO_BASE = "https://api.apollo.io/api/v1"


def check_apollo_health(api_key: str) -> tuple[bool, str]:
    """Validate the Apollo Master API key via GET /auth/health.

    Returns (valid, banner_message). Never raises.
    """
    try:
        resp = requests.get(
            f"{APOLLO_BASE}/auth/health",
            headers={"x-api-key": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return False, "Apollo connection failed — check your internet connection and try again."

    if resp.status_code == 401:
        return False, "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."
    if resp.status_code == 403:
        return False, "Apollo connection failed — this key is not a Master API key. Check Apollo Settings → Integrations → API Keys."
    if resp.status_code != 200:
        return False, f"Apollo connection failed — unexpected status {resp.status_code}."

    data = resp.json()
    if not data.get("is_logged_in", False):
        return False, "Apollo connection failed — key present but not recognized as logged in."
    return True, "Apollo connection OK"


def get_credit_balance(api_key: str) -> tuple[int | None, str]:
    """Return (credits_remaining_or_None, status_message). Never blocks (D-03).

    Informational only — a missing/renamed credit field degrades to
    "unavailable" rather than crashing the health page.
    """
    try:
        resp = requests.post(
            f"{APOLLO_BASE}/usage_stats/api_usage_stats",
            headers={"x-api-key": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return None, "Credit balance unavailable (network error)"

    if resp.status_code != 200:
        return None, "Credit balance unavailable"

    data = resp.json()
    # CONFIRMED (01-04 Task 3 human-verify, live call): this endpoint returns
    # per-endpoint rate-limit consumption (keyed by e.g. '["api/v1/contacts",
    # "bulk_match"]' -> {day,hour,minute: {limit,consumed,left_over}}), not a
    # credit balance. Apollo does not expose credit balance via any API
    # endpoint — per docs.apollo.io/docs/api-pricing, it's dashboard-only
    # (Settings > Billing and credits > Credit usage). This lookup will always
    # miss and correctly degrade to "unavailable" (D-03, non-blocking) — that
    # is the permanent expected behavior, not a bug to fix.
    credits = data.get("credits") or data.get("credit_balance")
    if credits is None:
        return None, "Credit balance unavailable (unexpected response shape)"
    return credits, "OK"
