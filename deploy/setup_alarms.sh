#!/usr/bin/env bash
# Create (or update) the operational alarm fan-out:
#
#   * SNS topic dialtone-outreach-ses-alerts (email subscription)
#   * CloudWatch alarm — SES Reputation.BounceRate    > BOUNCE_RATE_THRESHOLD
#   * CloudWatch alarm — SES Reputation.ComplaintRate > COMPLAINT_RATE_THRESHOLD
#   * CloudWatch alarm — Lambda Errors                > 0 over 1 invocation
#
# AWS suspends sending automatically at 10% bounces / 0.5% complaints —
# the alarms here fire well before that so the operator can investigate
# while the account is still in good standing.

source "$(dirname "$0")/_common.sh"

: "${ALERT_EMAIL:?ALERT_EMAIL must be set in deploy/config.env}"
: "${SNS_TOPIC_NAME:?SNS_TOPIC_NAME must be set in deploy/config.env}"
: "${BOUNCE_RATE_THRESHOLD:?BOUNCE_RATE_THRESHOLD must be set in deploy/config.env}"
: "${COMPLAINT_RATE_THRESHOLD:?COMPLAINT_RATE_THRESHOLD must be set in deploy/config.env}"
: "${LAMBDA_FUNCTION:?LAMBDA_FUNCTION must be set in deploy/config.env}"

log "Creating / fetching SNS topic ${SNS_TOPIC_NAME}"
TOPIC_ARN=$(aws sns create-topic \
  --name "${SNS_TOPIC_NAME}" \
  --region "${AWS_REGION}" \
  --query TopicArn --output text)
ok "Topic ARN: ${TOPIC_ARN}"

log "Subscribing ${ALERT_EMAIL} to the topic"
EXISTING_SUB=$(aws sns list-subscriptions-by-topic \
  --topic-arn "${TOPIC_ARN}" \
  --region "${AWS_REGION}" \
  --query "Subscriptions[?Endpoint=='${ALERT_EMAIL}'] | [0].SubscriptionArn" \
  --output text)
if [[ "${EXISTING_SUB}" == "None" || -z "${EXISTING_SUB}" ]]; then
  aws sns subscribe \
    --topic-arn "${TOPIC_ARN}" \
    --protocol email \
    --notification-endpoint "${ALERT_EMAIL}" \
    --region "${AWS_REGION}" >/dev/null
  warn "Subscription created — confirm via the email AWS just sent to ${ALERT_EMAIL}"
else
  ok "Email ${ALERT_EMAIL} already subscribed"
fi

put_alarm() {
  local name="$1"
  local description="$2"
  local namespace="$3"
  local metric="$4"
  local threshold="$5"
  local extra_args=("${@:6}")

  log "Upserting alarm ${name} (${metric} > ${threshold})"
  aws cloudwatch put-metric-alarm \
    --alarm-name "${name}" \
    --alarm-description "${description}" \
    --metric-name "${metric}" \
    --namespace "${namespace}" \
    --statistic Maximum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold "${threshold}" \
    --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching \
    --alarm-actions "${TOPIC_ARN}" \
    --ok-actions    "${TOPIC_ARN}" \
    --region "${AWS_REGION}" \
    "${extra_args[@]}"
  ok "${name}"
}

put_alarm \
  "dialtone-outreach-ses-bounce-rate" \
  "SES bounce rate exceeded ${BOUNCE_RATE_THRESHOLD} (AWS suspends at 0.10)" \
  "AWS/SES" \
  "Reputation.BounceRate" \
  "${BOUNCE_RATE_THRESHOLD}"

put_alarm \
  "dialtone-outreach-ses-complaint-rate" \
  "SES complaint rate exceeded ${COMPLAINT_RATE_THRESHOLD} (AWS suspends at 0.005)" \
  "AWS/SES" \
  "Reputation.ComplaintRate" \
  "${COMPLAINT_RATE_THRESHOLD}"

put_alarm \
  "dialtone-outreach-lambda-errors" \
  "DialTone Outreach Lambda raised an unhandled error" \
  "AWS/Lambda" \
  "Errors" \
  "0" \
  --dimensions "Name=FunctionName,Value=${LAMBDA_FUNCTION}"

ok "Alarms configured."
