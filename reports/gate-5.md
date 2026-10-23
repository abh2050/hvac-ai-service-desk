# Gate 5: cloud and app

Measured on 2026-10-23 in us-east-2. The results are in `reports/gate-5.json`, the per-run results in `reports/gate-5-e2e/`, and the MCP check in `reports/gate-5-e2e/mcp-gateway-check.json`.

## Summary

Uptime Desk runs end to end on AWS behind Cognito sign-in.

- **End-to-end runs:** the hosted app passed **8 of 10** runs: replay, diagnosis, approval, OR-Tools dispatch, then the technician assistant.
- **Why 2 runs failed:** the work order was **blocked** for "no sourced lockout step", so approval could not happen. The safety check behaved as designed. The cause is that the diagnosis model does not produce or verify the lockout quote every time for the same recorded day. The owner accepted 8 of 10 as the result of record, and the cause is listed below.
- **Speed:** a passing run went from replay start to a drafted work order in a median **39.4 s**, and to a dispatched technician in **77.3 s**.
- **Cost:** model calls cost a median **$0.0021 per incident**.
- **Access control:** no technician read another technician's work, either through the app or through the MCP gateway.

## What is deployed

| Part | Where | Profile |
|---|---|---|
| App (Vite, React, Amplify UI sign-in) | https://main.du00v4uwlekbh.amplifyapp.com, built from GitHub `main` | idle |
| Cognito user pool, `manager` and `technician` groups | Amplify Gen 2 (`app/amplify`); pool and client ids in SSM | idle |
| HTTP API (FastAPI on Lambda in the VPC); Cognito JWT on every route except CORS preflight; throttled at 5 requests per second, burst 10 | https://9pq6z01gmc.execute-api.us-east-2.amazonaws.com | idle |
| MCP endpoint: AgentCore Gateway, Cognito JWT, identity-injecting REQUEST interceptor, Lambda tool target | https://uptime-desk-mcp-4igswqw680.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp | idle |
| Aurora PostgreSQL 16.13 Serverless v2, auto-pausing at 0 ACU | isolated subnets | idle |
| Bedrock Knowledge Base on S3 Vectors (Titan v2, 654 page chunks); Bedrock Guardrail | | idle |
| CloudWatch dashboard `uptime-desk`: cost per incident, stage latency, Bedrock tokens, denied calls | | idle |
| Kinesis replay stream, detection and case Lambdas, two Step Functions state machines, EventBridge rules, Fargate OR-Tools task | | demo |

There is no NAT gateway. The in-VPC Lambdas reach AWS services through 4 interface endpoints in 1 AZ and the free S3 gateway endpoint.

## End-to-end test (measured)

`app/e2e/full-flow.spec.ts` drives Chromium against the hosted URL:

1. A manager signs in and replays the field day Site2-Colchester-10t, 2020-06-18 (replay of recorded data).
2. The test waits for the work order and checks that the diagnosis page shows verified citations or an abstention.
3. The manager approves the work order, which resumes the Step Functions run, and the test waits for the Fargate OR-Tools result on the dispatch board.
4. Technician T01 signs in, asks the assistant for their jobs, then asks for the manager's new order. That order belongs to another technician.

| Measure | Result |
|---|---|
| Full flow passed | **8 of 10** |
| Failed runs | 1 and 4: work order blocked, "no sourced lockout or disconnect step in the manuals" |
| Replay start to work order draft (passing runs) | median **39.4 s**, range 36.3 to 42.5 |
| Replay start to dispatch | median **77.3 s**, range 74.2 to 81.4 |
| Sign-in to test end | median **93.8 s**, range 89.7 to 99.0 |
| Dispatch outcome (passing runs) | 8 of 8 assigned by OR-Tools |
| Cross-technician request denied | 8 of 8 |
| Data leaked to the other technician | **0** |
| Work orders created in the batch | 8 draft and 2 blocked (CloudWatch metric `WorkOrders`) |

A harness defect affected this batch. `scripts/e2e.sh` also ran the MCP check file without its settings, so every process exited with code 1. The pass and fail counts above come from the full-flow test result in each run's log. The script now runs only the full-flow test.

