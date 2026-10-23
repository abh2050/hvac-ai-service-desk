#!/usr/bin/env bash
# Gate 5 measurement: run the end-to-end test N times in a row against the hosted app.
# Results: reports/gate-5-e2e/batch-<n>.json per run, plus the Playwright log per run.
set -uo pipefail
N="${1:-10}"
export E2E_DAY="${E2E_DAY:-2020-06-18}" E2E_UNIT="${E2E_UNIT:-Site2-Colchester-10t}"
mkdir -p "$(dirname "$0")/../reports/gate-5-e2e/logs"
for i in $(seq 1 "$N"); do
  echo "=== run $i of $N ($(date -u +%H:%M:%S) UTC)"
  "$(dirname "$0")/e2e.sh" "batch-$i" 0 > "$(dirname "$0")/../reports/gate-5-e2e/logs/batch-$i.log" 2>&1
  echo "exit $?"
done
