"""Review Queue page (QUEUE-01, QUEUE-02) — path-scoped, read-only view of
every drafted email awaiting a teammate's review.

Composes discovery/logic.py (PATH_OPTIONS/PATH_CONFIG — reused, never
re-derived), db/prospects.py (get_drafted_by_path, this plan's QUEUE-01
source query), and personalization/templates.py (assemble_email) into the
first vertical slice of Phase 4: a teammate can open this page, pick a
path, and see every status='drafted' contact for that path with the full
assembled email behind a per-row "View draft" expander.

D-11: the path selector always has exactly one path selected (index=0, no
"nothing chosen" state) — unlike Discovery's optional-until-chosen picker,
this page has no meaningful "do nothing" state, and a future plan's template
editor needs an unambiguous single-path target at all times.

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
from discovery.logic import PATH_CONFIG, PATH_OPTIONS
from personalization.templates import assemble_email

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

# Template editor section lands here in plan 04-02 (D-03) — no widgets yet.

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
                    # Plan 04-02 swaps this for the override-aware version
                    # (template_override lookup instead of PATH_TEMPLATES).
                    subject, body = assemble_email(
                        slug,
                        row.get("first_name") or "",
                        company,
                        row.get("opening_line") or "",
                    )
                    full_text = f"Subject: {subject}\n\n{body}"
                    st.code(full_text, language=None)
                except Exception:
                    st.caption(
                        "Couldn't assemble the full email preview — showing "
                        "the saved opening line only."
                    )
                    st.code(row.get("opening_line") or "", language=None)
