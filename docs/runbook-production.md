---
title: DialTone Outreach — Production Operations Runbook
last_updated: 2026-05-07
---

# DialTone Outreach — Production Operations Runbook

Steady-state operator reference. Covers the daily checklist, every CLI
command an operator runs by hand, the production Lambda runtime, and
how to respond when an alarm fires. For the one-time first-cohort
ramp-up, see [runbook-first-cohort.md](runbook-first-cohort.md). For
reviewer-facing web-UI usage, see [web-ui-guide.md](web-ui-guide.md).

## At a glance

```
                          ┌─ EventBridge schedules ──────────┐
                          │  daily-run     (cron weekdays)   │
                          │  reply-check   (rate 30 min)     │
                          └──────────────────────────────────┘
                                            │ {"task":"run"|"check-replies"}
                                            ▼
                                ┌──────────────────────┐
                                │  Lambda container    │
                                │  /aws/lambda/        │
                                │   dialtone-outreach  │
                                └──────────────────────┘
                                            │ stdout / stderr
                                            ▼
                                ┌──────────────────────┐
                                │  CloudWatch Logs     │
                                └──────────────────────┘

   Operator workstation                      AWS                       Reviewers
   ────────────────────                      ───                       ─────────
   python cli.py run         ─→ SES         (also from Lambda)    ─→   inboxes
   python cli.py check-…     ─→ IMAP        (also from Lambda)
   python cli.py status      ─→ Supabase    (also from Lambda)         localhost:8000
   uvicorn web.app:app       ─→ Supabase ◀──────────────────────────── (read-only viewer)

   SES Reputation.BounceRate ─→ CloudWatch ─→ SNS ─→ ALERT_EMAIL
   SES Reputation.ComplaintRate ─→ ……
   Lambda Errors             ─→ ……
```

The CLI on the operator's workstation and the production Lambda share
the same `outreach/` and `scripts/` packages — the Lambda image is the
same code that the operator runs interactively. The only thing the
Lambda doesn't do is import contacts (CLI-only) and serve the web UI
(operator-local).

## Daily routine

A 5-minute scan, ideally in the morning before the daily run fires
(09:00 Central / 14:00 UTC by default).

1. **Check the alarm inbox.** No new SES / Lambda alarm emails since
   yesterday → green. Any alarm → jump to the matching response section
   below.
2. **Run the dashboard:**

   ```bash
   python cli.py status
   python cli.py stats
   ```

   `status` shows the per-status breakdown (`new`, `emailed_1`, …,
   `demo_booked`). `stats` shows the conversion funnel.
3. **Skim yesterday's metrics:**

   ```bash
   python cli.py metrics --since 24h
   ```

   Spot-check bounce rate (target < 2%), complaint rate (target < 0.05%),
   reply rate (sequence-1 reply rate is the early signal that copy is
   landing).
4. **Glance at CloudWatch.** Open the log group, pick the most recent
   `daily-run` invocation, scan for `ERROR` lines:

   ```bash
   aws logs tail /aws/lambda/dialtone-outreach --since 24h \
     --filter-pattern '"ERROR"' --region us-east-1
   ```

   Empty output is the happy path.

If everything above is clean, you're done. If anything looks off, the
sections below cover the response.

## CLI operations

Run all commands from the repo root with the project venv active.

### Send a one-off cohort

Used when you want to send to a specific batch of contacts outside the
scheduled cadence (e.g. a manual A/B test, or a re-warm after a pause).

```bash
python cli.py preflight                                 # gate: must exit 0
python cli.py cohort lock --name batch-N --limit 25
python cli.py cohort show  --name batch-N               # inspect before sending
python cli.py run --cohort batch-N --dry-run            # final preview
python cli.py run --cohort batch-N                      # live send
python cli.py cohort unlock --name batch-N              # tidy up
python cli.py metrics --cohort batch-N                  # 24-72h after send
```

Cohort files live under `developer/cohorts/` and are gitignored — they
contain recipient PII. The `--dry-run` step renders every email through
the real template + SES path *without* sending; an operator should
visually skim 1-2 of the rendered subjects before going live.

### Mark a contact (demo / pilot / customer / not_interested)

The web UI is the easier path here ([web-ui-guide.md](web-ui-guide.md)),
but the CLI works for bulk or scripted updates. Direct status edits:

```bash
python cli.py contact --email owner@restaurant.com      # find the contact
# … then edit in Supabase Studio, or use the web UI's status dropdown
```

For the unsubscribe path specifically, use the dedicated CLI to keep
the audit trail right:

