#!/usr/bin/env bash
# Check the AgentCore Gateway MCP endpoint with real Cognito tokens (Gate 5).
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_session
get() { aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
export MANAGER_USER MANAGER_PASSWORD TECH_USER TECH_PASSWORD MCP_URL OTHER_WO
MANAGER_USER=$(get /uptime-desk/demo/manager-username)
MANAGER_PASSWORD=$(get /uptime-desk/demo/manager-password)
TECH_USER=$(get /uptime-desk/demo/technician-username)
TECH_PASSWORD=$(get /uptime-desk/demo/technician-password)
MCP_URL=$(get /uptime-desk/mcp/url)
OTHER_WO=${OTHER_WO:?set OTHER_WO to a work order assigned to another technician}
cd "$REPO_ROOT/app"
NODE_OPTIONS="--no-experimental-webstorage" npx playwright test e2e/mcp-gateway.spec.ts
