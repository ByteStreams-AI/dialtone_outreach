# DialTone Outreach — Web UI Guide

## What is this?

DialTone Outreach is a cold-email sequencer for restaurant owners. It sends a 5-email sequence to restaurant owners, pausing the moment anyone replies or is marked with a terminal status.

This web UI is a **local viewer and status editor**. It lets you monitor outreach progress and update contact statuses without touching the command line or the database directly.

**What you can do here:**
- See how many contacts are in each stage of outreach
- Search and filter the contact list
- View a contact's full email history
- Update a contact's status (e.g. mark as "demo booked" or "not interested")
- Add notes to contacts
- Preview which contacts would receive an email today

**What you cannot do here:**
- Send emails — that only happens via the CLI (`python cli.py run`)
- Import contacts — that's also CLI-only (`python cli.py import`)

This is intentional. Keeping the send action in the CLI means you can't accidentally trigger a live send from the browser.

---

## Starting the UI

```bash
source .venv/bin/activate
uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
```

Then open **http://localhost:8000** in your browser.

The UI runs locally only (127.0.0.1) — it's not accessible from other machines. There's no login because it's designed for local use only.

---

## Screens

### Dashboard (/)

The landing page. Shows three things at a glance:

- **Emails Sent Today** — how many emails went out in today's run
- **Total Contacts** — everyone in the system
- **Emails Sent (all time)** — total emails across all sequences

Below that:

- **Status Breakdown** — how many contacts are in each status, with percentages
- **Conversion Funnel** — the rates that matter:
  - Email → Demo (target: 3–6%)
  - Demo → Pilot (target: 30–50%)
  - Pilot → Customer (target: 50–80%)

### Contacts (/contacts)

A searchable, filterable list of all contacts.

**Filters:**
- **Search** — type to search by restaurant name, owner email, or domain. Results update as you type (300ms delay).
- **Status dropdown** — filter to a single status (e.g. show only "emailed_1" contacts)
- **Score dropdown** — filter by lead score (1–5)
- **City** — type a city name to filter by location
- **Reset** — clears all filters

Click any restaurant name to open its detail page.

### Contact Detail (/contacts/{id})

Everything about a single contact:

- **Owner info** — name, email, phone, location, lead score
- **Current status** — shown as a colored badge
- **Update Status** — buttons to change the contact's status. Only terminal/outcome statuses are available (see Status Reference below). The current status button is disabled.
- **Email History** — every email sent to this contact: sequence number, subject, send date, and whether it was opened, replied to, or bounced
- **Notes** — free-text field. Click "Save Notes" to persist. Use this for context like "Spoke on phone 5/1, interested in pilot" or "Left voicemail, will follow up."

### Run Preview (/run-preview)

A read-only view of what `python cli.py run` would do right now. Shows which contacts are due for an email today, what sequence number they're on, and what the subject line would be.

Use this to review before triggering a live send from the CLI.

---

## Status Reference

Every contact has a status that controls whether they receive further emails.

### Active statuses (sequence continues)

| Status | Meaning |
|--------|---------|
| `new` | Imported, not yet emailed |
| `emailed_1` | Email #1 sent |
| `emailed_2` | Email #2 sent |
| `emailed_3` | Email #3 sent |
| `breakup_sent` | Breakup email (email #4) sent |
| `re_engage` | Re-engage email (email #5) sent |

These are set automatically by the system when emails are sent. You don't need to set these manually.

### Terminal statuses (sequence stops)

| Status | Meaning | When to use |
|--------|---------|-------------|
| `replied` | Responded to any email | Set automatically by reply detection, or manually if you notice a reply |
| `demo_booked` | Demo/meeting scheduled | After a contact agrees to a call or demo |
| `pilot` | In pilot program | After a demo converts to a trial |
| `customer` | Paying customer | After a pilot converts to a paying relationship |
| `not_interested` | Explicitly opted out | When a contact says no, or sends an unsubscribe request |
| `invalid` | Bad email or not a real contact | Bad bounce, wrong person, not a restaurant, etc. |

Once a contact reaches a terminal status, they **never receive another email**. This is enforced by the sequence engine — there's no override in the UI.

**Status buttons in the UI only show terminal statuses.** You cannot manually set a contact back to `emailed_1` or another active status from the web UI. If you need to do that, use the Supabase dashboard directly.

---

## Typical Reviewer Workflow

1. **Open the Dashboard** — check today's send count and the conversion funnel
2. **Go to Contacts** — filter by `emailed_1` or `emailed_2` to see who's in the active sequence
3. **Check for replies** — filter by `replied` to see who's responded. Click into a contact to read their email history and add notes.
4. **Update statuses** — when a contact books a demo, click into their detail page and hit `demo_booked`. Add a note with the date and context.
5. **Preview the next run** — go to Run Preview to see who would get emailed tomorrow. Flag any contacts that should be marked `not_interested` or `invalid` before the next send.

---

## Lead Scores

Contacts are scored 1–5 to control outreach priority. Higher-scored contacts always send first when the daily limit is reached.

| Score | Meaning |
|-------|---------|
| 5 | Hot — demo booked or very engaged |
| 4 | Warm — replied, interested |
| 3 | Good fit, not yet contacted |
| 2 | Has contact info, lower fit |
| 1 | Minimal info, low priority |

---

## Email Sequence

The system sends a 5-email sequence with automatic timing:

| # | Timing | Subject | Purpose |
|---|--------|---------|---------|
| 1 | Day 0 | Friday nights at [Restaurant] | The opener — short, one question |
| 2 | Day 3 | The math on missed calls | Value add — the $87,500 stat |
| 3 | Day 7 | What other owners are saying | Social proof |
| 4 | Day 14 | Closing the loop | Breakup email — low pressure |
| 5 | Day 60 | Checking back in | Re-engage (only if email #4 was opened) |

The sequence stops immediately if a contact's status changes to any terminal value.