```bash
python cli.py unsubscribe --email owner@restaurant.com
python cli.py unsubscribe --email owner@restaurant.com --note "mailto reply 2026-05-07"
```

This flips the contact to `not_interested`, appends an audit line to
`notes`, and confirms before writing — the action is effectively
irreversible without a manual Supabase edit, so the prompt is there
on purpose. Use `--yes` to skip when scripting.

### Manual reply sweep

Lambda runs `check-replies` every 30 minutes by default, so manual
runs are mostly diagnostic. If you suspect the IMAP poll is stuck or
want to confirm a specific reply landed:

```bash
python cli.py check-replies --dry-run                   # preview matches
python cli.py check-replies                             # write back to Supabase
python cli.py check-replies --audit                     # find log/status mismatches
python cli.py check-replies --audit --fix               # auto-correct mismatches
```

`--audit` is the safety net for partial-failure scenarios — if a reply
got logged but the contact's `status` never flipped, this catches it
and (with `--fix`) repairs it.

### Send a verified test email

Used after a template change to confirm Gmail and Apple Mail render
correctly before the change touches a real recipient.

```bash
python cli.py send-test --to verified@inbox.example --seq 1
```

`--seq` selects which of the 5 templates to render (1-5). The render
goes through the real `render_email` + SES path, so what lands in the
verified inbox is byte-for-byte what production sends.

### Inspect the locked-cohort backlog

```bash
python cli.py cohort show                               # list every locked cohort
python cli.py cohort show --name batch-N                # one cohort's preview rows
```

## Web UI for reviewers

The web UI is read-only-ish — reviewers can update statuses and add
notes but cannot send email or import contacts. Start it locally:

```bash
source .venv/bin/activate
uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000
```

Full reviewer documentation, including screenshots of the status flow,
is in [web-ui-guide.md](web-ui-guide.md). Note that the UI talks to
the *production* Supabase — every status edit is live. There is no
staging environment.

## Production Lambda

### Schedules

| Rule | Cron / rate | Payload | Purpose |
|---|---|---|---|
| `dialtone-outreach-daily-run` | weekdays 14:00 UTC | `{"task":"run"}` | Today's outreach send |
| `dialtone-outreach-reply-check` | every 30 min | `{"task":"check-replies"}` | IMAP reply sweep |

Schedule expressions live in `deploy/config.env` and are applied by
`deploy/setup_schedule.sh`. To change the cadence: edit `config.env`,
re-run the script.

### Manual Lambda invocations

Smoke-test that the function is healthy without waiting for the cron:

```bash
# Read-only sanity check — env, Supabase, SES quota, DNS
aws lambda invoke --function-name dialtone-outreach \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"preflight"}' \
  --region us-east-1 /tmp/lambda-out.json && cat /tmp/lambda-out.json

# Dry-run a real day's pipeline (no email sent, no DB writes)
aws lambda invoke --function-name dialtone-outreach \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"run","dry_run":true}' \
  --region us-east-1 /tmp/lambda-out.json

# Force an off-cadence reply sweep
aws lambda invoke --function-name dialtone-outreach \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"check-replies"}' \
  --region us-east-1 /tmp/lambda-out.json
```

Empty `{}` payloads error by design — the handler refuses to default
to `run`, so an accidental click in the AWS console can't kick off a
real send.

### CloudWatch logs

Log group: `/aws/lambda/dialtone-outreach`. Each invocation emits a
structured `start task=… request_id=…` line and a matching `done` line
— grep on `request_id` to follow one invocation end-to-end.

```bash
aws logs tail /aws/lambda/dialtone-outreach --since 1h --region us-east-1
aws logs tail /aws/lambda/dialtone-outreach --follow --region us-east-1
aws logs tail /aws/lambda/dialtone-outreach --since 24h \
  --filter-pattern '"ERROR"' --region us-east-1
```

## Alarm response

All three alarms fan out through the SNS topic `dialtone-outreach-ses-alerts`
to whatever address is set in `deploy/config.env::ALERT_EMAIL`.

### SES bounce rate alarm — `dialtone-outreach-ses-bounce-rate`

**Threshold:** bounce rate > 5% over 5 minutes (AWS suspends sending at
10%, so this is a wide buffer).

**Response:**

1. **Stop the daily run** to prevent the rate climbing further:

   ```bash
   aws events disable-rule --name dialtone-outreach-daily-run --region us-east-1
   ```

2. Identify which contacts bounced — Supabase `email_log` table,
   filter by `bounced_at` IS NOT NULL within the alarm window.
