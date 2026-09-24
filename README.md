# Outreach Agent

An AI-assisted outreach tool for student org teammates. You pick a goal, describe who you want to reach, and the app finds contacts through Apollo.io, writes a personalized opening line for each one with Claude, and enrolls the approved contacts into an Apollo email sequence. No code required to run a campaign.

It supports three outreach goals:

| Path | Slug | Used for |
|------|------|----------|
| Club Sponsorship | `club_sponsorship` | Sponsors for the club |
| Productthon Sponsorship | `productthon` | Sponsors for the productthon event |
| Client Sourcing | `client_sourcing` | Companies to take on as project clients |

---

## How it works (end to end)

```
System Health  ──►  Contact Discovery  ──►  Review Queue  ──►  Apollo Sequence
(key, credits,      (search → enrich →      (edit template,     (Apollo sends the
 SPF/DKIM/DMARC)     AI drafts)              approve, enroll)    emails)
```

1. **System Health** (landing page): checks that the Apollo API key works, shows your remaining Apollo credits, and checks SPF, DMARC and DKIM for your sending domain. If the Apollo key is invalid, the app stops here with a plain-language error.
2. **Contact Discovery**
   - Pick a path, then type a company type and a target role in plain text (comma-separated).
   - **Find Contacts** runs a free Apollo search (0 credits) and shows how many contacts it found and how many credits enrichment will cost. It keeps only people Apollo has an email for, and caps the batch at 50.
   - People or company domains you've already contacted are removed automatically. Free email domains such as gmail.com never count as a company match.
   - **Enrich & Continue** spends credits (1 per person matched) to get verified emails. It then generates a draft for every contact straight away: Claude Haiku writes a one-sentence opening line based only on the person's title and company, and the app drops it into that path's email template. If a title is missing or too vague to use, the app falls back to a generic line and warns you when too many contacts in the batch needed the fallback.
3. **Review Queue**
   - Choose a path to see every drafted email waiting for review.
   - Edit that path's shared subject and body. The edit is saved as the new default for the path and survives restarts. The editor won't save a template that is missing `{first_name}`, `{company}` or `{opening_line}`.
   - Tick the contacts to send, confirm once, and the app will:
     1. create the Apollo contacts in bulk,
     2. write each contact's AI opening line to an Apollo custom field,
     3. enroll them in that path's pre-built Apollo sequence.
   - Each row then shows **Enrolled** or **Skipped**, along with Apollo's reason for any skip.
4. **Apollo** handles the actual sending, the timing of follow-ups, tracking and unsubscribes. This app never sends email itself.

Every prospect is tracked in SQLite through these statuses:
`found → selected → enriched → contact_created → drafted → approved → sequenced`

---

## What's included

```
app.py                      Streamlit entrypoint: creates the DB, checks secrets, sets up page navigation
pages/
  health_page.py            System Health: Apollo key, credits, mailbox DNS
  discovery_page.py         Contact Discovery: search → enrich → AI drafts
  review_queue_page.py      Review Queue: template editor, approval, sequence enrollment
apollo/client.py            Apollo REST client: health, credits, search, bulk_match,
                            bulk contact create, custom fields, add-to-sequence (429 backoff)
discovery/logic.py          Paths, turning free text into search filters, email filter, credit estimate
personalization/
  generator.py              Claude Haiku opening-line generation + sparse-title fallback
  templates.py              Per-path email templates, assembly, merge-field validation
review/logic.py             Builds Apollo payloads and matches Apollo's responses back to local rows
mailbox/dns_checks.py       SPF / DMARC / DKIM lookups via public DNS
db/
  schema.py                 Self-migrating SQLite schema (prospect, email_events,
                            template_override, contacted_registry view)
  prospects.py              Dedup filter, prospect inserts and status updates
  templates_store.py        Saves template edits per path
tests/                      pytest suite for the modules above (74 tests)
.streamlit/
  config.toml               Theme
  secrets.toml.example      Template for required secrets
spec.MD, apollo.MD          Original product spec and Apollo API notes
.planning/                  Planning docs: roadmap, requirements, per-phase plans
```

**Stack:** Python 3.12+, Streamlit, `requests`, `dnspython`, Anthropic SDK (`claude-haiku-4-5-20251001`), SQLite (stdlib).

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then fill in the values (see below)

streamlit run app.py
```

The SQLite database (`db/outreach.db`) is created automatically on first launch.

### Secrets (`.streamlit/secrets.toml`, gitignored)

| Key | What it is |
|-----|-----------|
| `APOLLO_API_KEY` | Apollo **Master** API key (Settings → Integrations → API Keys) |
| `ANTHROPIC_API_KEY` | Anthropic API key for opening-line generation |
| `SENDING_DOMAIN` | Domain you send from; used for SPF/DMARC/DKIM checks |
| `APOLLO_SEQUENCE_ID_CLUB_SPONSORSHIP` | Apollo sequence ID for the Club Sponsorship path |
| `APOLLO_SEQUENCE_ID_PRODUCTTHON` | Apollo sequence ID for the Productthon path |
| `APOLLO_SEQUENCE_ID_CLIENT_SOURCING` | Apollo sequence ID for the Client Sourcing path |
| `APOLLO_SENDING_EMAIL_ACCOUNT_ID` | Apollo ID of the mailbox that sends the sequence |

The app won't start without the Apollo and Anthropic keys. If a sequence or mailbox ID is missing, only the Review Queue's approve button is disabled; the rest of the app still works.

The sequences themselves are **built in Apollo's UI, not through the API**. Create one sequence per path and include the opening-line custom field in the first email.

### Deploying

Push to GitHub and deploy on Streamlit Community Cloud. Paste the same secrets into the Cloud secrets console. Note: Community Cloud does not guarantee that the SQLite file survives a redeploy.

---

## Tests

```bash
pytest
```

The tests cover the pure logic, the Apollo client (with mocked HTTP), the schema and migrations, dedup, DNS checks, templates, personalization and review reconciliation.

---

## Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1. Foundation | Health checks, SQLite registry | ✅ Done |
| 2. Contact Discovery | Paths, search, enrichment, dedup | ✅ Done |
| 3. AI Personalization | Haiku opening lines, templates, drafts | ✅ Done |
| 4. Review Queue & Enrollment | Template editor, approval, Apollo sequencing | 🚧 Built; waiting on a live check with real sequence IDs |
| 5. Analytics Dashboard | Open/reply rates per campaign from Apollo | ⏳ Not started |

## Cost notes

- Apollo search: free. Enrichment: 1 credit per matched person. Phone numbers are never requested (they would cost 8 extra credits each).
- Claude Haiku: about $0.04 per 50-contact campaign.
