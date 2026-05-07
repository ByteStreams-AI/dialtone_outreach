#!/usr/bin/env bash
# Create (or update) two EventBridge rules that drive the Lambda:
#
#   1. dialtone-outreach-daily-run     → {"task": "run"}
#   2. dialtone-outreach-reply-check   → {"task": "check-replies"}
#
# Idempotent — safe to re-run after editing schedule expressions in
# ``deploy/config.env``.

source "$(dirname "$0")/_common.sh"

: "${LAMBDA_FUNCTION:?LAMBDA_FUNCTION must be set in deploy/config.env}"
: "${DAILY_RUN_SCHEDULE:?DAILY_RUN_SCHEDULE must be set in deploy/config.env}"
: "${REPLY_CHECK_SCHEDULE:?REPLY_CHECK_SCHEDULE must be set in deploy/config.env}"

LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${LAMBDA_FUNCTION}"

upsert_rule() {
  local rule_name="$1"
  local schedule="$2"
  local input_json="$3"
  local statement_id="$4"

  log "Upserting rule ${rule_name} (${schedule})"
  aws events put-rule \
    --name "${rule_name}" \
    --schedule-expression "${schedule}" \
    --state ENABLED \
    --region "${AWS_REGION}" >/dev/null

  log "  → target = ${LAMBDA_FUNCTION}"
  aws events put-targets \
    --rule "${rule_name}" \
    --region "${AWS_REGION}" \
    --targets "Id=1,Arn=${LAMBDA_ARN},Input='${input_json}'" >/dev/null

  # Allow EventBridge to invoke the Lambda. ``add-permission`` errors if
  # the statement-id already exists, so swallow that case.
  if ! aws lambda add-permission \
        --function-name "${LAMBDA_FUNCTION}" \
        --statement-id "${statement_id}" \
        --action lambda:InvokeFunction \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:${AWS_REGION}:${AWS_ACCOUNT_ID}:rule/${rule_name}" \
        --region "${AWS_REGION}" >/dev/null 2>&1; then
    log "  permission ${statement_id} already present — skipped"
  fi

  ok "${rule_name} ready"
}

upsert_rule "dialtone-outreach-daily-run" \
            "${DAILY_RUN_SCHEDULE}" \
            '{"task":"run"}' \
            "events-invoke-daily-run"

upsert_rule "dialtone-outreach-reply-check" \
            "${REPLY_CHECK_SCHEDULE}" \
            '{"task":"check-replies"}' \
            "events-invoke-reply-check"

ok "Schedules configured."
echo
log "Test invocation (without waiting for the cron):"
echo "  aws lambda invoke --function-name ${LAMBDA_FUNCTION} \\"
echo "      --cli-binary-format raw-in-base64-out \\"
echo "      --payload '{\"task\":\"preflight\"}' --region ${AWS_REGION} /tmp/lambda-out.json"
