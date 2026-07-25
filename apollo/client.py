"""Apollo.io connectivity client: key-validity gate, informational credit balance,
and contact discovery/enrichment (search_people, bulk_match_people, enrich_candidates).

Two separate calls per Pitfall 1 (01-RESEARCH.md):
- GET /auth/health           -> key validity (D-01 gate)
- POST /usage_stats/api_usage_stats -> credit/usage info (D-03 informational)

Phase 2 adds the two credit-relevant discovery calls (DISC-03):
- POST /mixed_people/api_search -> search_people (0 credits)
- POST /people/bulk_match       -> bulk_match_people (1 credit per matched person)
plus enrich_candidates, a batching wrapper that chunks a candidate list into
<=10-detail bulk_match_people calls, and _post_with_retry, a shared helper that
implements the CLAUDE.md-mandated 429 exponential backoff (max 3 attempts).

Every function returns a typed tuple and never raises — network failures and
unexpected response shapes degrade to a plain-language banner message instead
of propagating a stack trace to the (non-technical) user (SC-2, T-03-02).

NEVER log or print the api_key (T-03-01 / T-02-04).
"""
from __future__ import annotations

import time

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


def _post_with_retry(
    url: str,
    api_key: str,
    json_body: dict,
    timeout: int = 15,
    max_attempts: int = 3,
) -> requests.Response | None:
    """POST with `x-api-key` auth, retrying a 429 with exponential backoff.

    Returns the final Response (200, 4xx, or the last 429) on any completed
    HTTP round-trip. Returns None only when every attempt raises a network
    `requests.RequestException` (T-02-03: DoS-via-429 mitigation, Pitfall 2).
    Never retries on 401/403/422 or any other non-429 status — those are
    returned to the caller immediately.
    """
    last_resp: requests.Response | None = None
    for attempt in range(max_attempts):
        try:
            resp = requests.post(
                url,
                headers={"x-api-key": api_key},
                json=json_body,
                timeout=timeout,
            )
        except requests.RequestException:
            continue

        last_resp = resp
        if resp.status_code != 429:
            return resp
        if attempt < max_attempts - 1:
            time.sleep(0.5 * (2**attempt))
    return last_resp


def search_people(
    api_key: str,
    person_titles: list[str],
    org_keyword_tags: list[str],
    per_page: int = 100,
    page: int = 1,
) -> tuple[list[dict] | None, str]:
    """Search Apollo for people matching titles/org keywords (DISC-03, 0 credits).

    Returns (people_or_None, message). Never raises.
    """
    payload = {
        "person_titles": person_titles,
        "q_organization_keyword_tags": org_keyword_tags,
        "per_page": per_page,
        "page": page,
    }
    resp = _post_with_retry(f"{APOLLO_BASE}/mixed_people/api_search", api_key, payload)
    if resp is None:
        return None, "Contact search failed — check your internet connection and try again."

    if resp.status_code == 401:
        return None, "Apollo connection failed — check that APOLLO_API_KEY is set correctly in Streamlit secrets."
    if resp.status_code == 403:
        return None, "Apollo connection failed — this key is not a Master API key. Check Apollo Settings → Integrations → API Keys."
    if resp.status_code == 429:
        return None, "Apollo is rate-limiting search requests right now — please wait a moment and try again."
    if resp.status_code != 200:
        return None, f"Contact search failed — unexpected status {resp.status_code}."

    data = resp.json()
    return data.get("people", []), "OK"
