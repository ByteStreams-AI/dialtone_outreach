---
title: DialTone Outreach — Production Process Flow
last_updated: 2026-05-07
---

# DialTone Outreach — Production Process Flow

Visual reference for how the production system actually runs.
Complements the prose in [runbook-production.md](runbook-production.md);
the runbook tells you *what to do*, this doc shows *what's happening*.

Every diagram below is a Mermaid block, which GitHub renders inline.
If you're reading raw markdown, the source is still legible.

## 1. Daily automated cycle

What happens each weekday morning when EventBridge fires the daily-run
schedule. Same path runs unattended; no operator interaction in the
happy case.

```mermaid
flowchart TD
    Cron["EventBridge<br/>cron(0 14 ? * MON-FRI *)"] -->|"{&quot;task&quot;:&quot;run&quot;}"| Handler["lambda_handler.handler"]
    Handler --> Dispatch{"task<br/>field"}
    Dispatch -->|"run"| Runner["outreach.runner.run()"]
    Runner --> ReadDue["Supabase: read due contacts<br/>(status, sequence, last sent_at)"]
    ReadDue --> Render["Render templates<br/>(Jinja2 + CAN-SPAM helpers)"]
    Render --> SendLoop{"per contact<br/>(rate-limited<br/>by DAILY_SEND_LIMIT)"}
    SendLoop -->|"send"| SES["SES SendEmail"]
    SES --> WriteLog["Supabase: insert email_log row<br/>+ bump contact.status"]
    WriteLog --> SendLoop
    SendLoop -->|"done"| Summary["Summary:<br/>sent / skipped / errors"]
    Summary --> Stdout["stdout/stderr → CloudWatch Logs<br/>/aws/lambda/dialtone-outreach"]

    SES -.->|"async bounce/complaint events"| Reputation["AWS/SES::Reputation.*"]
    Reputation -.->|"if &gt; threshold"| Alarm["CloudWatch alarm"]
    Alarm -.->|"breach"| SNS["SNS topic"]
    SNS -.-> EmailOps["ALERT_EMAIL"]
```

The dotted edges run *out of band* on AWS's side — bounces and
complaints don't block the Lambda invocation; they show up in
SES's reputation metrics minutes-to-hours later and trigger their
own alarm path.

## 2. Reply detection cycle

Independent schedule, every 30 minutes by default. Pulls unread
mail from the configured IMAP mailbox and marks any matching
contacts as `replied` so the daily-run loop stops emailing them.

```mermaid
flowchart TD
    Cron2["EventBridge<br/>rate(30 minutes)"] -->|"{&quot;task&quot;:&quot;check-replies&quot;}"| Handler2["lambda_handler.handler"]
    Handler2 --> Checker["outreach.reply_checker.check_replies()"]
    Checker --> IMAP["IMAP login<br/>(REPLY_CHECK_* env vars)"]
    IMAP --> Search["SEARCH UNSEEN"]
    Search --> Loop{"per message"}
    Loop --> Match{"sender matches<br/>known contact?"}
    Match -->|"no"| Skip["skip + leave UNSEEN"]
    Match -->|"yes"| Update["Supabase:<br/>contact.status = replied<br/>email_log.replied_at = now()"]
    Update --> MarkRead["IMAP: mark SEEN"]
    MarkRead --> Loop
    Skip --> Loop
    Loop -->|"done"| Result["{scanned, matched,<br/>skipped, errors}"]
    Result --> Stdout2["CloudWatch Logs"]
```

The audit-mode CLI (`check-replies --audit [--fix]`) runs against the
same Supabase state without touching IMAP — used to repair drift if
a partial failure leaves `email_log.replied_at` set but `contact.status`
unchanged.

## 3. Manual cohort send (operator-driven)

Off-cadence sends — a custom batch, an A/B test, a re-warm after
a pause. The operator runs every step from the workstation; the
cohort file at `developer/cohorts/<name>.json` is the snapshot
boundary.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant CLI as cli.py
    participant FS as developer/cohorts/
    participant DB as Supabase
    participant SES as AWS SES

    Op->>CLI: preflight
    CLI->>DB: read connectivity
    CLI->>SES: read send quota / identity / DKIM
    CLI-->>Op: pass / fail (gate)

    Op->>CLI: cohort show
    CLI->>FS: list *.json
    CLI-->>Op: existing cohort names

    Op->>CLI: cohort lock --name X --limit 25
    CLI->>DB: read next-due contacts
    CLI->>FS: write X.json (frozen)
    CLI-->>Op: locked count + preview

    Op->>CLI: cohort show --name X
    CLI->>FS: read X.json
    CLI-->>Op: per-contact preview rows

    Op->>CLI: run --cohort X --dry-run
    CLI->>FS: read X.json
    CLI->>DB: re-fetch contact rows
    CLI->>CLI: render templates (no send)
    CLI-->>Op: previews + would-send count

    Op->>CLI: run --cohort X
    CLI->>FS: read X.json
    CLI->>DB: re-fetch contact rows
    loop per contact (rate-limited)
        CLI->>SES: SendEmail
        SES-->>CLI: message_id
        CLI->>DB: insert email_log + bump status
    end
    CLI-->>Op: summary

    Op->>CLI: cohort unlock --name X
    CLI->>FS: delete X.json
    CLI-->>Op: ok

    Note over Op,SES: 24-72h later

    Op->>CLI: metrics --cohort X
    CLI->>DB: aggregate email_log + contacts<br/>scoped to cohort ids
    CLI-->>Op: bounce / complaint / reply / demo rates
