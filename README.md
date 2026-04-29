# DialTone Outreach

Cold email sequencer for restaurant owner outreach. Built on AWS SES + Supabase.

Imports owner contacts from Apollo and runs a 5-email sequence with automatic timing logic — pausing the moment anyone replies. Includes a local web UI for non-technical reviewers to monitor outreach and update contact statuses.

---

## Stack

| Layer | Tool |
|-------|------|
| Email sending | AWS SES |
| Database | Supabase (PostgreSQL) |
| CLI | Click + Rich |
| Web UI (local) | FastAPI + Jinja2 + HTMX |
| Contact source | Apollo (restaurant owner contacts) |

---

## Project Structure

```
dialtone-outreach/
├── cli.py                      # Entry point — all commands live here
├── schema.sql                  # Run once in Supabase SQL editor
├── requirements.txt
├── .env.example                # Copy to .env and fill in credentials
├── outreach/
│   ├── config.py               # All settings loaded from .env
│   ├── db.py                   # Supabase client and query functions
│   ├── email_client.py         # AWS SES wrapper
│   ├── sequence.py             # Timing logic — who gets what email today
│   ├── templates.py            # All 5 email templates (Jinja2)
│   └── runner.py               # Orchestration loop + terminal dashboard
├── scripts/
│   └── import_contacts.py      # Apollo CSV importer
└── web/                        # Local FastAPI UI for non-technical reviewers
    ├── app.py                  # FastAPI application + routes
    ├── templates/              # Jinja2 page templates (HTMX-driven)
    └── static/                 # CSS + minimal JS
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Bytes0211/dialtone-outreach.git
cd dialtone-outreach
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
FROM_EMAIL=steve@dialtone.menu
CALENDLY_URL=https://calendly.com/your-link
```

### 3. Create the database

