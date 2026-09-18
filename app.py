"""Streamlit entrypoint for the Outreach Agent.

Boot sequence on every run (per 01-RESEARCH.md Architecture Diagram):
1. ensure_schema() — auto-create the SQLite DB with no manual setup (SC-3).
2. Secrets presence gate — a missing APOLLO_API_KEY or ANTHROPIC_API_KEY
   renders a plain-language banner and hard-stops before any navigation is
   registered (SC-2).
3. Register st.navigation with the System Health page as the default landing
   screen (D-04). The actual Apollo/mailbox check rendering — including the
   D-01 hard block on an *invalid* (not just missing) key — lives in
   pages/health_page.py so the credit/mailbox cards can render once Apollo
   passes.

NEVER log or print the api_key (T-04-02).
"""
from __future__ import annotations

import streamlit as st

from db.schema import ensure_schema

# 1. Schema bootstrap — idempotent, safe on every boot (SC-3).
ensure_schema()

# 2. Secrets presence gate (SC-2). This only checks that the key is *set*;
#    validity against Apollo's API is checked inside health_page.py (D-01).
apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY")

if not apollo_key:
    st.error(
        "APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
        "Community Cloud secrets console (production)."
    )
    st.stop()

if not anthropic_key:
    st.error(
        "ANTHROPIC_API_KEY is not set. Add it to .streamlit/secrets.toml (local) or the "
        "Community Cloud secrets console (production)."
    )
    st.stop()

# 3. Gated navigation (D-04) — System Health is the only page in Phase 1 and
#    is always the default landing screen.
pages = {
    "Health": [st.Page("pages/health_page.py", title="System Health", default=True)],
    "Discovery": [st.Page("pages/discovery_page.py", title="Contact Discovery")],
    "Review Queue": [st.Page("pages/review_queue_page.py", title="Review Queue")],
    # Phase 4 will append the remaining real page here (Campaign Dashboard)
    # once the Apollo health gate passes.
}

pg = st.navigation(pages)
pg.run()
