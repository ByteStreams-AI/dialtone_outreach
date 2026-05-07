#!/usr/bin/env bash
# Create (or update) the Lambda function from the image pushed by
# ``build_and_push.sh``. Reads runtime env vars from the project's
# ``.env`` file at the repo root and forwards them as Lambda env vars
# so config.py finds the same values it does locally.

source "$(dirname "$0")/_common.sh"

: "${LAMBDA_FUNCTION:?LAMBDA_FUNCTION must be set in deploy/config.env}"
: "${LAMBDA_ROLE_NAME:?LAMBDA_ROLE_NAME must be set in deploy/config.env}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  warn "${ENV_FILE} not found; the Lambda will be created without env vars."
  warn "Populate them with 'aws lambda update-function-configuration --environment ...' or rerun after creating the file."
fi

REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"
ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

# Build the JSON ``Variables`` map from the .env file (if any). Only
# KEY=VALUE lines are forwarded; comments and blanks are dropped.
build_env_json() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo '{"Variables":{}}'
    return
  fi
  jq -Rsn '
    {Variables:
      ([inputs |
        split("\n")[] |
        select(length > 0) |
        select(test("^\\s*#") | not) |
        capture("^\\s*(?<k>[A-Za-z_][A-Za-z0-9_]*)=(?<v>.*)$") |
        .v |= sub("^\"(?<x>.*)\"$"; .x) |
        {(.k): .v}
      ] | add // {})
    }' < "${ENV_FILE}"
}

ENV_JSON=$(build_env_json)

if aws lambda get-function --function-name "${LAMBDA_FUNCTION}" \
      --region "${AWS_REGION}" >/dev/null 2>&1; then
  log "Updating existing Lambda ${LAMBDA_FUNCTION}"

  aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION}" \
    --image-uri "${IMAGE_URI}" \
    --region "${AWS_REGION}" >/dev/null

  log "Waiting for code update to complete"
  aws lambda wait function-updated \
    --function-name "${LAMBDA_FUNCTION}" \
    --region "${AWS_REGION}"

  aws lambda update-function-configuration \
    --function-name "${LAMBDA_FUNCTION}" \
    --timeout "${LAMBDA_TIMEOUT}" \
    --memory-size "${LAMBDA_MEMORY}" \
    --environment "${ENV_JSON}" \
    --region "${AWS_REGION}" >/dev/null

  ok "Updated ${LAMBDA_FUNCTION}"
else
  log "Creating Lambda ${LAMBDA_FUNCTION}"

  aws lambda create-function \
    --function-name "${LAMBDA_FUNCTION}" \
    --package-type Image \
    --code "ImageUri=${IMAGE_URI}" \
    --role "${ROLE_ARN}" \
    --timeout "${LAMBDA_TIMEOUT}" \
    --memory-size "${LAMBDA_MEMORY}" \
    --environment "${ENV_JSON}" \
    --region "${AWS_REGION}" >/dev/null

  ok "Created ${LAMBDA_FUNCTION}"
fi

aws lambda get-function-configuration \
  --function-name "${LAMBDA_FUNCTION}" \
  --region "${AWS_REGION}" \
  --query '{name:FunctionName,arn:FunctionArn,image:Code.ImageUri,timeout:Timeout,memory:MemorySize}' \
  --output table
