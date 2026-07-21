"""System Health landing page (D-04).

Renders the three health indicators per 01-UI-SPEC.md (authoritative
rendering contract — exact copy/icons locked there):

1. Apollo Connection — hard block (D-01): a failure renders a banner and
   calls st.stop(), so nothing below this card renders until it passes.
2. Apollo Credits — informational only (D-03): never blocks, regardless of
   balance or availability.
3. Mailbox Deliverability (SPF/DMARC/DKIM) — soft block (D-02): renders
   pass/fail/unknown but never calls st.stop(); no send/enroll actions exist
   yet in Phase 1 for this to gate.

Every external check call (Apollo, DNS) is wrapped in try/except so an
unexpected exception renders a plain-language st.error banner instead of a
Streamlit traceback (SC-2, T-04-01).
"""
from __future__ import annotations

import streamlit as st

from apollo.client import check_apollo_health, get_credit_balance
from mailbox.dns_checks import check_dkim, check_dmarc, check_spf

st.title("System Health")
st.caption("Checked automatically every time the app loads.")

apollo_key = st.secrets.get("APOLLO_API_KEY")
sending_domain = st.secrets.get("SENDING_DOMAIN")

with st.spinner("Checking Apollo connection and mailbox setup..."):

    # ------------------------------------------------------------------
    # Apollo Connection — hard block (D-01)
    # ------------------------------------------------------------------
    st.header("Apollo Connection")
    with st.status("Apollo API connection", expanded=True) as status:
        try:
            apollo_ok, apollo_banner = check_apollo_health(apollo_key)
        except Exception:
            apollo_ok, apollo_banner = (
                False,
                "Apollo connection failed — check your internet connection and try again.",
            )

        if apollo_ok:
            status.update(
                label="Apollo API connection: OK",
                state="complete",
                expanded=False,
            )
            st.success(apollo_banner, icon=":material/check_circle:")
        else:
            st.error(apollo_banner, icon=":material/cancel:")
            st.caption(
                "The rest of the app is unavailable until this is fixed. "
                "Fix the issue above, then click Recheck Connection."
            )
            status.update(
                label="Apollo API connection: FAILED",
                state="error",
                expanded=True,
            )

    st.button("Recheck Connection", icon=":material/refresh:")

    if not apollo_ok:
        # D-01 hard block — nothing below this renders until Apollo passes.
        st.stop()

    # ------------------------------------------------------------------
    # Apollo Credits — informational only, never blocks (D-03)
    # ------------------------------------------------------------------
    st.header("Apollo Credits")
    try:
        credits, _credit_msg = get_credit_balance(apollo_key)
    except Exception:
        credits = None

    if credits is not None:
        st.metric(label="Apollo Credits Remaining", value=credits)
    else:
        st.caption("Credit balance unavailable — this won't stop you from using the app.")

    # ------------------------------------------------------------------
    # Mailbox Deliverability — soft block, never st.stop() (D-02)
    # ------------------------------------------------------------------
    st.header("Mailbox Deliverability")
    st.caption(
        "These checks won't stop you from using the app today, but a campaign "
        "can't be sent until they pass (or DKIM is manually confirmed)."
    )

    try:
        spf_ok, spf_msg = check_spf(sending_domain)
    except Exception:
        spf_ok, spf_msg = False, "SPF check failed unexpectedly — please try again."

    if spf_ok:
        st.success(spf_msg, icon=":material/check_circle:")
    else:
        st.warning(
            "SPF: not found — add a TXT record starting with v=spf1 to your "
            "sending domain's DNS settings before sending a campaign.",
            icon=":material/error:",
        )

    try:
        dmarc_ok, dmarc_msg = check_dmarc(sending_domain)
    except Exception:
        dmarc_ok, dmarc_msg = False, "DMARC check failed unexpectedly — please try again."

    if dmarc_ok:
        st.success(dmarc_msg, icon=":material/check_circle:")
    else:
        st.warning(
            "DMARC: not found — add a TXT record starting with v=DMARC1 at "
            "_dmarc.<your-domain> before sending a campaign.",
            icon=":material/error:",
        )

    try:
        dkim_state, dkim_msg = check_dkim(sending_domain)
    except Exception:
        dkim_state, dkim_msg = "unknown", "DKIM check failed unexpectedly — please try again."

    if dkim_state == "pass":
        st.success(dkim_msg, icon=":material/check_circle:")
    else:
        st.warning(
            "DKIM: could not auto-detect. This doesn't necessarily mean it's "
            "misconfigured — some providers use custom selectors. If you've "
            "already set up DKIM with your email provider, check the box "
            "below to confirm.",
            icon=":material/help:",
        )
        st.checkbox("I've configured DKIM for this domain")