Open your [Supabase SQL editor](https://supabase.com/dashboard) and run the contents of `schema.sql`.

This creates:
- `contacts` table
- `email_log` table
- `contacts_due_for_outreach` view
- `contact_status_counts` view
- Auto-update trigger for `updated_at`

### 4. Verify SES sender identity

Your `FROM_EMAIL` must be verified in AWS SES before sending.

```bash
python -c "from outreach.email_client import verify_sender_identity; verify_sender_identity('steve@dialtone.menu')"
```

Check your inbox and click the verification link.

> **Note:** New AWS SES accounts are in sandbox mode (200 emails/day, verified recipients only).
> Request production access in the [SES console](https://console.aws.amazon.com/ses/home#/account)
> before running live outreach.

---

## Workflow

### Step 1 — Build your contact list

**Export from Apollo** (owner contact finder):
- Search: Title=Owner, Industry=Restaurants, Location=Nashville TN, Company size=1-50
- Save as `apollo_export.csv`

### Step 2 — Import

```bash
python cli.py import --source apollo --file apollo_export.csv

# Preview without writing
python cli.py import --source apollo --file apollo_export.csv --dry-run
```

### Step 3 — Preview today's run

Always dry-run first:

```bash
python cli.py run --dry-run
```

Output shows exactly which contacts would receive which email, with subject lines.

### Step 4 — Send

```bash
python cli.py run
```

Sends up to `DAILY_SEND_LIMIT` emails (default: 20). Ordered by `lead_score` descending — your hottest leads always go first.

### Step 5 — Monitor

```bash
# Status breakdown table
python cli.py status

# Conversion rates
python cli.py stats

# Look up a specific contact
python cli.py contact --email owner@rossieskitchen.com
python cli.py contact --domain rossieskitchen.com
```

---

## Email Sequence

| # | Timing | Subject | Purpose |
|---|--------|---------|---------|
| 1 | Day 0  | Friday nights at [Restaurant] | The opener — short, one question |
| 2 | Day 3  | The math on missed calls | Value add — the $87,500 stat |
| 3 | Day 7  | What other owners are saying | Social proof |
| 4 | Day 14 | Closing the loop | Breakup email — low pressure |
| 5 | Day 60 | Checking back in | Re-engage (openers only) |

**The sequence stops immediately if:**
- The contact replies (any email)
- The contact's status is set to `demo_booked`, `customer`, `pilot`, `not_interested`, or `invalid`

---

## Contact Statuses

| Status | Meaning |
|--------|---------|
| `new` | Imported, not yet emailed |
| `emailed_1` | Email #1 sent |
| `emailed_2` | Email #2 sent |
| `emailed_3` | Email #3 sent |
| `breakup_sent` | Breakup email sent |
| `re_engage` | Re-engage email sent |
| `replied` | Responded to any email — STOP sequence |
| `demo_booked` | Demo scheduled — STOP sequence |
| `pilot` | In pilot program — STOP sequence |
| `customer` | Paying customer — STOP sequence |
| `not_interested` | Explicitly opted out — STOP sequence |
| `invalid` | Bad email / not a real contact — STOP sequence |

Update status from the local web UI (see below) or directly in Supabase when contacts reply, book a demo, etc.

---

## Lead Scoring

Score contacts 1–5 to control outreach priority:

| Score | Meaning |
|-------|---------|
| 5 | Hot — demo booked or very engaged |
| 4 | Warm — replied, interested |
| 3 | Good fit, not yet contacted |
| 2 | Has contact info, lower fit |
| 1 | Minimal info, low priority |

Higher-scored contacts always send first when the daily limit is reached.

---

## Local Web UI

A lightweight FastAPI + Jinja2 + HTMX app for non-technical reviewers to monitor outreach and update contact statuses without touching the CLI or Supabase. Runs locally only — no auth, no public exposure.

### Start the server

```bash
uvicorn web.app:app --reload --port 8000
# then open http://localhost:8000
```

### Screens

| Screen | Purpose |
|--------|---------|
| **Dashboard** | Status counts, conversion funnel (Email → Demo → Pilot → Customer), emails sent today |
| **Contacts** | Searchable, filterable list (by status, lead score, city); click a row to open detail |
| **Contact detail** | Owner info, full email history (subject, sent, opened, replied), status edit buttons (`replied`, `demo_booked`, `pilot`, `customer`, `not_interested`, `invalid`), notes editor |
| **Run preview** | Read-only view of `cli.py run --dry-run` output — shows exactly which contacts would receive which email today |

### Scope

- **Read + status edits only.** Sending emails stays in the CLI (`python cli.py run`) so non-technical users can't accidentally trigger a live send.
- Reuses [outreach/db.py](outreach/db.py) and [outreach/templates.py](outreach/templates.py) — no duplication of business logic.
- Server-rendered Jinja2 pages with HTMX for interactive bits (status buttons, search). No JavaScript build step.

---

## Scheduling (Optional)

To run automatically every morning at 8am CT, add a cron job:

```bash
# crontab -e
0 8 * * 1-5 cd /path/to/dialtone-outreach && source venv/bin/activate && python cli.py run >> logs/outreach.log 2>&1
```

Or deploy as an AWS Lambda function triggered by EventBridge (same scheduler already in your DialTone stack).

---

## Customising Templates

All email templates are in `outreach/templates.py`. Each template is a Jinja2 string with these tokens:

| Token | Value |
|-------|-------|
| `{{ first_name }}` | Owner first name (falls back to "there") |
| `{{ restaurant_name }}` | Restaurant name |
| `{{ city }}` | City |
| `{{ calendly_url }}` | Your booking link |
| `{{ from_name }}` | Your name |

Edit the template strings directly — no restart needed, changes apply on next run.

---

## Connecting Reply Detection

Currently, marking a contact as `replied` requires a manual status update in Supabase. To automate this:

1. **Gmail/Google Workspace** — use a Google Apps Script that watches your inbox and calls a Supabase edge function when a reply arrives from a known contact email.
2. **AWS SES + SNS** — configure SES notification topics for bounces and complaints, and extend `email_client.py` to handle them.
3. **Webhook** — if you route through a service like Mailgun or SendGrid in the future, reply webhooks are built-in.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | ✓ | — | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✓ | — | Service role key (bypasses RLS) |
| `AWS_ACCESS_KEY_ID` | ✓ | — | AWS IAM key with SES send permissions |
| `AWS_SECRET_ACCESS_KEY` | ✓ | — | AWS IAM secret |
| `AWS_REGION` | — | `us-east-1` | AWS region for SES |
| `FROM_EMAIL` | ✓ | — | Verified SES sender address |
| `FROM_NAME` | — | `Steve Cotton` | Display name for sender |
| `DAILY_SEND_LIMIT` | — | `20` | Max emails per run |
| `CALENDLY_URL` | — | placeholder | Booking link appended to email CTAs |

---

## License

Private — ByteStreams LLC. Not for redistribution.
