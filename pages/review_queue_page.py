"""Review Queue page (QUEUE-01 through QUEUE-04) — path-scoped view of every
drafted email awaiting a teammate's review, a shared per-path template
editor (D-03 through D-06), and bulk approval into Apollo (D-07 through
D-18).

Composes discovery/logic.py (PATH_OPTIONS/PATH_CONFIG — reused, never
re-derived), db/prospects.py (get_drafted_by_path, mark_contact_created,
mark_sequenced), db/templates_store.py (get_template/save_template_override),
personalization/templates.py (validate_template_fields, override-aware
assemble_email), apollo/client.py (the enrollment engine and custom-field
lifecycle calls), and review/logic.py (the pure response-reconciliation
layer) into the full vertical slice of Phase 4: a teammate can open this
page, pick a path, edit the shared subject/body, select which drafts to
send, confirm once, and watch each contact come back Enrolled or Skipped
with Apollo's own reason.

D-03: the template editor lives on this page, above the queue, never on
Discovery's read-only Email Drafts section. D-04: saving re-assembles every
visible preview immediately. D-05: an edited template persists across app
restarts as the new default for that path; PATH_TEMPLATES stays the
seed/fallback. D-06: all three merge fields ({first_name}, {company},
{opening_line}) are validated before any save. D-14 consequence: only the
opening line actually travels to Apollo — the editor makes this explicit so
a teammate never assumes an edit here changes what Apollo sends.

D-11: the path selector always has exactly one path selected (index=0, no
"nothing chosen" state) — unlike Discovery's optional-until-chosen picker,
this page has no meaningful "do nothing" state, and the template editor
needs an unambiguous single-path target at all times.

D-10: rows render as a manual st.columns row loop (not st.dataframe) so each
row's Select cell can swap between an interactive checkbox and a status
outcome badge in place (D-12).

D-01/D-02/D-13: the three per-path sequence-secret keys and the one shared
sending-mailbox secret are read once, module scope, alongside the existing
Apollo key — never a live lookup at enrollment time. A missing key soft-fails
this page only (a plain-language banner, approve buttons disabled) — it must
never stop Health or Discovery from working, so no boot gate is added.

D-18: the "AI Opening Line" custom field is resolved lazily, once per
Streamlit session, the first time this page runs — never at app boot (that
would add an unnecessary Apollo round-trip to pages that don't need it and
would hard-stop the whole app over a page-scoped capability).

D-09: both approve buttons route through a confirmation dialog rather than
firing an Apollo call directly — a deliberate, documented exception to this
app's immediate-fire button convention (Discovery's Find/Enrich), justified
by irreversibility: enrollment sends real emails to real companies.

This page never hard-stops the run — a database read failure, a malformed
row, or an unexpected exception during approval must never blank the whole
page or raise past a plain-language banner, matching
pages/discovery_page.py's established never-hard-stop convention.

NEVER log or print the api_key, the sending-mailbox id, or any secret value.
"""
from __future__ import annotations

import streamlit as st

from apollo.client import (
    add_contacts_to_sequence,
    create_contacts_bulk,
    ensure_custom_field,
    update_contact_custom_field,
)
from db.prospects import get_drafted_by_path, mark_contact_created, mark_sequenced
from db.templates_store import get_template, save_template_override
from discovery.logic import PATH_CONFIG, PATH_OPTIONS
from personalization.templates import PATH_TEMPLATES, assemble_email, validate_template_fields
from review.logic import (
    build_contact_payloads,
    map_created_contacts,
    split_contacts_by_origin,
    split_enrollment_outcome,
)

# D-02/D-13: exact secret key names, one Apollo sequence ID per path plus a
# single shared sending mailbox — hardcoded per D-01, zero live-lookup
# dependency at enrollment time.
SEQUENCE_SECRET_BY_SLUG = {
    "club_sponsorship": "APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP",
    "productthon": "APOLLO_SEQUENCE_ID_PRODUCTTHON",
    "client_sourcing": "APOLLO_SEQUENCE_ID_CLIENT_SOURCING",
}

st.title("Review Queue")
st.caption(
    "Review every drafted email, tweak the shared template if needed, and "
    "approve the ones you're ready to send."
)

# Read once; never re-fetched mid-handler. NEVER log/print this.
apollo_key = st.secrets.get("APOLLO_API_KEY")

