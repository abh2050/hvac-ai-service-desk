# shellcheck shell=bash disable=SC2034
# Shared settings for Uptime Desk scripts. Region is us-east-2 because the org SCP denies
# regional services in us-west-2 and us-east-1.
export AWS_PROFILE="${AWS_PROFILE:-awsnew}"
export AWS_REGION="us-east-2"
export AWS_DEFAULT_REGION="us-east-2"
ACCOUNT_ID="054772656600"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$REPO_ROOT/infra"

require_session() {
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "AWS session for profile $AWS_PROFILE is missing or expired. Run: aws login" >&2
    exit 1
  fi
}

confirm() {
  local prompt="$1"
  if [[ "${UPTIME_DESK_YES:-}" == "1" ]]; then return 0; fi
  read -r -p "$prompt [type yes]: " answer
  [[ "$answer" == "yes" ]] || { echo "Stopped. Nothing was changed." >&2; exit 1; }
}
