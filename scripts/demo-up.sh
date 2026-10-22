#!/usr/bin/env bash
# Switch from the idle profile to the demo profile: deploy the demo stack (Kinesis stream,
# ECS cluster for the Fargate optimizer, dashboards) on top of the always-on foundation.
# Shows the change set and asks before deploying.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_session
cd "$INFRA_DIR"

echo "Change set for the demo profile:"
npx cdk diff -c profile=demo UptimeDesk-Foundation UptimeDesk-Demo || true
confirm "Deploy the demo profile to $ACCOUNT_ID in $AWS_REGION?"
npx cdk deploy -c profile=demo UptimeDesk-Foundation UptimeDesk-Demo --require-approval never \
  --outputs-file "$REPO_ROOT/reports/demo-outputs.json"
echo "Demo profile is up. Run scripts/demo-down.sh when the demo ends."