# D-11: always exactly one path selected — no placeholder/index=None, since
# this page (unlike Discovery) has no meaningful "nothing chosen" state.
selected_path = st.selectbox("Outreach path", PATH_OPTIONS, index=0)
slug = PATH_CONFIG[selected_path]["slug"]

# D-01/D-02/D-13: resolved once the path is known. Never logged/printed.
sequence_id = st.secrets.get(SEQUENCE_SECRET_BY_SLUG[slug])
sending_account_id = st.secrets.get("APOLLO_SENDING_EMAIL_ACCOUNT_ID")

# D-18: idempotent, page-scoped, once per session — never at app boot (that
# would add an Apollo round-trip to Health/Discovery, which don't need this
# field, and would hard-stop the whole app over a capability only this page
# uses).
if "opening_line_field_id" not in st.session_state:
    try:
        field_id, field_message = ensure_custom_field(apollo_key)
    except Exception:
        field_id, field_message = (
            None,
            "Could not resolve the Apollo custom field for the AI opening line — check your internet connection and try again.",
        )
    st.session_state.opening_line_field_id = field_id
    st.session_state.opening_line_field_message = field_message

# This page's never-hard-stop convention: a missing secret or an unresolved
# custom field disables approving, but the template editor and the queue
# table below still render and work fully.
missing_secret_key = None
if not sequence_id:
    missing_secret_key = SEQUENCE_SECRET_BY_SLUG[slug]
elif not sending_account_id:
    missing_secret_key = "APOLLO_SENDING_EMAIL_ACCOUNT_ID"

approve_disabled = False

if missing_secret_key:
    approve_disabled = True
    st.warning(
        f"Approving is paused for this path — the secret `{missing_secret_key}` "
        "is missing. Add it to .streamlit/secrets.toml locally, or the "
        "Community Cloud secrets console.",
        icon=":material/error:",
    )

if st.session_state.opening_line_field_id is None:
    approve_disabled = True
    st.error(
        f"{st.session_state.opening_line_field_message} Emails would send "
        "without the personalized opening line, so approving is paused "
        "until this resolves.",
        icon=":material/cancel:",
    )

st.divider()

# D-03: template editor lives here, above the queue, below the path
# selector — never on Discovery's read-only Email Drafts section.
if "template_result" not in st.session_state:
    st.session_state.template_result = None  # None = no save attempted yet this session
if "approve_result" not in st.session_state:
    st.session_state.approve_result = None  # None = no approve attempted yet this session
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None  # a target id list once the dialog confirms

# One path's approve outcome must never render against another path's rows —
# clear both whenever the path selector value changes.
if st.session_state.get("_approve_scope_path") != slug:
    st.session_state.approve_result = None
    st.session_state.pending_approval = None
    st.session_state._approve_scope_path = slug


@st.dialog("Confirm enrollment")
def _confirm_enrollment_dialog(target_ids: list[int], path_label: str) -> None:
    count = len(target_ids)
    st.write(f"Enroll {count} contact{'' if count == 1 else 's'} into the {path_label} sequence?")
    dialog_col1, dialog_col2 = st.columns(2)
    if dialog_col1.button("Confirm Enrollment", type="primary"):
        st.session_state.pending_approval = target_ids
        st.rerun()
    if dialog_col2.button("Keep in Queue", type="secondary"):
        st.session_state.pending_approval = None
        st.rerun()


st.subheader(f"Email Template — {selected_path}")

try:
    current_subject, current_body = get_template(slug)
except Exception:
    current_subject = PATH_TEMPLATES[slug]["subject"]
    current_body = PATH_TEMPLATES[slug]["body"]
    st.warning(
        "Couldn't load the saved template — showing the default text instead.",
        icon=":material/error:",
    )

# Per-slug key suffix (D-11/path-switch behavior): switching paths re-renders
# the editor with that path's own text instead of carrying unsaved edits
# from the previous path across.
edited_subject = st.text_input(
    "Email subject", value=current_subject, key=f"tpl_subject_{slug}"
)
edited_body = st.text_area(
    "Email body", value=current_body, height=240, key=f"tpl_body_{slug}"
)
st.caption(
    "Keep {first_name}, {company}, and {opening_line} somewhere in the "
    "subject or body — these get replaced with each contact's real details."
)
st.caption(
    "Apollo sends the email text saved in each sequence's own editor — "
    "only the personalized opening line is sent from here. If you change "
    "the paragraphs below, paste the same text into the Apollo sequence "
    "for this path."
)

