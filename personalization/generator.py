"""Claude Haiku opening-line generation: grounded prompt, sparse-title
detection, and the shared fallback path used by both sparse-data (D-07) and
API-failure (D-14) cases.

Every function here returns a typed tuple and never raises — an Anthropic
SDK failure degrades to a plain-language message instead of propagating a
stack trace, mirroring apollo/client.py's never-raise contract.

NEVER log or print the api_key (same rule as APOLLO_API_KEY).
"""
from __future__ import annotations

import anthropic

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "You write a single opening sentence for a cold outreach email from a "
    "student organization to a business contact. Tone: warm but professional "
    "-- conversational, not stiff corporate boilerplate, not casual or slang.\n\n"
    "You will be given the contact's title and company inside <contact> tags. "
    "You may reference ONLY the exact title and company text given -- do not "
    "infer, assume, or add any other detail (such as background, achievements, "
    "role level, or location) that is not literally present in the tags. "
    "If you are unsure whether something is grounded in the given data, leave "
    "it out.\n\n"
    "Output ONLY the single sentence itself -- no quotation marks, no preamble "
    "like 'Here's an opening line:', no labels. One sentence, 20-30 words."
)

# Fallback references ONLY company (the other allowed D-06 field), never
# title, since title is by definition the unreliable/absent field in every
# branch that reaches this fallback (D-07 sparse title, D-14 API failure).
FALLBACK_LINE = (
    "I hope this reaches you at a good time -- I wanted to reach out to "
    "{company} directly."
)

# [ASSUMED] The exact set of placeholder strings Apollo may return for a
# missing title is not documented anywhere in Apollo's API reference -- this
# blocklist is a reasonable default, not a verified Apollo behavior. Widen it
# if real data surfaces other placeholder patterns during execution.
_PLACEHOLDER_TITLES = {"", "n/a", "na", "unknown", "-", "none", "tbd"}

# D-16: strict-majority default. CONTEXT.md left the exact number to the
# planner; RESEARCH.md Open Question 2 recommends 0.5. Planner-set, tunable.
FALLBACK_BANNER_THRESHOLD = 0.5

# Path-specific framing instruction, injected alongside the <contact> tags.
# This is NOT a D-06 grounding-scope change -- it never adds a fact about the
# contact beyond title/company. It's a fixed instruction about the email's
# business purpose, which the generic SYSTEM_PROMPT has no way to know: the
# sponsorship paths ask the company for support, while client_sourcing offers
# the company free help -- the opposite direction. Without this, Haiku
# defaults to a "we'd love to learn about your approach" framing regardless
# of path, which reads as nonsensical for client_sourcing (the org is
# offering to solve a problem FOR the company, not asking to learn from it).
PATH_FRAMING = {
    "club_sponsorship": (
        "This email asks the company to become an annual sponsor, offering "
        "recruiting access and brand visibility in return. Write the opener "
        "with genuine interest in their work as a natural hook."
    ),
    "productthon": (
        "This email asks the company to sponsor a one-day student "
        "product-thon, offering recruiting access and brand visibility in "
        "return. Write the opener with genuine interest in their work as a "
        "natural hook."
    ),
    "client_sourcing": (
        "This email offers the company a free student consulting team to "
        "help ship one of THEIR OWN internal product initiatives -- the "
        "organization is offering to help them, not asking to learn from "
        "them or be mentored by them. Do not frame the opener around "
        "wanting to learn about their approach, philosophy, or work. "
        "Instead, use their title and company only as a natural hook for "
        "why they would be the right person to talk to about a project "
        "like this -- never invent or guess what that initiative might be."
    ),
}


def make_client(api_key: str) -> anthropic.Anthropic:
    """Construct the Anthropic client once, with D-15/Pitfall-3 overrides.

    The retry count is set to exactly one, implementing D-15's "one retry
    before falling back" using the SDK's own built-in retry mechanism -- do
    not hand-roll a retry loop. The per-call timeout is bounded well below
    the SDK's 10-minute default, which would stall a 50-iteration synchronous
    loop on a single hung call.
    """
    return anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=20.0)


def _is_sparse_title(title: str | None) -> bool:
    """D-07: title missing, null, or placeholder-looking.

    [ASSUMED] The exact set of placeholder strings Apollo may return for a
    missing title is not documented anywhere in Apollo's API reference --
    this heuristic (blank/whitespace-only or a small common-placeholder
    blocklist) is a reasonable default, not a verified Apollo behavior. Widen
    it if real data shows other patterns during execution.
    """
    if not title or not title.strip():
        return True
    return title.strip().lower() in _PLACEHOLDER_TITLES


def generate_opening_line(
    client, title: str, company: str, path_slug: str
) -> tuple[str | None, str]:
    """Call Claude Haiku for one grounded opening sentence. Never raises.

    Sends ONLY title and company inside <contact> tags -- no industry,
    seniority, or any other field (D-06). `path_slug` selects a fixed
    business-framing instruction (PATH_FRAMING) describing the email's
    actual ask for that path -- this is not a new fact about the contact,
    so it does not reopen D-06's grounding-scope restriction. Returns
    (line_or_None, message); the caller applies the D-07/D-14 fallback on a
    None line.
    """
    framing = PATH_FRAMING.get(path_slug, PATH_FRAMING["club_sponsorship"])
    user_prompt = (
        f"<contact><title>{title}</title><company>{company}</company></contact>\n"
        f"<framing>{framing}</framing>"
    )
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIConnectionError:
        # Covers anthropic.APITimeoutError too (it subclasses APIConnectionError).
        return None, "Personalization request failed — connection error."
    except anthropic.RateLimitError:
        return None, "Personalization rate-limited."
    except anthropic.APIStatusError as e:
        return None, f"Personalization failed — status {e.status_code}."

    text_blocks = [b.text for b in message.content if b.type == "text"]
    line = "".join(text_blocks).strip().strip('"').strip()
    if not line:
        return None, "Personalization returned empty output."
    return line, "OK"


def build_opening_line(
    client, title: str | None, company: str, path_slug: str
) -> tuple[str, str]:
    """Single decision point both fallback triggers flow through.

    D-07 (sparse title) and D-14 (API failure) share one fallback path.
    `path_slug` is threaded through to generate_opening_line so the prompt
    carries the correct business-framing instruction for this path (see
    PATH_FRAMING). Returns (opening_line, "ai" | "fallback"). Never raises.
    """
    if _is_sparse_title(title):
        return FALLBACK_LINE.format(company=company), "fallback"

    line, _message = generate_opening_line(client, title, company, path_slug)
    if line is None:
        return FALLBACK_LINE.format(company=company), "fallback"
    return line, "ai"


def should_warn_fallback_rate(fallback_count: int, total: int) -> bool:
    """D-16: does this batch's fallback fraction exceed the warning threshold?

    False for an empty batch (no division by zero). Strictly greater than
    FALLBACK_BANNER_THRESHOLD, so an exact 50/50 split does not warn.
    """
    if total == 0:
        return False
    return fallback_count / total > FALLBACK_BANNER_THRESHOLD
