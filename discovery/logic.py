"""Pure, network-free discovery transforms for the Find Contacts stage.

No `requests`, no live Apollo, no AI normalization — every function here is a
deterministic transform over already-fetched data or plain free-text strings
(DISC-01, DISC-02, DISC-04, PATH-02). Path selection (PATH_OPTIONS/PATH_CONFIG)
determines only the downstream Apollo sequence slug, never the search filters
themselves — build_search_filters intentionally takes no path argument.
"""
from __future__ import annotations

CONTACT_CAP = 50

# Exact labels/order per 02-UI-SPEC.md Copywriting Contract (PATH-01 source of truth).
PATH_OPTIONS = [
    "Club Sponsorship",
    "Productthon Sponsorship",
    "Client Sourcing",
]

# Path selection changes only the downstream slug (sequence/template lookup),
# never the search filters (PATH-02, D-01).
PATH_CONFIG = {
    "Club Sponsorship": {"slug": "club_sponsorship"},
    "Productthon Sponsorship": {"slug": "productthon"},
    "Client Sourcing": {"slug": "client_sourcing"},
}


def to_filter_list(free_text: str) -> list[str]:
    """Split comma-separated free text into a list of literal keyword strings.

    No AI normalization (D-04) — a straight split-and-strip only. Empty or
    whitespace-only input returns an empty list; a single phrase (no comma)
    returns a one-element list.
    """
    if not free_text or not free_text.strip():
        return []
    return [part.strip() for part in free_text.split(",") if part.strip()]


def build_search_filters(
    company_type: str, target_role: str
) -> tuple[list[str], list[str]]:
    """Translate free text into (person_titles, org_keyword_tags).

    Takes NO path argument — path selection never affects search filters
    (DISC-01/PATH-02, D-01). person_titles derives from target_role,
    org_keyword_tags derives from company_type.
    """
    person_titles = to_filter_list(target_role)
    org_keyword_tags = to_filter_list(company_type)
    return person_titles, org_keyword_tags


def filter_has_email(people: list[dict]) -> list[dict]:
    """Keep only candidates with a truthy has_email field (DISC-02).

    A candidate missing the key entirely is dropped, not crashed on —
    defensive `.get()` per the Assumptions A1 degradation rule.

    CONFIRMED (02-03 live human-verify, 2026-09-11): a real
    `mixed_people/api_search` response carries `has_email` as a boolean on
    every person, exactly as assumed — no field-name mismatch found here.
    """
    return [p for p in people if p.get("has_email")]


def cost_estimate(candidates: list[dict]) -> int:
    """Local-only cost estimate: min(len(candidates), CONTACT_CAP).

    No api_key/network argument — no Apollo call is made (DISC-04/D-05).
    Must be called strictly after the has_email and dedup filters have
    already run (Pitfall 4) so the count reflects final, post-filter
    candidates, not the raw search result count.
    """
    return min(len(candidates), CONTACT_CAP)
