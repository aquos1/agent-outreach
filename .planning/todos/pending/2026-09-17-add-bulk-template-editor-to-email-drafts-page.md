---
created: 2026-09-17T19:21:15.064Z
title: Add bulk template editor to Email Drafts page
area: ui
files:
  - pages/discovery_page.py
  - personalization/templates.py
---

## Problem

Teammates need a way to manually edit the per-path email **template** directly on the "Email Drafts" section of the Discovery page — and have that edit apply to ALL emails in the current batch/path before send, not just one contact's draft.

This is distinct from `REVIEW-01` ("Individual approve/edit/skip per contact in review queue"), which is already logged in `REQUIREMENTS.md` as Out of Scope for v1 (deferred to v2). REVIEW-01 is per-contact editing; this idea is bulk/global template editing — editing the shared template that `personalization/templates.py`'s `assemble_email()` uses for every contact in a path.

Currently `PATH_TEMPLATES` in `personalization/templates.py` is a hardcoded dict of static strings with no UI, no persistence, and no edit path. Raised by the developer during Phase 3's human-verify checkpoint (03-04) while reviewing live generated drafts — explicitly scoped for later, not part of Phase 3.

Open design questions for whenever this gets planned:
- Where do edited templates persist (DB table vs. config/session state)?
- Does editing the template retroactively regenerate already-drafted contacts (`status='drafted'`), or only apply to future `assemble_email()` calls?
- Is this per-path, per-campaign-run, or global across all future campaigns?
- How does this interact with Phase 4's Review Queue (`QUEUE-01..04`, currently bulk-approve-only, no editing)?

## Solution

TBD — likely needs its own `/gsd:discuss-phase` or `/gsd:quick` scoping pass rather than being folded silently into Phase 4. Candidate hook point: the "Email Drafts" section rendered in `pages/discovery_page.py` (added by plan 03-04), before/alongside the eventual Review Queue page.
