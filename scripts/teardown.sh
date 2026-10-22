#!/usr/bin/env bash
# Remove everything Uptime Desk created in the account: the demo and foundation stacks,
# the Amplify app, the project budget, and the SSM parameters under /uptime-desk/.
# The CDK bootstrap stack is shared with other projects and is left in place.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_session
cd "$INFRA_DIR"

echo "This removes all Uptime Desk resources in $ACCOUNT_ID ($AWS_REGION):"
aws cloudformation describe-stacks \
  --query "Stacks[?starts_with(StackName,'UptimeDesk-') || starts_with(StackName,'amplify-uptimedesk')].StackName" --output text
aws ssm get-parameters-by-path --path /uptime-desk/ --recursive --query 'Parameters[].Name' --output text || true
confirm "Delete all of the above?"

if aws cloudformation describe-stacks --stack-name UptimeDesk-Demo >/dev/null 2>&1; then
  npx cdk destroy -c profile=demo UptimeDesk-Demo --force
fi
npx cdk destroy UptimeDesk-Foundation --force

app_id=$(aws amplify list-apps --query "apps[?name=='uptime-desk'].appId" --output text)
if [[ -n "$app_id" ]]; then aws amplify delete-app --app-id "$app_id" >/dev/null; echo "Deleted Amplify app $app_id"; fi

for name in $(aws ssm get-parameters-by-path --path /uptime-desk/ --recursive --query 'Parameters[].Name' --output text); do
  aws ssm delete-parameter --name "$name"
done

if aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name uptime-desk-monthly >/dev/null 2>&1; then
  aws budgets delete-budget --account-id "$ACCOUNT_ID" --budget-name uptime-desk-monthly
  echo "Deleted budget uptime-desk-monthly"
fi
echo "Teardown complete."
