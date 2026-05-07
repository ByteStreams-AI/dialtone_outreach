# Sourced by every deploy/*.sh script. Loads ``deploy/config.env`` and
# pre-flights the bare-minimum prerequisites (aws CLI) so failures
# happen up-front with a clear message rather than mid-deploy.
# ``create_lambda.sh`` additionally needs python-dotenv to parse
# ``.env`` — checked there at the point of use.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.env"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "✗ ${CONFIG_FILE} not found." >&2
  echo "  Copy deploy/config.env.example → deploy/config.env and fill it in." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"

if ! command -v aws >/dev/null 2>&1; then
  echo "✗ Required command 'aws' not on PATH." >&2
  exit 1
fi

: "${AWS_REGION:?AWS_REGION must be set in deploy/config.env}"
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID must be set in deploy/config.env}"

# Reject the placeholder values from config.env.example. Both have hit
# silently in practice — the AWS_ACCOUNT_ID one points docker push at
# someone else's account (403 from ECR), and the ALERT_EMAIL one
# subscribes a non-existent address so the SES bounce/complaint alarms
# never reach a human. Better to fail with a clear message than to
# pretend everything succeeded.
if [[ "${AWS_ACCOUNT_ID}" == "123456789012" ]]; then
  echo "✗ AWS_ACCOUNT_ID is still the placeholder (123456789012)." >&2
  echo "  Set it to your real account: aws sts get-caller-identity --query Account --output text" >&2
  exit 1
fi
if [[ "${ALERT_EMAIL:-}" == "ops@example.com" ]]; then
  echo "✗ ALERT_EMAIL is still the placeholder (ops@example.com)." >&2
  echo "  Set it to a real email in deploy/config.env before running setup_alarms.sh." >&2
  exit 1
fi

export AWS_PAGER=""    # Disable the interactive less pager in CI/non-TTY use.

log()  { printf "→ %s\n" "$*"; }
ok()   { printf "✓ %s\n" "$*"; }
warn() { printf "! %s\n" "$*" >&2; }
