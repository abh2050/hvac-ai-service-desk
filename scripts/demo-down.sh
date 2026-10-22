#!/usr/bin/env bash
# Switch back to the idle profile: destroy only the demo stack. The foundation stack
# (data, Aurora with auto pause, Cognito, API, endpoints) stays.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_session
cd "$INFRA_DIR"

if ! aws cloudformation describe-stacks --stack-name UptimeDesk-Demo >/dev/null 2>&1; then
  echo "UptimeDesk-Demo is not deployed. The account is already in the idle profile."
  exit 0
fi
aws cloudformation list-stack-resources --stack-name UptimeDesk-Demo \
  --query 'StackResourceSummaries[].[ResourceType,LogicalResourceId]' --output table
confirm "Destroy UptimeDesk-Demo (the resources above)?"
npx cdk destroy -c profile=demo UptimeDesk-Demo --force
echo "Idle profile restored."