```

Lock is the snapshot boundary — once `X.json` is written, the contact
list is frozen even if Supabase changes underneath. `metrics --cohort X`
works *after* `unlock` because it scopes by contact-id list, not by
the file.

## 4. Alarm response decision tree

When an SNS-fanout email lands in `ALERT_EMAIL`, the response path
depends on which alarm fired. The first move in every case is to
stop the bleed (disable the schedule), then diagnose. Re-enable only
once the root cause is fixed *and* the metric is back inside its band.

```mermaid
flowchart TD
    Email["Alarm email arrives in ALERT_EMAIL"] --> Which{"Which alarm?"}

    Which -->|"ses-bounce-rate<br/>(&gt; 5%)"| BounceStop["Disable daily-run rule:<br/>aws events disable-rule<br/>--name dialtone-outreach-daily-run"]
    BounceStop --> BounceDiag["Identify bounced contacts<br/>email_log.bounced_at within<br/>alarm window"]
    BounceDiag --> BounceMark["Mark each as<br/>contact.status = invalid"]
    BounceMark --> BounceRoot["Single import batch?<br/>→ tighten import filter<br/>Distributed?<br/>→ check sender reputation"]
    BounceRoot --> Wait["Wait until rate &lt; 1%<br/>for 1 hour"]
    Wait --> Reenable["enable-rule"]

    Which -->|"ses-complaint-rate<br/>(&gt; 0.1%)"| ComplaintStop["Disable daily-run rule<br/>(same command)"]
    ComplaintStop --> ComplaintDiag["Identify complainers<br/>email_log.complained_at"]
    ComplaintDiag --> ComplaintMark["unsubscribe_contact<br/>(audit log captures<br/>complaint as reason)"]
    ComplaintMark --> ComplaintCopy["Review most recent<br/>sequence template +<br/>most recent import source"]
    ComplaintCopy --> ComplaintWarm["Consider tightening<br/>WARMUP_DAY_LIMITS<br/>before re-enabling"]
    ComplaintWarm --> Reenable

    Which -->|"lambda-errors<br/>(≥ 1 error)"| LambdaLogs["aws logs tail … <br/>--filter-pattern '&quot;ERROR&quot;'"]
    LambdaLogs --> LambdaTrace["Read traceback from CloudWatch"]
    LambdaTrace --> LambdaFix["Fix forward:<br/>build_and_push.sh +<br/>create_lambda.sh"]
    LambdaFix --> LambdaVerify["aws lambda invoke<br/>--payload<br/>'{&quot;task&quot;:&quot;preflight&quot;}'"]
    LambdaVerify --> Done(["Done — schedule retries<br/>on next tick"])

    Reenable --> Done
```

`disable-rule` does not delete anything — it leaves the EventBridge
rule, target, and Lambda permission intact, just stops the cron from
triggering. Inverse of `disable-rule` is `enable-rule` with the same
name.

## 5. Emergency pause and resume

Quickest path to halt all production sending. Both schedules go inert;
the function and its image are untouched, so manual `aws lambda invoke`
calls still work for diagnostics during the pause.

```mermaid
flowchart LR
    Trigger["Operator decides<br/>to halt sends"] --> Disable1["disable-rule<br/>dialtone-outreach-daily-run"]
    Disable1 --> Disable2["disable-rule<br/>dialtone-outreach-reply-check"]
    Disable2 --> Diagnose["Diagnose:<br/>logs / metrics / SES console"]
    Diagnose --> Fix["Fix forward<br/>(code patch + redeploy<br/>or AWS-console action)"]
    Fix --> Verify["aws lambda invoke<br/>--payload<br/>'{&quot;task&quot;:&quot;preflight&quot;}'"]
    Verify --> Healthy{"preflight<br/>exit_code 0?"}
    Healthy -->|"no"| Diagnose
    Healthy -->|"yes"| Enable1["enable-rule<br/>dialtone-outreach-daily-run"]
    Enable1 --> Enable2["enable-rule<br/>dialtone-outreach-reply-check"]
    Enable2 --> Resumed(["Production schedule live"])
```

For SES-side emergencies (account-level send pause, identity revoked)
the AWS Console SES dashboard is the source of truth — boto3 doesn't
expose the un-pause flow, so treat it as a manual one-time step.

## Cross-references

- [runbook-production.md](runbook-production.md) — narrative for every
  state in these diagrams (alarm thresholds, exact commands, troubleshooting)
- [runbook-first-cohort.md](runbook-first-cohort.md) — one-time M2 ramp-up
- [deploy/README.md](../deploy/README.md) — initial deploy + branch protection
- [web-ui-guide.md](web-ui-guide.md) — reviewer-facing UI usage
