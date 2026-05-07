#!/usr/bin/env bash
# Create (or update) the Lambda execution role used by the outreach
# function. Permissions:
#
#   * AWSLambdaBasicExecutionRole — write logs to CloudWatch
#   * inline ses-send policy     — send email via SES
#
# Supabase / SES API keys are still passed through as Lambda env vars
# (see ``create_lambda.sh``) — we don't migrate those to IAM here.

source "$(dirname "$0")/_common.sh"

: "${LAMBDA_ROLE_NAME:?LAMBDA_ROLE_NAME must be set in deploy/config.env}"

TRUST_POLICY=$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
)

SES_POLICY=$(cat <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail",
        "ses:GetSendQuota",
        "ses:GetSendStatistics",
        "ses:GetIdentityVerificationAttributes",
        "ses:GetIdentityDkimAttributes"
      ],
      "Resource": "*"
    }
  ]
}
JSON
)

log "Ensuring IAM role ${LAMBDA_ROLE_NAME} exists"
if ! aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "${LAMBDA_ROLE_NAME}" \
    --assume-role-policy-document "${TRUST_POLICY}" \
    --description "Execution role for the DialTone Outreach Lambda" >/dev/null
  ok "Created role ${LAMBDA_ROLE_NAME}"
else
  ok "Role ${LAMBDA_ROLE_NAME} already exists"
fi

log "Attaching AWSLambdaBasicExecutionRole (CloudWatch Logs)"
aws iam attach-role-policy \
  --role-name "${LAMBDA_ROLE_NAME}" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

log "Putting inline SES send policy"
aws iam put-role-policy \
  --role-name "${LAMBDA_ROLE_NAME}" \
  --policy-name dialtone-outreach-ses-send \
  --policy-document "${SES_POLICY}"

ROLE_ARN=$(aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" \
              --query 'Role.Arn' --output text)
ok "Role ARN: ${ROLE_ARN}"
echo "${ROLE_ARN}"
