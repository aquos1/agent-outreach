"""Review Queue page (QUEUE-01, QUEUE-02) — path-scoped view of every
drafted email awaiting a teammate's review, plus a shared per-path template
editor (D-03 through D-06).

Composes discovery/logic.py (PATH_OPTIONS/PATH_CONFIG — reused, never
re-derived), db/prospects.py (get_drafted_by_path, 04-01's QUEUE-01 source
query), db/templates_store.py (get_template/save_template_override, this
plan's D-05 persistence), and personalization/templates.py
(validate_template_fields, override-aware assemble_email) into the second
vertical slice of Phase 4: a teammate can open this page, pick a path, edit
the shared subject/body for that path in one place, and see every
status='drafted' contact for that path with the full assembled email
(reflecting the saved override) behind a per-row "View draft" expander.

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

D-10: rows render as a manual st.columns row loop (not st.dataframe) so a
later plan can swap a row's Select cell for a status badge in place — this
plan leaves that cell blank (see the loop below) since the checkbox/badge
swap is 04-04's job, not this plan's.

This page never hard-stops the run — a database read failure or a
malformed row must never blank the whole page; both degrade to a
plain-language st.error/inline caption instead, matching
pages/discovery_page.py's established never-hard-stop convention.

NEVER log or print the api_key.
"""
from __future__ import annotations

import streamlit as st

from db.prospects import get_drafted_by_path
from db.templates_store import get_template, save_template_override
from discovery.logic import PATH_CONFIG, PATH_OPTIONS
from personalization.templates import PATH_TEMPLATES, assemble_email, validate_template_fields

st.title("Review Queue")
st.caption(
    "Review every drafted email, tweak the shared template if needed, and "
    "approve the ones you're ready to send."
)

# Read once; never re-fetched mid-handler. Unused this plan — establishes
# the same st.secrets.get() convention discovery_page.py uses, ahead of the
# Apollo calls a later Phase 4 plan adds to this page. NEVER log/print this.
apollo_key = st.secrets.get("APOLLO_API_KEY")

# D-11: always exactly one path selected — no placeholder/index=None, since
# this page (unlike Discovery) has no meaningful "nothing chosen" state.
selected_path = st.selectbox("Outreach path", PATH_OPTIONS, index=0)
slug = PATH_CONFIG[selected_path]["slug"]

st.divider()

# D-03: template editor lives here, above the queue, below the path
# selector — never on Discovery's read-only Email Drafts section.
if "template_result" not in st.session_state:
    st.session_state.template_result = None  # None = no save attempted yet this session

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

        for row in rows:
            name = row.get("name") or "—"
            company = row.get("company") or "—"
            title = row.get("title") or "—"

            row_cols = st.columns([1, 3, 3, 3, 2])
            row_cols[0].write("")  # Select checkbox lands here in plan 04-04
            row_cols[1].write(name)
            row_cols[2].write(company)
            row_cols[3].write(title)
            row_cols[4].write("")  # Status badge lands here in plan 04-04

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