## Cost per incident (measured)

| Item | Value | Source |
|---|---|---|
| Model calls per incident (diagnosis gpt-oss-120b plus entailment gpt-oss-20b) | average **$0.00206**, range $0.00197 to $0.00226, over 10 incidents | CloudWatch `UptimeDesk/IncidentModelCostUSD` |
| Lambda, Step Functions, EventBridge, Fargate per incident | not isolated | Cost Explorer does not resolve single runs |

## MCP gateway check with real Cognito tokens (measured)

| Check | Result |
|---|---|
| Call without a token | HTTP **401** |
| Tools listed | `uptime___get_work_order`, `uptime___list_my_jobs`, `uptime___get_asset_history`, `uptime___search_manuals`, plus AgentCore's built-in tool search |
| T01 lists own jobs | 9 jobs, all T01's |
| T01 reads T16's work order | **denied**: "work order is assigned to another technician" |
| T01 sends `caller_context` claiming the manager role | **denied**: the interceptor replaced the claim with the token's identity |
| Manager reads the same work order | found, assigned to T16 |

## Idle cost

**Not measured yet.** The owner keeps the demo profile up for one week so a hiring manager can use the app. The idle cost is measured from Cost Explorer after `scripts/demo-down.sh`, once a full idle day has been billed.

The list-price estimate is about $7.50 per week idle and about $3 per week more with the demo profile up. This is an estimate, not a measurement.

## Defects found and fixed in this gate

1. CORS preflight requests hit the JWT authorizer and got 401, so the browser showed "Failed to fetch". We added an unauthenticated `OPTIONS` route that returns 204. Every other method still needs a token.
2. Times were stored as Connecticut wall-clock time but read as UTC, which put SLAs off by 4 hours. Aurora sessions now use `America/New_York`.
3. The detection Lambda failed on import: the XGBoost classifier wrapper needs scikit-learn. It now loads a plain Booster. A test shows the probabilities match to within 1e-6.
4. The API's assistant failed on import of the MCP SDK. That import is now lazy, and every handler's imports are checked inside the container image before each deploy.
5. Live dispatch planned from midnight, so late-day jobs found no slots. It now plans the next 24 hours from the current hour. Gate 3's scenario evaluation is unchanged.
6. The cost-profile tag was applied app-wide, so a demo deploy retagged always-on resources. Tags are now set per stack.
7. Knowledge Base list metadata came back with quote characters. These are now cleaned. Filtering was already correct.
8. One local test video was pushed to the public repo in commit `30310ed`. It held no passwords or tokens, which we checked against the real values. It was removed from the current tree, and every `artifacts*` folder is now ignored. It remains in that commit's history unless the owner asks for a rewrite.

## Not verified

1. Idle cost (see above).
2. The approval-timeout path running live. The 4-hour Step Functions timeout, then escalation, is tested in code (Gate 3, policy 9), but no live run waited 4 hours.
3. Whether the Bedrock Guardrail blocks anything in normal use. It is attached, but no blocked event was observed.
4. Live diagnosis accuracy across many scenarios. The live pipeline uses the Bedrock Knowledge Base where Gate 2 used a local index of the same vectors. Only the Colchester day was run repeatedly.

## Design choices and their baselines

| Choice | Baseline | Outcome |
|---|---|---|
| Interface endpoints, no NAT | NAT gateway | It works for every in-VPC call (Aurora, Bedrock, Secrets Manager, Step Functions). The idle estimate is not yet measured. |
| Identity injected by a gateway interceptor | Trusting the model or client to send the technician id | It survives: a spoofed manager claim was replaced and denied. |
| Rules primary with the model as second opinion; live replay through Kinesis | Batch scoring only | The live path matched Gate 1 window by window on recorded days (`tests/test_live_detection.py`). |
| A lockout step must be sourced before approval | Allow approval without one | It held: 2 of 10 runs were blocked rather than dispatched without a sourced step. This costs demo reliability, and the owner accepted that. |
