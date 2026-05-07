# Sourced by every deploy/*.sh script. Loads ``deploy/config.env`` and
# pre-flights the bare-minimum prerequisites (aws CLI, jq) so failures
# happen up-front with a clear message rather than mid-deploy.

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

for cmd in aws jq; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "✗ Required command '${cmd}' not on PATH." >&2
    exit 1
  fi
done

: "${AWS_REGION:?AWS_REGION must be set in deploy/config.env}"
: "${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID must be set in deploy/config.env}"

export AWS_PAGER=""    # Disable the interactive less pager in CI/non-TTY use.

log()  { printf "→ %s\n" "$*"; }
ok()   { printf "✓ %s\n" "$*"; }
warn() { printf "! %s\n" "$*" >&2; }
