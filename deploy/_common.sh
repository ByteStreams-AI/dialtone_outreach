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

export AWS_PAGER=""    # Disable the interactive less pager in CI/non-TTY use.

log()  { printf "→ %s\n" "$*"; }
ok()   { printf "✓ %s\n" "$*"; }
warn() { printf "! %s\n" "$*" >&2; }
