# Production deploy — AWS Lambda container image

This directory provisions the production scheduler for DialTone Outreach:
a Python 3.12 Lambda container image, two EventBridge schedules (daily
run + reply check), and CloudWatch alarms wired through SNS to an
operator email.

```
EventBridge ─┬─ cron(daily run)        ┐
             └─ rate(reply check)      ├─→ Lambda (container image) ─→ SES / Supabase / IMAP
                                       │           │
SES   ─→ CloudWatch (Reputation.*) ────┤           ├─ stdout / stderr → CloudWatch Logs
Lambda → CloudWatch (Errors)           │           │
                                       └→ CloudWatch alarms → SNS → email
```

## Prerequisites

- AWS account + an IAM user with permission to create ECR repos, IAM
  roles, Lambda functions, EventBridge rules, SNS topics, and CloudWatch
  alarms. The deploy scripts use the credentials of whichever profile
  `aws` finds (`AWS_PROFILE`, `~/.aws/credentials`, env vars, or
  instance role — any AWS auth source works).
- `aws` CLI v2 on `PATH`.
- Docker daemon running locally.
- A Python with `python-dotenv` installed. `create_lambda.sh` resolves
  Python in priority order: `uv run` (if `uv` is on PATH and a
  `pyproject.toml` exists, no venv activation needed) →
  `${REPO_ROOT}/.venv/bin/python` → system `python3`. `uv sync` once at
  repo root is the simplest setup since `python-dotenv` is in
  `requirements.txt`.
- The repo's runtime `.env` populated (Supabase URL/key, AWS SES keys,
  `FROM_EMAIL`, `BUSINESS_ADDRESS`, IMAP creds, etc.). `create_lambda.sh`
  forwards every `KEY=VALUE` from `.env` as a Lambda env var, parsed by
  the same `python-dotenv` the CLI uses — so single/double quoting and
  `\n` escapes match local behavior exactly.
- The sender domain verified in SES with DKIM enabled. Confirm with
  `uv run python cli.py preflight` *before* deploying.

## One-time setup

```bash
cp deploy/config.env.example deploy/config.env
$EDITOR deploy/config.env                       # set account ID, region, alert email

bash deploy/create_iam_role.sh                  # Lambda execution role + SES policy
bash deploy/build_and_push.sh                   # build image, push to ECR
bash deploy/create_lambda.sh                    # create the Lambda function
bash deploy/setup_schedule.sh                   # EventBridge rules → Lambda
bash deploy/setup_alarms.sh                     # SNS topic + CloudWatch alarms
```

After `setup_alarms.sh` runs, AWS sends a confirmation email to
`ALERT_EMAIL`. Click the link or the topic stays unsubscribed and no
alerts ever fire.

## Updating after a code change

Repeated deploys re-run only the build + Lambda update:

```bash
bash deploy/build_and_push.sh
bash deploy/create_lambda.sh
```

Schedule and alarm definitions are idempotent — re-run the corresponding
script if you change a cron expression or threshold in `config.env`.

## Smoke-test the function

```bash
aws lambda invoke \
  --function-name dialtone-outreach \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"preflight"}' \
  --region us-east-1 \
  /tmp/lambda-out.json && cat /tmp/lambda-out.json
```

`preflight` is read-only — it validates env vars, Supabase reachability,
SES quota, and DNS records without touching the contact pipeline. A
successful invocation returns `{"task":"preflight","exit_code":0,...}`
and the run shows up in CloudWatch Logs at
`/aws/lambda/dialtone-outreach`.

> **`task` is required.** Invoking the function with the AWS console's
> default empty `{}` test payload, or `aws lambda invoke` without
> `--payload`, returns a `ValueError`. This is intentional — it
> prevents an accidental click in the console from kicking off a real
> send. Always pass one of `{"task":"preflight"}`,
> `{"task":"run","dry_run":true}`, `{"task":"run"}`, or
> `{"task":"check-replies"}`.

To rehearse an actual run:

```bash
aws lambda invoke \
  --function-name dialtone-outreach \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task":"run","dry_run":true}' \
  --region us-east-1 \
  /tmp/lambda-out.json
```

`dry_run=true` exercises every code path that the real run uses —
template rendering, Supabase reads, cohort gating — without sending
email or writing back to `email_log`.

## Logs

CloudWatch log group: `/aws/lambda/dialtone-outreach`. Each invocation
emits a structured `start task=… request_id=…` line and a matching
`done` line; pivot on `request_id` to follow a single run end-to-end.
Retention is `Never expire` by default — set a sensible retention
policy once volume justifies it:

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/dialtone-outreach \
  --retention-in-days 90 \
  --region us-east-1
```

## Branch protection

This is a one-time GitHub-side step that the deploy scripts cannot
perform on your behalf. From the repo's **Settings → Branches → Add
branch ruleset** (or *Branch protection rules* on classic):

- Branch name pattern: `main`
- Require pull request reviews before merging
- Require status checks to pass before merging
  - Required check: `ci / ci` (the workflow added in [.github/workflows/ci.yml](../.github/workflows/ci.yml))
- Require branches to be up to date before merging
- (Optional) Require linear history

After saving, push a no-op PR and confirm `main` rejects a direct push.

## Tearing it all down

```bash
aws events remove-targets --rule dialtone-outreach-daily-run     --ids 1 --region "$AWS_REGION"
aws events remove-targets --rule dialtone-outreach-reply-check   --ids 1 --region "$AWS_REGION"
aws events delete-rule    --name dialtone-outreach-daily-run     --region "$AWS_REGION"
aws events delete-rule    --name dialtone-outreach-reply-check   --region "$AWS_REGION"
aws cloudwatch delete-alarms --alarm-names \
  dialtone-outreach-ses-bounce-rate \
  dialtone-outreach-ses-complaint-rate \
  dialtone-outreach-lambda-errors --region "$AWS_REGION"
aws lambda  delete-function    --function-name "$LAMBDA_FUNCTION" --region "$AWS_REGION"
aws iam     delete-role-policy --role-name "$LAMBDA_ROLE_NAME" --policy-name dialtone-outreach-ses-send
aws iam     detach-role-policy --role-name "$LAMBDA_ROLE_NAME" \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam     delete-role        --role-name "$LAMBDA_ROLE_NAME"
aws ecr     delete-repository  --repository-name "$ECR_REPO" --force --region "$AWS_REGION"
aws sns     delete-topic       --topic-arn "$TOPIC_ARN" --region "$AWS_REGION"
```
