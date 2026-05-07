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

# Build the JSON ``Variables`` map from the .env file (if any). Uses the
# project's own ``python-dotenv`` so the Lambda environment matches the
# CLI's runtime parser exactly:
#   * single- and double-quoted values both have their quotes stripped
#   * \n / \t escapes inside double-quoted values are interpreted (so
#     multi-line values like BUSINESS_ADDRESS render correctly in the
#     CAN-SPAM footer)
#   * ``export`` prefixes and inline comments are handled by dotenv
# Hand-rolled parsers diverged from this on every edge case in practice;
# delegating to dotenv is the only way to keep them in lockstep.
build_env_json() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo '{"Variables":{}}'
    return
  fi

  local python="python3"
  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    python="${REPO_ROOT}/.venv/bin/python"
  fi

  "${python}" - "${ENV_FILE}" <<'PY'
import json
import sys
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:
    sys.stderr.write(
        "✗ python-dotenv is not installed in the active Python.\n"
        "  Activate the project venv (it's in requirements.txt) or run\n"
        "    pip install python-dotenv\n"
        "  before re-running this script.\n"
    )
    sys.exit(1)

# Lambda rejects ``CreateFunction`` / ``UpdateFunctionConfiguration``
# if the env map contains any key the runtime reserves. AWS_ACCESS_KEY_ID,
# AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, and AWS_REGION are populated
# automatically from the execution role + function region — boto3 picks
# them up via the default credential chain, so SES / Supabase calls just
# work without us forwarding the operator's local IAM-user keys.
# Full list: https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
RESERVED = {
    "_HANDLER",
    "_X_AMZN_TRACE_ID",
    "AWS_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_DEFAULT_REGION",
    "AWS_EXECUTION_ENV",
    "AWS_LAMBDA_FUNCTION_MEMORY_SIZE",
    "AWS_LAMBDA_FUNCTION_NAME",
    "AWS_LAMBDA_FUNCTION_VERSION",
    "AWS_LAMBDA_INITIALIZATION_TYPE",
    "AWS_LAMBDA_LOG_GROUP_NAME",
    "AWS_LAMBDA_LOG_STREAM_NAME",
    "AWS_LAMBDA_RUNTIME_API",
    "AWS_REGION",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "LAMBDA_RUNTIME_DIR",
    "LAMBDA_TASK_ROOT",
    "TZ",
}

env_path = Path(sys.argv[1])
parsed = {k: v for k, v in dotenv_values(env_path).items() if v is not None}
filtered = {k: v for k, v in parsed.items() if k not in RESERVED}
dropped = sorted(parsed.keys() - filtered.keys())
if dropped:
    sys.stderr.write(
        f"  (dropped Lambda-reserved keys: {', '.join(dropped)})\n"
    )
print(json.dumps({"Variables": filtered}))
PY
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
