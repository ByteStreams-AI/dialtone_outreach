---
title: First Live Cohort — Operator Runbook (Milestone 2)
last_updated: 2026-04-30
---

# First Live Cohort — Operator Runbook

This runbook walks through the human-only steps for Milestone 2 in
[project-status.md](project-status.md). The repo provides the tooling
(`preflight`, `cohort`, `metrics`, warmup-aware `run`); this document
captures the order in which to use them and the AWS / DNS work that
sits outside the codebase.

## 0. Prerequisites

- M1 templates have shipped on `main` and the verified-inbox test send
  has been visually approved in Gmail and Apple Mail.
- Production `.env` is populated. `BUSINESS_ADDRESS` is the real
  ByteStreams mailing address (not the historical placeholder).
- Apollo CSV has been imported and `python cli.py status` shows the
  expected number of `new` contacts.

## 1. Confirm AWS SES posture

This step is operator-only — AWS doesn't expose the production-access
flow via boto3.

1. Open the [SES Account dashboard](https://console.aws.amazon.com/ses/home#/account)
   in the same region used for `AWS_REGION`.
2. If "Sending account is in the sandbox" still appears, request
   production access. Approval typically takes <24h.
3. While the request is pending you can still run the cohort against
   verified test recipients only — `python cli.py preflight` will warn
   when sandbox is active.

## 2. Verify SPF, DKIM, DMARC for the sender domain

The repo can confirm DKIM via SES (`get_identity_dkim_attributes`) and,
when `dnspython` is installed, SPF / DMARC TXT records too. Install the
optional dep with [uv](https://docs.astral.sh/uv/) — the project's
preferred package manager:

```bash
uv add dnspython          # updates pyproject.toml + uv.lock
# or, ad-hoc into the active venv without touching the lockfile:
uv pip install dnspython
```

If you used `uv add`, regenerate the lock and sync the venv:

```bash
uv lock
uv sync
```

Do not fall back to bare `pip install` — it bypasses `uv.lock` and will
drift the environment from what `uv sync` produces on other machines.

Then:

```bash
python cli.py preflight
```

Expected outcome:

- `ses: dkim` row reads `pass` for the sender domain.
- `dns: spf` row contains a `v=spf1` record that includes
  `include:amazonses.com`.
- `dns: dmarc` row contains a `v=DMARC1; p=...` policy.

Add or correct DNS records in your registrar / Cloudflare panel until
all three are green. Re-run `preflight` until the only remaining
warning is sandbox (if applicable) or an unset recommended env var.

## 3. Set the warmup ramp

Edit `.env`:

```env
WARMUP_START_DATE=YYYY-MM-DD     # day 1 of the live cohort
WARMUP_DAY_LIMITS=5,5,5,10,10,10,20
```

`WARMUP_DAY_LIMITS` is the project-status.md cautious ramp:

| Day | Cap |
|-----|-----|
| 1–3 | 5   |
| 4–6 | 10  |
| 7+  | 20  |

After day 7 the runner falls back to `DAILY_SEND_LIMIT`. Edit `.env`,
not code, so the schedule is reproducible.

## 4. Lock the contact list with reviewers

Snapshot the next batch and send the preview to reviewers:

```bash
python cli.py cohort lock --name batch-1 --limit 5
python cli.py cohort show  --name batch-1
```

`cohort lock` writes `developer/cohorts/batch-1.json` (gitignored —
contains owner emails). The preview table shows restaurant name, city,
owner email, lead score, sequence number, and the rendered subject for
each contact. Walk reviewers through that table; if they want changes,
unlock and re-lock:

```bash
python cli.py cohort unlock --name batch-1
# adjust contacts in Supabase if needed (mark someone invalid /
# not_interested / lower lead_score), then:
python cli.py cohort lock --name batch-1 --limit 5
```

## 5. Dry-run review

Confirm the runner agrees with the cohort before going live:

```bash
python cli.py run --dry-run --cohort batch-1
```

The banner should show:

- `Limit: 5 (warmup)` (or whatever the day yields).
- `Cohort: batch-1`.
- 5 `→` lines, each rendering the right subject for the right
  recipient.

If anything looks wrong, unlock and rebuild the cohort.

## 6. Execute the live send

Only after reviewer approval:

```bash
python cli.py run --cohort batch-1
```

Monitor SES bounce / complaint topics in real time (CloudWatch metrics
or SNS subscriptions). The runner logs each send to `email_log` with
the SES `MessageId`, which is what the M3 reply-detection work will key
off.

## 7. Capture baseline metrics after 7 days

```bash
python cli.py metrics --cohort batch-1     # cohort-scoped numbers
python cli.py metrics --since 7d           # rolling time-window
```

Expected outcome to satisfy M2 acceptance:

- Bounce rate < 5%.
- Complaint rate < 0.1%.
- At least one real reply (positive or negative) so the M3 reply-
  detection workflow can be validated end-to-end.

If bounces / complaints exceed the thresholds, pause the next ramp day
(`unset WARMUP_START_DATE` or set `DAILY_SEND_LIMIT=0` in `.env`),
investigate, and clean up the contact list before resuming.

## 8. Tick the milestone

When acceptance criteria are met, update
[docs/project-status.md](project-status.md) — tick the per-step
checkboxes you completed, then the **Milestone complete** box for
Milestone 2. Add a journal entry to
[developer/developer-journal.md](../developer/developer-journal.md)
summarising the cohort: contacts targeted, sent / bounced / complained
counts, replies, and any deliverability lessons learned.
