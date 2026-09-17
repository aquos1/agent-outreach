"""Contact Discovery page (PATH-01, PATH-03) — two-stage, session-state-driven
Find Contacts -> Enrich & Continue flow.

Composes discovery/logic.py (free-text -> filter translation, has_email
pre-filter, cost estimate), apollo/client.py (search_people,
enrich_candidates), db/prospects.py (dedup_filter, insert_enriched,
update_draft), and personalization/ (build_opening_line, assemble_email) into
the teammate-facing vertical slice per 02-UI-SPEC.md and 03-UI-SPEC.md.

Two distinct stages (D-06): "Find Contacts" is free and only shows a count +
cost estimate (D-07) — no contact table until "Enrich & Continue" (which
spends credits) succeeds. Results persist in st.session_state across reruns
so the count/cost banner and the results table stay visible on screen after
their respective button click.

Draft generation (Phase 3, D-01) is chained automatically immediately after
"Enrich & Continue" succeeds — there is no separate button. A per-contact
Claude Haiku opening line (grounded only in Apollo's title/company, D-06)
plus the path-specific template body is assembled and persisted to
status='drafted' for every enriched contact, with a progress indicator while
it runs and a collapsed "View draft" expander per contact once it finishes.

Every external call (search_people, enrich_candidates, dedup_filter,
insert_enriched, the Claude Haiku personalization loop) is wrapped in
try/except so an unexpected exception renders a plain-language st.error/
st.warning banner instead of a Streamlit traceback, matching
pages/health_page.py's established convention. This page never hard-stops
on a failure — inputs and both buttons must stay usable so the teammate can
retry (UI-SPEC Stage table; contrast with health_page.py's D-01 hard block,
which does not apply to this page).

NEVER log or print the api_key (T-02-04) or the ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import streamlit as st

from apollo.client import enrich_candidates, search_people
from db.prospects import dedup_filter, insert_enriched, update_draft
from discovery.logic import (
    CONTACT_CAP,
    PATH_CONFIG,
    PATH_OPTIONS,
    build_search_filters,
    cost_estimate,
    filter_has_email,
)
from personalization.generator import (
    build_opening_line,
    make_client,
    should_warn_fallback_rate,
)
from personalization.templates import assemble_email

st.title("Contact Discovery")
st.caption(
    "Pick a path, tell us who you're looking for, and we'll find verified "
    "contacts — no filters to configure."
)

# Read once; never re-validate here — app.py/health_page.py's boot-time gate
# already guarantees a valid key by the time this page runs.
apollo_key = st.secrets.get("APOLLO_API_KEY")
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")

if "find_result" not in st.session_state:
    st.session_state.find_result = None  # None = not yet searched this session
if "enrich_result" not in st.session_state:
    st.session_state.enrich_result = None
if "draft_result" not in st.session_state:
    st.session_state.draft_result = None

selected_path = st.selectbox(
    "Outreach path", PATH_OPTIONS, index=None, placeholder="Select an outreach path..."
)
company_type = st.text_input(
    "Company type or industry",
    placeholder="e.g. software startups, nonprofits, apparel brands",
)
target_role = st.text_input(
    "Target role", placeholder="e.g. Marketing Director, Head of Partnerships"
)
st.caption(
    "We search Apollo using these words directly — try a few different terms "
    "if you don't get good matches."
)

find_disabled = not selected_path or not (company_type.strip() or target_role.strip())

if st.button(
    "Find Contacts",
    type="primary",
    icon=":material/manage_search:",
    disabled=find_disabled,
):
    # Re-searching always discards any prior search/enrichment/draft result
    # (no separate "New Search" control needed per UI-SPEC).
    st.session_state.enrich_result = None
    st.session_state.draft_result = None
    with st.spinner("Searching Apollo for matching contacts..."):
        try:
            person_titles, org_keyword_tags = build_search_filters(
                company_type, target_role
            )
            people, message = search_people(apollo_key, person_titles, org_keyword_tags)
        except Exception:
            people, message = (
                None,
                "Contact search failed — check your internet connection and try again.",
            )

        if people is None:
            st.session_state.find_result = {"error": message}
        else:
            try:
                candidates = filter_has_email(people)  # DISC-02
                candidates = dedup_filter(candidates)  # DEDUP-02
            except Exception:
                candidates = None

            if candidates is None:
                st.session_state.find_result = {
                    "error": "Contact search failed — check your internet connection and try again."
                }
            else:
                matched = len(candidates)
                capped_candidates = candidates[:CONTACT_CAP]
                cost = cost_estimate(capped_candidates)  # computed LAST (Pitfall 4)
                st.session_state.find_result = {
                    "error": None,
                    "matched": matched,
                    "cost": cost,
                    "candidates": capped_candidates,
                }

find_result = st.session_state.find_result

if find_result is not None:
    if find_result["error"]:
        st.error(find_result["error"], icon=":material/cancel:")
    elif find_result["matched"] == 0:
        # D-12: zero results is never a failure — no credits were spent,
        # inputs stay editable, plain st.info only.
        st.info(
            "No new contacts found — try different search terms.",
            icon=":material/search_off:",
        )
    else:
        matched = find_result["matched"]
        if matched > CONTACT_CAP:
            st.info(
                f"Found {matched} new contacts — showing the first {CONTACT_CAP}. "
                f"Enriching will use up to {CONTACT_CAP} credits.",
                icon=":material/manage_search:",
            )
        else:
            plural = "" if matched == 1 else "s"
            st.info(
                f"Found {matched} new contact{plural} — enriching will use up to "
                f"{matched} credit{plural}.",
                icon=":material/manage_search:",
            )

        if st.button("Enrich & Continue", type="primary", icon=":material/bolt:"):
            with st.spinner("Enriching contacts with verified emails..."):
                try:
                    matches, message = enrich_candidates(
                        apollo_key, find_result["candidates"]
                    )
                except Exception:
                    matches, message = (
                        None,
                        "Contact enrichment failed — check your internet connection and try again.",
                    )

                if matches is None:
                    st.session_state.enrich_result = {"error": message, "rows": None}
                    st.session_state.draft_result = None
                else:
                    try:
                        slug = PATH_CONFIG[selected_path]["slug"]
                        insert_enriched(matches, path=slug)
                        st.session_state.enrich_result = {
                            "error": None,
                            "rows": matches,
                        }

                        # D-01: draft generation is chained automatically
                        # here — no second button, no confirmation step.
                        # This inner block degrades to a draft_result error
                        # on any unexpected exception (never a traceback,
                        # never st.stop()) rather than escaping to the
                        # outer except and falsely reporting enrichment
                        # itself as failed.
                        try:
                            total = len(matches)
                            progress_placeholder = st.empty()
                            progress_placeholder.progress(
                                0, text=f"Personalizing drafts... 0/{total}"
                            )

                            client = make_client(anthropic_key)
                            draft_rows = []
                            fallback_count = 0

                            for i, match in enumerate(matches):
                                title = match.get("title")
                                company = (
                                    match.get("organization") or {}
                                ).get("name") or ""
                                first_name = match.get("first_name") or ""

                                opening_line, source = build_opening_line(
                                    client, title, company
                                )
                                if source == "fallback":
                                    fallback_count += 1

                                subject, body = assemble_email(
                                    slug, first_name, company, opening_line
                                )
                                update_draft(
                                    match.get("id"),
                                    opening_line,
                                    source,
                                    first_name=first_name,
                                )

                                draft_rows.append(
                                    {
                                        "name": match.get("name"),
                                        "company": company,
                                        "subject": subject,
                                        "body": body,
                                        "source": source,
                                    }
                                )

                                progress_placeholder.progress(
                                    (i + 1) / total,
                                    text=f"Personalizing drafts... {i + 1}/{total}",
                                )

                            progress_placeholder.empty()
                            st.session_state.draft_result = {
                                "error": None,
                                "rows": draft_rows,
                                "fallback_count": fallback_count,
                                "total": total,
                            }
                        except Exception:
                            st.session_state.draft_result = {
                                "error": "Draft personalization failed unexpectedly — click Enrich & Continue again to retry.",
                                "rows": None,
                            }
                    except Exception:
                        # Rule 2: a DB write failure means the "written to
                        # prospect" guarantee did not hold — surface a
                        # failure banner rather than a false success.
                        st.session_state.enrich_result = {
                            "error": "Contact enrichment failed — check your internet connection and try again.",
                            "rows": None,
                        }
                        st.session_state.draft_result = None

    enrich_result = st.session_state.enrich_result

    if enrich_result is not None:
        if enrich_result["error"]:
            st.error(enrich_result["error"], icon=":material/cancel:")
        elif enrich_result["rows"]:
            rows = enrich_result["rows"]
            count = len(rows)
            plural = "" if count == 1 else "s"
            st.success(
                f"Enrichment complete — {count} contact{plural} ready.",
                icon=":material/check_circle:",
            )

            draft_result = st.session_state.draft_result

            if (
                draft_result is not None
                and not draft_result.get("error")
                and should_warn_fallback_rate(
                    draft_result.get("fallback_count", 0),
                    draft_result.get("total", 0),
                )
            ):
                st.warning(
                    "AI personalization is unavailable right now — drafts are using generic openers.",
                    icon=":material/error:",
                )

            table_rows = [
                {
                    "Name": match.get("name"),
                    "Company": (match.get("organization") or {}).get("name"),
                    "Title": match.get("title"),
                    "Email": match.get("email"),
                }
                for match in rows
            ]
            # D-11/D-13: exactly Name/Company/Title/Email, st.dataframe,
            # read-only — no on_select (D-10).
            st.dataframe(table_rows)

            if draft_result is not None:
                if draft_result.get("error"):
                    st.error(draft_result["error"], icon=":material/cancel:")
                else:
                    st.divider()
                    st.subheader("Email Drafts", icon=":material/drafts:")
                    for draft in draft_result["rows"]:
                        with st.expander(
                            f"View draft — {draft['name']} ({draft['company']})",
                            icon=":material/mail:",
                            expanded=False,
                        ):
                            full_text = (
                                f"Subject: {draft['subject']}\n\n{draft['body']}"
                            )
                            st.code(full_text, language=None)
