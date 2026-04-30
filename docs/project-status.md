---
title: DialTone Outreach — Project Status
last_updated: 2026-04-29
---

# DialTone Outreach — Project Status

## Overview

Cold email sequencer for restaurant owner outreach. Stack is AWS SES + Supabase + Click/Rich CLI, with a planned local FastAPI + Jinja2 + HTMX UI for non-technical reviewers.

**Current state:** Sequence engine, contact import (Apollo), and CLI dashboard are functional. Repo migrated to `ByteStreams-AI/dialtone_outreach` (private). No live emails sent yet. Reviewers cannot self-serve outcomes — that gap is what motivates the web UI milestone.

**Active scope decisions:**
- Apollo is the only contact source. Outscraper paths and the merge step are out of scope.
- Sending stays in the CLI. The web UI is read + status-edit only.
- Secrets are managed by the user on `ByteStreams-AI` (Cloudflare and others to be added).

## Milestones

Each milestone below has a corresponding GitHub issue on `ByteStreams-AI/dialtone_outreach` (links added after issue creation).

---

### Milestone 1 — Email Generation Hardening

**Goal:** Templates are bug-free, CAN-SPAM compliant, and personalize against actual Apollo fields. Safe to send live.

**Issue:** [#1](https://github.com/ByteStreams-AI/dialtone_outreach/issues/1)

**Steps:**
1. Fix the unsubscribe-link rendering bug in [outreach/templates.py:39](../outreach/templates.py#L39) — `{{{{ unsubscribe_url }}}}` inside the f-string emits literal `{{ unsubscribe_url }}` to recipients. Replace with a real URL or pass the value through the render context.
2. Replace the placeholder footer ("DialTone · dialtone.menu · Nashville, TN") with a CAN-SPAM-compliant footer: real physical address, working unsubscribe link, sender identity.
3. Inspect [docs/apollo-contacts-export.csv](apollo-contacts-export.csv) — confirm what columns Apollo actually populates for the target audience, and whether the `company` field needs cleanup (strip "LLC", "Inc.", trailing punctuation) before being used as `{{ restaurant_name }}`.
4. Add `{{ city }}` to at least the opener subject and body — it is plumbed through [outreach/templates.py:163-168](../outreach/templates.py#L163-L168) but currently unused in any template.
5. Add fallback handling in `render_email()` for missing/empty `restaurant_name` so subjects don't render as `Friday nights at ` (broken).
6. Manual review of all 5 rendered templates with the project owner before unfreezing send.

**Acceptance criteria:**
- `python cli.py run --dry-run` against 5 sample contacts produces clean, personalized output with no template artifacts in any field.
- A test send to a verified inbox renders correctly in Gmail and Apple Mail (HTML + plain text), with a working unsubscribe link.

---

### Milestone 2 — First Live Cohort

**Goal:** Send the first batch of real emails, baseline deliverability, and capture initial response data.

**Issue:** [#2](https://github.com/ByteStreams-AI/dialtone_outreach/issues/2)

**Steps:**
1. Confirm AWS SES is out of sandbox mode (or accept the 200/day + verified-recipients-only constraint for the pilot batch).
2. Verify SPF, DKIM, and DMARC are configured on the sending domain. Without these, opens drop and replies disappear into spam.
3. Set a conservative warmup schedule — start `DAILY_SEND_LIMIT=5` for 3 days, ramp to 10, then 20. Update via `.env`, not code.
4. Run a dry-run review with reviewers; lock the contact list for batch 1.
5. Execute the first live send. Monitor SES bounce/complaint topics in real time.
6. Capture baseline metrics after 7 days: bounce rate, open rate (if tracked), reply count, demo bookings.

**Acceptance criteria:**
- Bounce rate < 5%, complaint rate < 0.1% on the first cohort.
- At least one real reply received (positive or negative) so the reply-detection workflow can be validated end-to-end.

---

### Milestone 3 — Reply Detection Automation

**Goal:** Contacts who reply are automatically marked `replied` so the sequence stops without manual Supabase edits.

**Issue:** [#3](https://github.com/ByteStreams-AI/dialtone_outreach/issues/3)

**Steps:**
1. Pick the inbound mechanism. Options documented in [README.md:255-261](../README.md#L255-L261): Gmail Apps Script, AWS SES + SNS inbound, or a forwarding service. Decision should weigh setup cost vs reliability.
2. Implement the chosen path:
   - Write the inbound handler (Lambda, Apps Script, or webhook endpoint).
   - Match incoming sender email to a `contacts.owner_email` row.
   - Call `db.mark_contact_replied()` and `db.mark_email_replied()`.
3. Test with a deliberate reply from a verified test inbox.
4. Add a small status check that surfaces "replied but still in active status" mismatches, so a missed webhook doesn't silently keep emailing a replier.

**Acceptance criteria:**
- A reply from a known contact updates `contacts.status = 'replied'` within 5 minutes of arrival.
- The runner skips that contact on the next `python cli.py run`.

---

### Milestone 4 — Local Web UI v1

**Goal:** Non-technical reviewers can monitor outreach and update contact statuses in a browser without touching the CLI or Supabase.

**Issue:** [#4](https://github.com/ByteStreams-AI/dialtone_outreach/issues/4)

**Steps:**
1. Scaffold a `web/` package: `web/app.py` (FastAPI), `web/templates/` (Jinja2), `web/static/` (CSS). Add `fastapi`, `uvicorn`, `python-multipart` to `requirements.txt`.
2. Build the four screens:
   - **Dashboard** — status counts, conversion funnel, emails-sent-today (reuse logic from [outreach/runner.py:137-186](../outreach/runner.py#L137-L186)).
   - **Contacts list** — searchable, filterable by status / lead score / city. HTMX-backed search input.
   - **Contact detail** — owner info, full email history, status edit buttons (`replied`, `demo_booked`, `pilot`, `customer`, `not_interested`, `invalid`), notes editor.
   - **Run preview** — read-only HTML rendering of `cli.py run --dry-run` output.
3. Reuse [outreach/db.py](../outreach/db.py) and [outreach/templates.py](../outreach/templates.py) directly — no duplicated business logic.
4. Bind to `127.0.0.1` only. No auth (local-only by design); document this constraint clearly in the README section.
5. Add a `make web` (or equivalent) command and document the run instructions.

**Acceptance criteria:**
- Reviewers can complete a full session — dashboard → drill into a contact → mark `demo_booked` — without needing CLI or Supabase access.
- Sending is not exposed in the UI.

---

### Milestone 5 — Apollo-Only Code Cleanup

**Goal:** Remove dead Outscraper and merge code paths so the codebase reflects the actual workflow.

**Issue:** [#5](https://github.com/ByteStreams-AI/dialtone_outreach/issues/5)

**Steps:**
1. Remove `--source` choice from `cli.py import` (default to apollo, drop outscraper option).
2. Delete `cli.py merge` command and `scripts/merge_contacts.py`.
3. Remove Outscraper branches from `scripts/import_contacts.py` (`OUTSCRAPER_MAP`, `process_outscraper`, `KNOWN_CHAINS`, the rating/review filter).
4. Decide what to do with the unused `restaurant_name`, `rating`, `reviews`, `category` columns in `schema.sql` — keep as nullable (cheap), or drop in a migration.
5. Remove any remaining Outscraper references from documentation.

**Acceptance criteria:**
- `grep -i outscraper` returns no hits in code (docs may retain a single historical note).
- `python cli.py --help` shows no `merge` command.

---

### Milestone 6 — Production Operations

**Goal:** Daily runs are scheduled and observable. New repo has CI/CD wired up.

**Issue:** [#6](https://github.com/ByteStreams-AI/dialtone_outreach/issues/6)

**Steps:**
1. Add `.github/workflows/` for lint and tests (minimum: `ruff` or `flake8`, plus a smoke test that imports every module).
2. Configure branch protection on `main` — require passing checks before merge.
3. Confirm Cloudflare and any other secrets are populated on `ByteStreams-AI/dialtone_outreach` (owned by the user — only verify workflow files reference the right secret names).
4. Pick a scheduling target — AWS EventBridge → Lambda (consistent with the existing DialTone stack) or cron on a small EC2/host. Document the choice and provision it.
5. Capture run logs to a persistent location (CloudWatch Logs, or a logfile in a known path).
6. Add an alert for SES bounce/complaint rate thresholds.

**Acceptance criteria:**
- Daily run executes unattended at the scheduled time and logs are reviewable.
- A failing run page or notification is delivered to the operator.

---

## Working Notes

- Reviewers will primarily review *outcomes*, not templates, so the web UI's value compounds after the first live cohort. Sequencing the work email-first → batch send → UI is intentional.
- The CLI remains the source of truth for the send action. The web UI is a viewer + status editor by design — keeps the live-send blast radius narrow.
