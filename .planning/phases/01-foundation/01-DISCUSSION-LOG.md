# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-20
**Phase:** 1-Foundation
**Areas discussed:** Health check gating

---

## Health check gating

| Option | Description | Selected |
|--------|-------------|----------|
| Hard block | Nothing else in the app is usable until the Apollo key check passes | ✓ |
| Warning banner only | Show a red banner but let the teammate poke around other screens | |

**User's choice:** Hard block on invalid/missing Apollo API key.

| Option | Description | Selected |
|--------|-------------|----------|
| Block sending only | Discovery/drafting still usable, final send/enroll disabled until deliverability passes | ✓ |
| Hard block everything | Same treatment as a bad API key | |
| Warning only, never blocks | Always informational | |

**User's choice:** Block sending only, on failed mailbox deliverability (SPF/DKIM/DMARC).

| Option | Description | Selected |
|--------|-------------|----------|
| Warning only | Show low balance clearly, don't block — DISC-04 is the real spending gate | ✓ |
| Block discovery/enrichment | Prevent starting a new campaign below a threshold | |

**User's choice:** Warning only, on zero/low Apollo credit balance.

| Option | Description | Selected |
|--------|-------------|----------|
| Always the landing page | Teammate always sees status first, every session | ✓ |
| On-demand only | App opens straight to campaign flow; status lives in a settings tab | |

**User's choice:** Health check page is always the landing screen on boot.

**Notes:** All four questions resolved with the recommended option. No pushback or alternate rationale offered.

---

## Claude's Discretion

- Mailbox deliverability check method (DNS lookup vs. self-attestation checkbox) — user chose "I'm ready for context" over exploring this area further.
- Dedup registry scope (free-domain exclusion) — same.
- Error message design (banner + next-step hint) — same.

See CONTEXT.md `<decisions>` → "Claude's Discretion" for the specific defaults chosen and rationale.

## Deferred Ideas

None — discussion stayed within phase scope.