if st.button("Save Template", type="primary", icon=":material/save:"):
    ok, message = validate_template_fields(edited_subject, edited_body)
    if not ok:
        st.session_state.template_result = {"error": "validation", "message": message}
    else:
        try:
            save_template_override(slug, edited_subject, edited_body)
        except Exception:
            st.session_state.template_result = {
                "error": "save_failed",
                "message": "Couldn't save the template — try again.",
            }
        else:
            st.session_state.template_result = {
                "error": None,
                "message": "Template saved — every draft below now uses the updated text.",
            }
            st.rerun()

template_result = st.session_state.template_result
if template_result is not None:
    if template_result["error"] == "validation":
        st.warning(template_result["message"], icon=":material/error:")
    elif template_result["error"] == "save_failed":
        st.error(template_result["message"], icon=":material/cancel:")
    else:
        st.success(template_result["message"], icon=":material/check_circle:")

st.divider()

st.subheader(f"Drafts Awaiting Review — {selected_path}")

try:
    rows = get_drafted_by_path(slug)
except Exception:
    rows = None
    st.error(
        "Couldn't load the review queue — try reloading the page.",
        icon=":material/cancel:",
    )

if rows is not None:
    if not rows:
        # D-12/UI-SPEC: an empty queue is never a failure — st.info only.
        st.info(
            f"No drafts waiting for review in {selected_path} — head to "
            "Contact Discovery to find and personalize more contacts for "
            "this path.",
            icon=":material/inbox:",
        )
    else:
        n = len(rows)
        st.caption(f"{n} draft{'' if n == 1 else 's'} ready for review.")

        header_cols = st.columns([1, 3, 3, 3, 2])
        header_cols[0].markdown("**Select**")
        header_cols[1].markdown("**Name**")
        header_cols[2].markdown("**Company**")
        header_cols[3].markdown("**Title**")
        header_cols[4].markdown("**Status**")

        selected_ids: list[int] = []
        for row in rows:
            name = row.get("name") or "—"
            company = row.get("company") or "—"
            title = row.get("title") or "—"

            row_cols = st.columns([1, 3, 3, 3, 2])
            # QUEUE-03: default checked — a teammate unchecks to exclude a
            # specific contact from the next Approve action.
            checked = row_cols[0].checkbox(
                "", value=True, key=f"sel_{row['id']}", label_visibility="collapsed"
            )
            if checked:
                selected_ids.append(row["id"])
            row_cols[1].write(name)
            row_cols[2].write(company)
            row_cols[3].write(title)
            row_cols[4].write("")  # Status badge lands here in Task 2

            with st.expander(
                f"View draft — {name} ({company})",
                icon=":material/mail:",
                expanded=False,
            ):
                try:
                    # D-04: assemble from the loaded override (or its
                    # PATH_TEMPLATES fallback), not the raw defaults, so a
                    # saved template edit shows up in every preview
                    # immediately with no stale text.
                    subject, body = assemble_email(
                        slug,
                        row.get("first_name") or "",
                        company,
                        row.get("opening_line") or "",
                        subject_template=current_subject,
                        body_template=current_body,
                    )
                    full_text = f"Subject: {subject}\n\n{body}"
                    st.code(full_text, language=None)
                except Exception:
                    st.caption(
                        "Couldn't assemble the full email preview — showing "
                        "the saved opening line only."
                    )
                    st.code(row.get("opening_line") or "", language=None)

        approve_cols = st.columns(2, gap="small")
        approve_selected_clicked = approve_cols[0].button(
            f"Approve Selected ({len(selected_ids)})",
            type="secondary",
            icon=":material/send:",
            disabled=approve_disabled or not selected_ids,
        )
        approve_all_clicked = approve_cols[1].button(
            f"Approve All ({n})",
            type="primary",
            icon=":material/send:",
            disabled=approve_disabled,
        )

        # D-09: both buttons open the confirmation dialog rather than firing
        # an Apollo call directly — see the module docstring for why this is
        # a deliberate exception to this app's immediate-fire button
        # convention (irreversibility: real emails send).
        if approve_selected_clicked:
            _confirm_enrollment_dialog(selected_ids, selected_path)
        if approve_all_clicked:
            _confirm_enrollment_dialog([r["id"] for r in rows], selected_path)
