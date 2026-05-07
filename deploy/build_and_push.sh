#!/usr/bin/env bash
# Build the Lambda container image and push it to ECR. Idempotent:
# creates the ECR repository on first run and re-pushes the same tag on
# subsequent runs (Lambda picks up the new image when ``create_lambda.sh``
# runs ``update-function-code``).

source "$(dirname "$0")/_common.sh"

REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"

log "Ensuring ECR repository ${ECR_REPO} exists in ${AWS_REGION}"
if ! aws ecr describe-repositories --repository-names "${ECR_REPO}" \
      --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws ecr create-repository \
    --repository-name "${ECR_REPO}" \
    --region "${AWS_REGION}" \
    --image-scanning-configuration scanOnPush=true >/dev/null
  ok "Created ECR repo ${ECR_REPO}"
else
  ok "ECR repo ${ECR_REPO} already exists"
fi

log "Authenticating Docker against ECR"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REPO_URI}"

log "Building image ${IMAGE_URI}"
# --provenance=false keeps the image OCI-compatible with Lambda; recent
# BuildKit defaults add provenance attestations that Lambda rejects.
docker build \
  --provenance=false \
  --platform linux/amd64 \
  -t "${IMAGE_URI}" \
  "$(dirname "$0")/.."

log "Pushing image"
docker push "${IMAGE_URI}"

ok "Pushed ${IMAGE_URI}"
echo "${IMAGE_URI}"
