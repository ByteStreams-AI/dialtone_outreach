---
title: DialTone Outreach — Project Status
last_updated: 2026-04-30
---

# DialTone Outreach — Project Status

## Overview
Cold email sequencer for restaurant owner outreach. Stack is AWS SES + Supabase + Click/Rich CLI, with a planned local FastAPI + Jinja2 + HTMX UI for non-technical reviewers.
**Current state:** Sequence engine, contact import (Apollo), and CLI dashboard are functional. Repo migrated to `ByteStreams-AI/dialtone_outreach` (private). Milestone 1 (email-generation hardening) merged via PR #7. **First live cohort sent on 2026-04-30** (`batch-1`, 5 contacts, 0 send-time errors). Milestone 2 is now waiting on the 7-day metrics review (bounce / complaint / reply rates against the M2 thresholds). Reviewers still cannot self-serve outcomes — that gap is what motivates the web UI milestone.
**Active scope decisions:**
- Apollo is the only contact source. Outscraper paths and the merge step are out of scope.
- Sending stays in the CLI. The web UI is read + status-edit only.
- Secrets are managed by the user on `ByteStreams-AI` (Cloudflare and others to be added).

## Milestones

Each milestone below has a corresponding GitHub issue on `ByteStreams-AI/dialtone_outreach`. Tick the milestone box when its acceptance criteria are met; tick step boxes as work completes.

---

### Milestone 1 — Email Generation Hardening

- [ ] **Milestone complete**

**Goal:** Templates are bug-free, CAN-SPAM compliant, and personalize against actual Apollo fields. Safe to send live.

