# Gate 2: diagnosis

We recorded three runs on 2026-10-23 in us-east-2 with Bedrock.
- **Run 3 is the result of record.** Its data is in `reports/gate-2.json`, and each case's output is in `reports/gate-2-cases.jsonl`.
- **All three runs are kept in `reports/gate-2-runs/`**, including the run 1 report as first written.
- **Cost:** each run took about 280 seconds and cost about $0.22 in model calls.

## Summary

The AI names the fault more accurately than the rule hint overall (0.424 against 0.326). Its manual citations pass verification at 0.880, against 0.122 for a keyword baseline. When the policy requires a verified citation, the AI is right on 0.293 of real cases and abstains on 0.348. The baseline is right on 0.043.

It abstained on all 20 cases where we withheld the manual evidence. It finds the economizer RTU and field RTU faults reliably (verified 0.458 and 0.625). Two weak spots remain:
- **Lab AHUs:** zero verified answers. The coil valve faults have no matching manual page.
- **Building operations faults:** the AI never recognizes them (0 of 11).

## What changed across runs

| Run | Change | Why |
|---|---|---|
| 1 | The first full run. It used a propose, retrieve, cite design and 5 manuals. | Smoke tests showed that quotes cannot prove the cause in installation and maintenance manuals. The citations therefore cover what the manual says about the component. |
| 2 | We added 3 component manuals (Siemens and Johnson Controls duct sensors, Honeywell valve actuators). We routed operations faults to operations review, showed the model each day's operating hours, and added a prompt nudge toward operations faults. | Owner approved. Run 1 had 38 of 51 abstentions on components no manual covered. |
| 3 | We reverted the prompt nudge. We kept the manuals, the routing, and the operating hours. Operations routing is now allowed only when no equipment rule fired that day. | Run 2's nudge cut proposal accuracy from 0.402 to 0.304. It also misrouted 9 of 81 equipment cases and let 2 withheld-evidence probes through. Run 3 reverts to the run 1 prompt and adds one safety check. |

Step 1, which names the cause, never sees the manuals. So changes in proposal accuracy come from prompt changes. Changes in abstention and citation support come mostly from the manual set.

## Results by run (measured; ground truth is the LBNL labels; 92 cases plus 20 probes each)

| Metric | Run 1 | Run 2 | Run 3 | Baseline (run 3) |
|---|---|---|---|---|
| Proposal accuracy (step 1) | 0.402 | 0.304 | **0.424** | rule hint 0.326 |
| Verified fault accuracy (abstention counts as wrong) | 0.174 | 0.239 | **0.293** | 0.043 |
| Accuracy when answered | 0.390 | 0.423 | **0.458** | n/a |
| Abstention on real cases | 0.554 | **0.337** | 0.348 | 0.902 |
| Citation support rate | 0.804 | 0.811 | **0.880** | 0.122 |
| Withheld-evidence probes abstained | 20/20 | 18/20 | **20/20** | 20/20 |
| Equipment cases misrouted to operations review | n/a | 9/81 | **1/81** | n/a |
| Operations faults routed to operations review | n/a | 0/11 | 0/11 | n/a |
| Cost per diagnosis | $0.00187 | $0.00187 | $0.00196 | $0 |

## Run 3 detail

### By segment

| Segment | Cases | AI proposal | Rule hint | AI verified | Baseline verified | AI abstention |
|---|---|---|---|---|---|---|
| Lab AHU | 23 | **0.217** | 0.087 | 0.000 | 0.000 | 0.826 |
| Lab economizer RTU | 48 | **0.583** | 0.458 | **0.458** | 0.042 | 0.250 |
| Lab RTU.csv | 13 | 0.000 | **0.077** | 0.000 | **0.077** | 0.000 |
| Field RTUs | 8 | **0.750** | 0.625 | **0.625** | 0.125 | 0.125 |

The lab and field rows are kept separate. The field row rests on 2 faulted episodes.

### Technician-facing output (answered technician cases)

| Metric | Lab | Field | All |
|---|---|---|---|
| Actionability: at least one verified check | 0.377 | 0.500 | 0.390 |
| A sourced lockout or disconnect step | 0.623 | 0.833 | 0.644 |
| Compatibility warning | 1.000 | 1.000 | 1.000 |

Every Release 1 manual is a class match, so the compatibility warning always shows.

### Why the AI abstained (32 of 92 real cases)

| Reason | Cases |
|---|---|
| No retrieved page concerned the component | 21 |
| The verifier rejected every citation | 8 |
| The proposal reply was unusable | 2 |
| An operations proposal conflicted with the equipment rules | 1 |

Lab AHU abstentions are mostly about coil valves: cooling coil valve 7, heating coil valve 10, cooling coil water valve 1. The Honeywell document covers the valve actuator, and the model did not treat actuator pages as covering a stuck or leaking valve.

### Operations faults

All 11 operations cases come from lab RTU.csv. The AI proposed a stage 2 compressor fault on 10 of them and undercharge on 1. The operating-hours evidence did not change that.

### Cost and latency (run 3)

| Measure | Value |
|---|---|
| Diagnosis model, gpt-oss-120b | 220 calls, 495,967 input and 167,640 output tokens, $0.175 |
| Entailment model, gpt-oss-20b | 284 calls, 326,362 input and 73,829 output tokens, $0.045 |
| Cost per diagnosis | $0.00196 |
| Latency, AI path | p50 9.89 s, p95 14.54 s (4 parallel workers) |
| Diagnosis replies cut off at the token limit | 1 of 220 |

Prices come from the AWS Pricing API for us-east-2.

### Policy 1 check

30.4% of the cases have a mean model probability below 0.70. In the pipeline, those go to manual review unless the rules (the primary detector) alarmed.

## Passed

1. Every quote cited by the AI appears on the cited page. The deterministic pass rate is 1.000 in all runs.
2. No unverified quote, check, or safety step reaches the final output.
3. The AI abstained on 20 of 20 withheld-evidence probes in run 3.
4. The AI beats the rule hint at naming the fault overall, and in 3 of 4 segments.
5. The cost per diagnosis is under $0.002.

## Failed

1. Lab AHU diagnoses produce zero verified answers.
2. The AI does not recognize building operations faults (0 of 11).
3. Actionability is 0.390. Most answered cases cite a component description, not an inspection step.

## Not verified

1. Bedrock Guardrails on the diagnosis call. The Guardrail resource is not deployed yet.
2. The Bedrock Knowledge Base on S3 Vectors. This run used a local index of the same Titan v2 vectors.
3. Whether a hot water or chilled water valve service manual would fix the AHU gap.

## Design choices and their baselines

| Choice | Baseline | Outcome |
|---|---|---|
| The LLM proposes the cause from sensor evidence | The rule hint | It survives: 0.424 against 0.326 overall. It loses on lab RTU.csv operations faults. |
| LLM citation selection with deterministic and entailment checks | The BM25 best sentence | It survives: 0.880 against 0.122 citation support. |
| Abstaining without a verified citation | Always answering | It survives: 20 of 20 probes abstain, and no unverified procedure is shown. |
| Operations routing gated by the rules | Trusting the LLM's operations label | It survives: misroutes fall from 9 of 81 to 1 of 81. |
