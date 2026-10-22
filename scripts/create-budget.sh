#!/usr/bin/env bash
# Create the $50/month Uptime Desk budget, scoped to resources tagged project=uptime-desk.
# The tag filter counts spend only after "project" is activated as a cost allocation tag
# in the Billing console (activation can take up to 24 hours).
# Usage: BUDGET_EMAIL=you@example.com scripts/create-budget.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_session
: "${BUDGET_EMAIL:?set BUDGET_EMAIL to the address that receives alerts}"

# shellcheck disable=SC2016  # "$uptime-desk" is AWS tag syntax, not a shell variable
budget='{
  "BudgetName": "uptime-desk-monthly",
  "BudgetLimit": {"Amount": "50", "Unit": "USD"},
  "BudgetType": "COST",
  "TimeUnit": "MONTHLY",
  "CostFilters": {"TagKeyValue": ["user:project$uptime-desk"]}
}'
notifications=$(cat <<JSON
[
  {"Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 80, "ThresholdType": "PERCENTAGE"},
   "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "$BUDGET_EMAIL"}]},
  {"Notification": {"NotificationType": "FORECASTED", "ComparisonOperator": "GREATER_THAN", "Threshold": 100, "ThresholdType": "PERCENTAGE"},
   "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "$BUDGET_EMAIL"}]}
]
JSON
)
echo "$budget"
echo "$notifications"
confirm "Create this budget in account $ACCOUNT_ID?"
aws budgets create-budget --account-id "$ACCOUNT_ID" --budget "$budget" --notifications-with-subscribers "$notifications"
echo "Created budget uptime-desk-monthly."
