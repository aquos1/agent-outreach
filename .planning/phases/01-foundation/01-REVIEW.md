---
phase: 01-foundation
reviewed: 2026-07-21T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - db/schema.py
  - apollo/client.py
  - mailbox/dns_checks.py
  - app.py
  - pages/health_page.py
  - apollo/__init__.py
  - db/__init__.py
  - mailbox/__init__.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 01-foundation: Code Review Report

**Reviewed:** 2026-07-21T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the Phase 1 foundation surface: SQLite schema bootstrap, the Apollo health/credit client, DNS-based mailbox deliverability checks, the Streamlit entrypoint, and the System Health page. `apollo/__init__.py`, `db/__init__.py`, and `mailbox/__init__.py` are empty package markers with nothing to review.

No Critical/security-class findings (no injection, no hardcoded secrets, no unsafe eval, API keys are never logged). The main defects are broken "never raises" contracts in `apollo/client.py` and `mailbox/dns_checks.py` — both modules explicitly promise in their docstrings that external-call failures degrade to a tuple rather than propagating, but each has at least one code path that can still raise an unhandled exception. Today these are masked because `pages/health_page.py` wraps every call site in a blanket `try/except Exception`, but that's an incidental safety net, not a guarantee — any future caller (e.g. a Phase 2+ page) that reuses these functions without the same wrapper will get an unhandled traceback in front of a non-technical user, which is exactly what these modules were designed to prevent. There's also a real logic bug in the credit-balance parsing (`0 or fallback`) that would misreport a genuine "0 credits" state as "unavailable" if the endpoint's response shape ever matches the code's assumption.

## Warnings

### WR-01: `check_apollo_health` can raise despite "never raises" contract

**File:** `apollo/client.py:41`
**Issue:** The module docstring (lines 7-9) explicitly guarantees "network failures and unexpected response shapes degrade to a plain-language banner message instead of propagating a stack trace." The `try/except requests.RequestException` block (lines 25-32) only wraps the `requests.get()` call. `data = resp.json()` on line 41 runs *outside* that block. If Apollo (or a proxy/CDN in front of it) ever returns HTTP 200 with a non-JSON body, `resp.json()` raises `requests.exceptions.JSONDecodeError` (a `RequestException` subclass, but raised after the try/except has already exited), which is not caught here. It currently doesn't crash the app only because `pages/health_page.py` happens to wrap every call site in its own `try/except Exception` — that's a caller-side accident, not a guarantee this function provides.
**Fix:**
```python
try:
    data = resp.json()
except ValueError:
    return False, "Apollo connection failed — unexpected response from Apollo."
```

### WR-02: `get_credit_balance` — unguarded `resp.json()` and a falsy-value logic bug

**File:** `apollo/client.py:65,74`
**Issue:** Same unguarded-`resp.json()` issue as WR-01 (line 65). Additionally, line 74 is a real logic bug:
```python
credits = data.get("credits") or data.get("credit_balance")
```
If Apollo ever returns `{"credits": 0}` (a legitimate "you have zero credits left" state — arguably the *most* important value to surface to the user), `0 or data.get("credit_balance")` evaluates the fallback because `0` is falsy in Python. If `"credit_balance"` is absent, this silently becomes `None`, and the function reports "Credit balance unavailable (unexpected response shape)" instead of correctly showing `0`. This masks the exact scenario (out of credits) the health page exists to surface.
**Fix:**
```python
try:
    data = resp.json()
except ValueError:
    return None, "Credit balance unavailable (unexpected response shape)"

credits = data.get("credits")
if credits is None:
    credits = data.get("credit_balance")
if credits is None:
    return None, "Credit balance unavailable (unexpected response shape)"
return credits, "OK"
```

### WR-03: `mailbox/dns_checks._txt_records` doesn't catch all resolution/decoding failures

**File:** `mailbox/dns_checks.py:40-49`
**Issue:** The function's docstring promises "[] on no-record/error (not exception)," but the `except` clause on line 48 only catches `NXDOMAIN`, `NoAnswer`, and `Timeout`. Other realistic failure modes are left unhandled:
- `dns.resolver.NoNameservers` (all configured nameservers refused/failed) is not a subclass of any caught exception.
- `_valid_domain()` (lines 22-37) rejects empty/whitespace/`://`/no-dot inputs but does not reject malformed hostnames like `"sub..example.com"` (double dot) or a leading/trailing dot pathology, which cause `dns.name.EmptyLabel` / `dns.exception.SyntaxError` inside `dns.resolver.resolve`, not caught here.
- Line 45, `part.decode()`, uses the default UTF-8 codec with no `errors=` handling; a TXT record containing non-UTF-8 bytes raises `UnicodeDecodeError`, also uncaught.

