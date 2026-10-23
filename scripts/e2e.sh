#!/usr/bin/env bash
# Run the Playwright end-to-end test against the hosted app. Demo credentials are read from SSM
# into environment variables for this process only. Usage: scripts/e2e.sh [run-number] [video]
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_session
get() { aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
export MANAGER_USER MANAGER_PASSWORD TECH_USER TECH_PASSWORD
MANAGER_USER=$(get /uptime-desk/demo/manager-username)
MANAGER_PASSWORD=$(get /uptime-desk/demo/manager-password)
TECH_USER=$(get /uptime-desk/demo/technician-username)
TECH_PASSWORD=$(get /uptime-desk/demo/technician-password)
export E2E_RUN="${1:-1}" E2E_VIDEO="${2:-0}"
cd "$REPO_ROOT/app"
NODE_OPTIONS="--no-experimental-webstorage" npx playwright test e2e/full-flow.spec.ts