**Issue:** [#1](https://github.com/ByteStreams-AI/dialtone_outreach/issues/1)

**Steps:**
- [x] Fix the unsubscribe-link rendering bug — `outreach/templates.py` now resolves the link via `_resolve_unsubscribe_url()` and renders it through the Jinja context, so neither the HTML nor plain-text footer leaks `{{ unsubscribe_url }}`.
- [x] Replace the placeholder footer with a CAN-SPAM-compliant footer (real physical address, working unsubscribe link, sender + legal-entity identity). `render_email()` raises if `BUSINESS_ADDRESS` is unset so we cannot send a non-compliant email by accident.
- [x] Inspect [docs/apollo-contacts-export.csv](apollo-contacts-export.csv) and harden the company-name pipeline. `clean_company_name()` in `outreach/templates.py` strips trailing corporate suffixes (LLC, Inc., Corp., Ltd., Co., PLLC, PC, L.P.), surrounding quotes, and collapses whitespace; `scripts/import_contacts.process_apollo` runs it at import time.
- [x] Add `{{ city }}` to the opener — `EMAIL_1_TEXT` now uses a `{% if city %}` hook so contacts with a city see a localized lede and rows without one fall back cleanly.
- [x] Add fallback handling in `render_email()` for missing/empty `restaurant_name` (`RESTAURANT_FALLBACK = "your restaurant"`) and `first_name` (`FIRST_NAME_FALLBACK = "there"`).
- [ ] Manual review of all 5 rendered templates with the project owner before unfreezing send. Use `python scripts/preview_templates.py` to render against real Apollo rows, then `python cli.py send-test --to verified@inbox.example` to confirm Gmail / Apple Mail rendering.

**Acceptance criteria:**

- `python cli.py run --dry-run` against 5 sample contacts produces clean, personalized output with no template artifacts in any field.
- A test send to a verified inbox renders correctly in Gmail and Apple Mail (HTML + plain text), with a working unsubscribe link.

---

### Milestone 2 — First Live Cohort

- [ ] **Milestone complete**

**Goal:** Send the first batch of real emails, baseline deliverability, and capture initial response data.

**Issue:** [#2](https://github.com/ByteStreams-AI/dialtone_outreach/issues/2)

**Tooling:** Operator runbook lives in [docs/runbook-first-cohort.md](runbook-first-cohort.md). Code-side support: `python cli.py preflight`, `cohort lock|show|unlock`, `run --cohort <name>`, and `metrics --cohort <name> | --since Nd`. Warmup is driven by `WARMUP_START_DATE` + `WARMUP_DAY_LIMITS` env vars; `email_log` carries `bounced_at` / `complained_at` columns (idempotent migration in `schema.sql`).

**Steps:**

- [x] Confirm AWS SES is out of sandbox mode (or accept the 200/day + verified-recipients-only constraint for the pilot batch). Code support: `python cli.py preflight` surfaces sandbox state; AWS console request is operator-only. **Verified 2026-04-30** — production access confirmed via SES Account dashboard: 50,000 emails/24h quota, 14 emails/sec rate, region `us-east-1`, account health `Healthy`.
- [x] Verify SPF, DKIM, and DMARC are configured on the sending domain. Without these, opens drop and replies disappear into spam. Code support: `preflight` uses SES `GetIdentityDkimAttributes` and (optionally) `dnspython` to look up SPF / DMARC TXT records; DNS edits are operator-only. **Verified 2026-04-30** — domain identity `dialtone.menu` shows `Verified` in the Identities pane (DKIM CNAMEs resolve, otherwise SES would not flip the identity to verified). DMARC `_dmarc.dialtone.menu` returns `v=DMARC1; p=quarantine; rua=mailto:hello@dialtone.menu`. SPF on `dialtone.menu` is now a single record — `v=spf1 include:_spf.mx.cloudflare.net include:amazonses.com ~all` — after the duplicate-record fix (RFC 7208 §3.2 requires at most one SPF TXT).
- [x] Set a conservative warmup schedule — start `DAILY_SEND_LIMIT=5` for 3 days, ramp to 10, then 20. Update via `.env`, not code. Code support: set `WARMUP_START_DATE` (and optionally `WARMUP_DAY_LIMITS`) and the runner uses `effective_send_limit()` per-day automatically. **Done 2026-04-30** — `WARMUP_START_DATE=2026-04-30`, `WARMUP_DAY_LIMITS=5,5,5,10,10,10,20` (default). Runner banner now reads `Limit: 5 (warmup)` on day 0.
- [x] Run a dry-run review with reviewers; lock the contact list for batch 1. Code support: `python cli.py cohort lock --name batch-1 --limit 5` snapshots a JSON file under `developer/cohorts/`; `cohort show` renders a review table; `run --dry-run --cohort batch-1` confirms the runner agrees. **Done 2026-04-30** — several lock/unlock cycles on `batch-1` with reviewer-driven SQL cleanup (JuneShine Brands flagged `invalid`, SPB Hospitality / Insomnia Cookies / Firehouse Subs flagged `not_interested`, Green Hills Barber Shop flagged `invalid`). Final approved cohort: Hattie B's Hot Chicken, Stoney River Steakhouse, Bluff City Crab, Party Fowl, Newk's Eatery.
- [x] Execute the first live send. Monitor SES bounce/complaint topics in real time. Code support: `python cli.py run --cohort batch-1` restricts the send to the locked set; the live SES + SNS monitoring itself is operator-only. **Done 2026-04-30 — 5 sent, 0 skipped, 0 errors.** Bounce / complaint monitoring continues passively via SES Console (Reputation tab) for the next 7 days; SNS topic plumbing remains optional and would land with M3.
- [ ] Capture baseline metrics after 7 days: bounce rate, open rate (if tracked), reply count, demo bookings. Code support: `python cli.py metrics --cohort batch-1` and `metrics --since 7d` aggregate sent / opened / replied / bounced / complained against the M2 acceptance thresholds. **Pending until ~2026-05-07.** Until then, `metrics --cohort batch-1` will show `Sent=5` and zeros across the board (no opens / bounces / complaints registered yet).

**Acceptance criteria:**

- Bounce rate < 5%, complaint rate < 0.1% on the first cohort.
- At least one real reply received (positive or negative) so the reply-detection workflow can be validated end-to-end.

---

### Milestone 3 — Reply Detection Automation

- [x] **Milestone complete**

**Goal:** Contacts who reply are automatically marked `replied` so the sequence stops without manual Supabase edits.

**Issue:** [#3](https://github.com/ByteStreams-AI/dialtone_outreach/issues/3)

**Mechanism decision:** IMAP polling via `python cli.py check-replies`. Uses stdlib `imaplib` + `email` (no new deps). Works with any mail provider (Gmail, Cloudflare Email Routing, etc.). Automated scheduling (cron, EventBridge + Lambda, persistent host) is deferred to M6 — during the pilot phase, the operator runs `check-replies` manually before each cohort send.

**Steps:**

- [x] Pick the inbound mechanism. Options documented in [README.md](../README.md#reply-detection-milestone-3): Gmail Apps Script, AWS SES + SNS inbound, or a forwarding service. Decision should weigh setup cost vs reliability. **Decision: IMAP polling** — simplest, no infrastructure changes, stdlib-only, meets 5-minute SLA via cron (scheduling deferred to M6).
- [x] Implement the chosen path:
  - [x] Write the inbound handler — `outreach/reply_checker.py` (IMAP scanner with `check_replies()` entry point).
  - [x] Match incoming sender email to a `contacts.owner_email` row — `db.find_contact_by_owner_email()` (case-insensitive ILIKE lookup).
  - [x] Call `db.mark_contact_replied()` and `db.mark_email_replied()` — `_process_reply()` calls both; marks the most recent `email_log` row for the contact.
- [x] Test with a deliberate reply from a verified test inbox. **Verified 2026-05-01** — inserted a test contact (`cottonbytes@gmail.com`), sent via `send-test`, replied from Gmail, ran `check-replies`: `Scanned: 1, Matched: 1`. Contact status flipped to `replied`, `email_log.replied_at` set. Bug fix during testing: switched IMAP fetch from `RFC822` to `BODY.PEEK[]` so unmatched messages stay UNSEEN.
- [x] Add a small status check that surfaces "replied but still in active status" mismatches — `outreach/audit.py` + `python cli.py check-replies --audit [--fix]`. `db.find_reply_status_mismatches()` catches contacts where `email_log.replied_at` is set but `contacts.status` is not terminal.

**Code support:** `outreach/reply_checker.py`, `outreach/audit.py`, `outreach/config.py` (`REPLY_CHECK_*` env vars), `outreach/db.py` (`find_contact_by_owner_email`, `find_reply_status_mismatches`). CLI: `python cli.py check-replies [--dry-run]`, `python cli.py check-replies --audit [--fix]`.

**Acceptance criteria:**

- A reply from a known contact updates `contacts.status = 'replied'` within 5 minutes of arrival (when run via cron; manual runs are immediate).
- The runner skips that contact on the next `python cli.py run`.

---

### Milestone 4 — Local Web UI v1

- [x] **Milestone complete**

**Goal:** Non-technical reviewers can monitor outreach and update contact statuses in a browser without touching the CLI or Supabase.

**Issue:** [#4](https://github.com/ByteStreams-AI/dialtone_outreach/issues/4)

**Steps:**

- [x] Scaffold a `web/` package: `web/app.py` (FastAPI), `web/templates/` (Jinja2), `web/static/` (CSS). Add `fastapi`, `uvicorn[standard]`, `python-multipart` to `requirements.txt`. Styled with Pico CSS (CDN, classless) + HTMX (CDN). No build step.
- [x] Build the four screens:
  - [x] **Dashboard** — status counts table, conversion funnel (Email → Demo → Pilot → Customer), emails sent today. Reuses `db.get_status_counts()` and `db.get_emails_sent_today()`.
  - [x] **Contacts list** — searchable, filterable by status / lead score / city. HTMX-backed search via `GET /partials/contacts`. New `db.search_contacts()` helper.
  - [x] **Contact detail** — owner info, full email history, status edit buttons (`replied`, `demo_booked`, `pilot`, `customer`, `not_interested`, `invalid`), notes editor with save.
  - [x] **Run preview** — read-only table of contacts due today with seq number, subject, owner email. Reuses `sequence.get_contacts_due()` + `render_email()`.
- [x] Reuse [outreach/db.py](../outreach/db.py) and [outreach/templates.py](../outreach/templates.py) directly — no duplicated business logic.
- [x] Bind to `127.0.0.1` only. No auth (local-only by design); documented in README.
- [x] Start command: `uvicorn web.app:app --reload --host 127.0.0.1 --port 8000`. Documented in README.

**Code support:** `web/app.py` (FastAPI routes), `web/templates/` (6 Jinja2 templates), `web/static/style.css`, `outreach/db.py` (new: `search_contacts()`, `update_contact_notes()`).

**Acceptance criteria:**

- Reviewers can complete a full session — dashboard → drill into a contact → mark `demo_booked` — without needing CLI or Supabase access.
- Sending is not exposed in the UI.

---

### Milestone 5 — Apollo-Only Code Cleanup

- [ ] **Milestone complete**

**Goal:** Remove dead Outscraper and merge code paths so the codebase reflects the actual workflow.

**Issue:** [#5](https://github.com/ByteStreams-AI/dialtone_outreach/issues/5)

**Steps:**

- [ ] Remove `--source` choice from `cli.py import` (default to apollo, drop outscraper option).
- [ ] Delete `cli.py merge` command and `scripts/merge_contacts.py`.
- [ ] Remove Outscraper branches from `scripts/import_contacts.py` (`OUTSCRAPER_MAP`, `process_outscraper`, `KNOWN_CHAINS`, the rating/review filter).
- [ ] Decide what to do with the unused `restaurant_name`, `rating`, `reviews`, `category` columns in `schema.sql` — keep as nullable (cheap), or drop in a migration.
- [ ] Remove any remaining Outscraper references from documentation.

**Acceptance criteria:**

- `grep -i outscraper` returns no hits in code (docs may retain a single historical note).
- `python cli.py --help` shows no `merge` command.

---

### Milestone 6 — Production Operations

- [ ] **Milestone complete**

**Goal:** Daily runs are scheduled and observable. New repo has CI/CD wired up.

**Issue:** [#6](https://github.com/ByteStreams-AI/dialtone_outreach/issues/6)

**Steps:**

- [ ] Add `.github/workflows/` for lint and tests (minimum: `ruff` or `flake8`, plus a smoke test that imports every module).
- [ ] Configure branch protection on `main` — require passing checks before merge.
- [ ] Confirm Cloudflare and any other secrets are populated on `ByteStreams-AI/dialtone_outreach` (owned by the user — only verify workflow files reference the right secret names).
- [ ] Pick a scheduling target — AWS EventBridge → Lambda (consistent with the existing DialTone stack) or cron on a small EC2/host. Document the choice and provision it. **Note:** This also covers scheduling `python cli.py check-replies` (deferred from M3). The reply-checker is a CLI command by design so it can be scheduled alongside the daily `run` command on the same host / Lambda.
- [ ] Capture run logs to a persistent location (CloudWatch Logs, or a logfile in a known path).
- [ ] Add an alert for SES bounce/complaint rate thresholds.

**Acceptance criteria:**

- Daily run executes unattended at the scheduled time and logs are reviewable.
- A failing run page or notification is delivered to the operator.

---

## Working Notes
- Reviewers will primarily review *outcomes*, not templates, so the web UI's value compounds after the first live cohort. Sequencing the work email-first → batch send → UI is intentional.
- The CLI remains the source of truth for the send action. The web UI is a viewer + status editor by design — keeps the live-send blast radius narrow.
- Milestone 1 work lives on `chore/email-gen-hardening`. The remaining gate before merging is the manual template review against verified inboxes; preview tooling (`scripts/preview_templates.py`, `cli.py send-test`) is in place to support it.