Any of these propagates out of `check_spf`/`check_dmarc`/`check_dkim` (none of which have their own try/except) and is currently only caught by `pages/health_page.py`'s blanket `except Exception` around each call — again an incidental safety net rather than a guarantee this module provides.
**Fix:**
```python
def _txt_records(name: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT")
        return [
            "".join(part.decode(errors="replace") for part in r.strings)
            if hasattr(r, "strings") else str(r)
            for r in answers
        ]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
            dns.resolver.NoNameservers, dns.exception.DNSException):
        return []
```
(`dns.exception.DNSException` is the common base class for `Timeout` and the DNS-syntax errors, so catching it replaces the three specific classes and closes the gap in one change.)

### WR-04: Secrets/validity gate is duplicated and not enforced on `health_page.py` itself

**File:** `pages/health_page.py:28-29`
**Issue:** `app.py` gates on a missing `APOLLO_API_KEY` (lines 26-34) *before* registering `st.navigation`, so under the normal app flow `health_page.py` never runs with `apollo_key` unset. However, `health_page.py` independently re-fetches `apollo_key = st.secrets.get("APOLLO_API_KEY")` (line 28) with no local guard. This file has no defense-in-depth of its own — it relies entirely on `app.py`'s ordering never changing. If a future refactor moves the pages dict construction earlier, adds another entry page, or someone runs `streamlit run pages/health_page.py` directly during local dev, `apollo_key` can be `None` here with no explicit handling before it's passed into `check_apollo_health(None)`.
**Fix:** Add a local guard at the top of `health_page.py`, independent of `app.py`:
```python
apollo_key = st.secrets.get("APOLLO_API_KEY")
if not apollo_key:
    st.error("APOLLO_API_KEY is not set. Add it to .streamlit/secrets.toml.")
    st.stop()
```

## Info

### IN-01: `sending_domain` fetched but unused in `app.py`

**File:** `app.py:27`
**Issue:** `sending_domain = st.secrets.get("SENDING_DOMAIN")` is assigned but never referenced anywhere in `app.py`. It's independently re-fetched in `pages/health_page.py:29`, where it's actually used. The assignment in `app.py` is dead code that adds confusion about where the "real" read happens.
**Fix:** Remove the unused line from `app.py`, or if it's meant to be a future validation point, add a comment explaining why it's read here without being used.

### IN-02: Credit-balance status message discarded

**File:** `pages/health_page.py:76`
**Issue:** `credits, _credit_msg = get_credit_balance(apollo_key)` discards the distinguishing message (`"...network error"` vs `"...unexpected response shape"`) from `apollo/client.py`. Both cases render the same generic caption ("Credit balance unavailable — this won't stop you from using the app."), which matches the UI spec, but the more specific message is thrown away entirely rather than being logged, making future debugging of "why is this always unavailable" harder than necessary.
**Fix:** Consider logging `_credit_msg` (not to the UI, just to server-side logs) when `credits is None`, so unexpected-shape vs network-error can be told apart without re-instrumenting later.

### IN-03: DKIM self-attestation checkbox state isn't persisted

**File:** `pages/health_page.py:137`
**Issue:** `st.checkbox("I've configured DKIM for this domain")` has no `key=`, isn't written to `st.session_state`, and isn't stored anywhere (DB or otherwise). This matches Phase 1's stated scope (per the module docstring, "no send/enroll actions exist yet in Phase 1 for this to gate") so it's not a bug today. But per `01-UI-SPEC.md`, the checkbox exists specifically so a later phase can gate campaign sends on it — as written, the confirmation is fully ephemeral and reset on every rerun, so there is currently no mechanism for a future phase to recover "did the user confirm DKIM."
**Fix:** No action required for Phase 1; flag for the phase that implements the send/enroll gate (D-02) to persist this (e.g., a `dkim_confirmed` flag in `st.session_state` or a settings table), rather than assuming the checkbox alone will suffice.

### IN-04: Declared foreign key is never enforced

**File:** `db/schema.py:35`
**Issue:** `email_events.prospect_id INTEGER NOT NULL REFERENCES prospect(id)` declares a foreign key, but `ensure_schema()` never issues `PRAGMA foreign_keys = ON` on the connection it creates (lines 84-90). SQLite disables FK enforcement by default per-connection, so this constraint is currently decorative — nothing prevents inserting an `email_events` row with a `prospect_id` that doesn't exist in `prospect`. Harmless today since no delete paths exist yet, but worth fixing before any delete/cleanup logic is added on `prospect`.
**Fix:**
```python
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON")
```
(Note this only affects the connection opened in `ensure_schema()`; every other connection opened elsewhere in the app will also need this pragma set for it to have any effect at runtime.)

---

_Reviewed: 2026-07-21T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
