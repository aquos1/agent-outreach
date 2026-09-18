"""Pure, network-free and database-free reconciliation layer between Apollo's
bulk contact-creation/sequence-enrollment responses and local prospect rows
(Phase 4 QUEUE-04). Mirrors discovery/logic.py's role for Phase 2: no
`requests`, no `sqlite3`, no `streamlit` import anywhere in this module.

D-07 and D-08 live here, not in apollo/client.py or the page:
- D-07: "Enrolled" is derived strictly from Apollo's add_contact_ids response
  body (`contacts` array), never from the HTTP status code alone.
- D-08: a partial-failure batch marks only Apollo-confirmed contacts as
  enrolled; every other submitted contact must stay untouched so it remains
  retryable in the queue (see split_enrollment_outcome below).
"""
from __future__ import annotations


def build_contact_payloads(rows: list[dict]) -> list[dict]:
    """Transform queue rows into Apollo bulk_create contact payloads.

    Rows without a truthy `email` are omitted entirely — Apollo cannot create
    a contact without one. `opening_line` is a transport-only field: it rides
    through this payload unmodified so `create_contacts_bulk` can convert it
    into `typed_custom_fields` (D-16); it is never itself sent to Apollo as a
    top-level contact attribute. A NULL opening_line becomes an empty string,
    never the literal "None".

    When a row's `first_name`/`last_name` are missing (rows drafted before
    the `last_name` column existed carry NULL), they are derived from the
    row's `name` by splitting on the first space: first token -> first_name,
    remainder -> last_name (empty string when there is no remainder, e.g. a
    single-word name).
    """
    payloads = []
    for row in rows:
        email = row.get("email")
        if not email:
            continue

        first_name = row.get("first_name")
        last_name = row.get("last_name")
        if not first_name and not last_name:
            name = row.get("name") or ""
            parts = name.split(" ", 1)
            first_name = parts[0] if parts else ""
            last_name = parts[1] if len(parts) > 1 else ""

        payloads.append(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "organization_name": row.get("company"),
                "title": row.get("title"),
                "opening_line": row.get("opening_line") or "",
            }
        )
    return payloads


def map_created_contacts(response: dict, rows: list[dict]) -> dict[int, str]:
    """Map prospect id -> Apollo contact id by matching email, never list
    position (Apollo does not document input-order == output-order across
    `created_contacts`/`existing_contacts`, 04-RESEARCH.md Pattern 2).

    Builds an email -> prospect-id map from `rows` first (lowercased), then
    walks `created_contacts + existing_contacts`, mapping each entry's
    lowercased email back to its prospect id. Entries whose email matches no
    row are skipped silently.
    """
    email_to_prospect_id = {
        row["email"].lower(): row["id"] for row in rows if row.get("email")
    }

    result: dict[int, str] = {}
    all_contacts = response.get("created_contacts", []) + response.get(
        "existing_contacts", []
    )
    for contact in all_contacts:
        email = contact.get("email")
        if not email:
            continue
        prospect_id = email_to_prospect_id.get(email.lower())
        if prospect_id is not None:
            result[prospect_id] = contact.get("id")
    return result


def split_enrollment_outcome(
    response: dict, contact_to_prospect: dict[str, int]
) -> tuple[list[int], list[tuple[int, str]]]:
    """Split a submitted batch into (enrolled_ids, [(prospect_id, reason)]).

    D-07: only prospect ids whose Apollo contact id appears in
    `response["contacts"]` are Enrolled. Every other prospect id in
    `contact_to_prospect` is Skipped, paired with the reason from
    `response["skipped_contact_ids"]` when that structure is a dict and
    carries the id, or the literal fallback string "not confirmed by Apollo"
    when the id is absent from both arrays, or when `skipped_contact_ids`
    arrives as a bare list instead of an id->reason dict. Reason strings are
    returned verbatim — Apollo's own wording is what the teammate sees;
    never hardcode a comparison against spec.MD's differently-prefixed
    override-flag vocabulary (04-RESEARCH.md Pitfall 2).

    An HTTP 200 is never sufficient on its own — a response with an empty
    `contacts` array enrolls nobody, even though every contact id was
    submitted.
    """
    enrolled_contact_ids = {
        contact.get("id") for contact in response.get("contacts", [])
    }
    raw_skipped = response.get("skipped_contact_ids", {})
    skipped_reasons = raw_skipped if isinstance(raw_skipped, dict) else {}

    enrolled: list[int] = []
    skipped: list[tuple[int, str]] = []
    for contact_id, prospect_id in contact_to_prospect.items():
        if contact_id in enrolled_contact_ids:
            enrolled.append(prospect_id)
        else:
            reason = skipped_reasons.get(contact_id) or "not confirmed by Apollo"
            skipped.append((prospect_id, reason))

    return enrolled, skipped