3. Mark each bounced contact's status as `invalid` (the runner
   already excludes terminal statuses, so future runs skip them).
4. Look at the *source* of the bounces. Single common pattern (one
   bad import batch) → fix the import filter. Distributed across
   many sources → investigate sender reputation (DKIM/SPF/DMARC,
   recent template changes, list hygiene).
5. Once the bounce rate is back under 1% for an hour:

   ```bash
   aws events enable-rule --name dialtone-outreach-daily-run --region us-east-1
   ```

### SES complaint rate alarm — `dialtone-outreach-ses-complaint-rate`

**Threshold:** complaint rate > 0.1% over 5 minutes (AWS suspends at
0.5% — much narrower margin than bounces).

Complaints are recipients hitting "report spam." This is more
serious than bounces.

**Response:**

1. **Stop the daily run immediately** (same `disable-rule` command above).
2. Identify the complaining recipients in `email_log` (filter by
   `complained_at`).
3. Mark each as `not_interested` *and* `unsubscribed_at`. Use
   `python cli.py unsubscribe --email …` so the audit log captures
   the complaint as the reason.
4. Stronger remediation than bounces — review the most recent
   sequence template that went out. Spam complaints usually come
   from copy that reads as too pushy or from an import source the
   recipients didn't expect to be in.
5. Before re-enabling the run, consider tightening the ramp via
   `WARMUP_DAY_LIMITS` for a few days to rebuild reputation.

### Lambda errors alarm — `dialtone-outreach-lambda-errors`

**Threshold:** ≥ 1 unhandled error in the function over 5 minutes.

This means the daily run or the reply sweep raised an exception that
escaped the handler. The schedule will retry on the next tick, so
there's no immediate damage — but a recurring failure means today's
sends are skipped.

**Response:**

1. Pull the failing invocation's logs:

   ```bash
   aws logs tail /aws/lambda/dialtone-outreach --since 1h \
     --filter-pattern '"ERROR"' --region us-east-1
   ```

2. The traceback indicates the failure mode. Common patterns and
   fixes are in the troubleshooting table below.
3. Fix forward — patch the code, rebuild and redeploy:

   ```bash
   bash deploy/build_and_push.sh
   bash deploy/create_lambda.sh
   ```

4. Verify with a manual `preflight` invocation before waiting for the
   next cron tick.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Lambda exit_code 1 with `InvalidClientTokenId` on SES calls | Stale image (built before the boto3-default-chain fix) | `bash deploy/build_and_push.sh && bash deploy/create_lambda.sh` |
| Lambda exit_code 1 with `BUSINESS_ADDRESS not configured` | `.env` not forwarded, or value was empty | `bash deploy/create_lambda.sh` to refresh env vars |
| `aws lambda invoke … exit_code 1` with SES `MessageRejected` | Domain not yet out of SES sandbox, or sender identity not verified | `python cli.py preflight` locally; fix DKIM / verification in SES console |
| `check-replies` finds 0 matches but you know there's a reply | IMAP password rotated, or `+` aliasing disabled | Refresh `REPLY_CHECK_PASSWORD` in `.env`, redeploy with `bash deploy/create_lambda.sh` |
| All recent runs send 0 emails | Warmup ramp gating on a past day, or no `new`/`emailed_*` contacts due | `python cli.py preflight` then `python cli.py status` to see breakdown |
| CI failing on push but tests pass locally | New module added without registering in `tests/test_smoke.py::MODULES` | Add the import to the parametrize list |

## Pause everything (emergency)

Quickest way to halt all production sending without deleting anything:

```bash
aws events disable-rule --name dialtone-outreach-daily-run    --region us-east-1
aws events disable-rule --name dialtone-outreach-reply-check  --region us-east-1
```

Both schedules become inert. Re-enable with `enable-rule`. The Lambda
function and its image are untouched, so a manual `aws lambda invoke`
still works for diagnostics while the schedules are off.

For SES-side emergencies (e.g. AWS auto-paused sending due to a
reputation event), the AWS Console SES Account dashboard is the
source of truth — boto3 doesn't expose the un-pause flow. Treat it as
manual / one-time.

## Cross-references

- [deploy/README.md](../deploy/README.md) — initial AWS deploy + branch protection
- [docs/runbook-first-cohort.md](runbook-first-cohort.md) — the M2 first-cohort ramp-up
- [docs/web-ui-guide.md](web-ui-guide.md) — reviewer-facing UI guide
- [AGENTS.md](../AGENTS.md) — codebase orientation for engineers
- [README.md](../README.md) — initial setup and CLI cheatsheet
