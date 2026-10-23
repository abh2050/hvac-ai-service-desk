# Gate 2: diagnosis

We recorded three runs on 2026-10-23 in us-east-2 with Bedrock, plus one holdout scoring of the frozen run 3 pipeline.
- **Run 3 on the test cases:** `reports/gate-2.json` and `reports/gate-2-cases.jsonl`.
- **Holdout:** `reports/gate-2-holdout.json` and `reports/gate-2-holdout-cases.jsonl`.
- **Statistics:** `reports/gate-2-stats.json` and `reports/gate-2-holdout-stats.json`.
- **All three runs are kept in `reports/gate-2-runs/`**, including the run 1 report as first written.
- **Cost:** each run took about 280 seconds and cost about $0.22 in model calls.

## Summary

**Result of record.** This gate has two results of record, both from the run 3 pipeline: run 3 on the test cases, and that pipeline frozen and scored once on a holdout.
- **The prompt was chosen on the test set.** Run 3 was picked after runs 1 and 2 were scored on the same 92 test cases. Every lab episode was used in those runs, so no lab holdout exists.
- **The holdout is unused days, not unused episodes.** The frozen pipeline was scored once on 60 flagged field days that no run had used. Those days come from the same 2 field episodes.

**The AI does not significantly beat the rule hint at naming the fault.** It scored 0.424 against 0.326 on the test cases (exact McNemar p = 0.078) and 0.867 against 0.783 on the holdout (p = 0.0625). We make no claim that it does.

**The AI does significantly beat the keyword baseline on verified diagnoses.** It scored 0.293 against 0.043 on the test cases and 0.750 against 0.133 on the holdout (both p < 0.0001). Its citations pass verification at 0.880 on the test cases and 0.915 on the holdout. Citations that fail verification never reach a user, as the tests confirm.

**Weak spots.** These are listed in the README as limitations.
- Lab AHUs get zero verified answers, because no manual covers their coil valves.
- The AI recognizes none of the 11 building operations faults.

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

## Statistics (owner condition 2)

All figures are from `reports/gate-2-stats.json` (test cases) and `reports/gate-2-holdout-stats.json` (holdout). The intervals are Wilson 95% intervals, and the tests are exact McNemar tests on paired cases.

| Comparison | Set | AI | Comparison | Discordant (AI only : other only) | p |
|---|---|---|---|---|---|
| AI proposal vs rule hint | test, 92 cases | 0.424 (0.328 to 0.526) | 0.326 (0.239 to 0.427) | 15 : 6 | 0.078 |
| AI proposal vs rule hint | test, lab, 84 | 0.393 (0.295 to 0.500) | 0.298 (0.210 to 0.402) | 14 : 6 | 0.115 |
| AI proposal vs rule hint | test, field, 8 | 0.750 (0.409 to 0.929) | 0.625 (0.306 to 0.863) | 1 : 0 | 1.000 |
| AI proposal vs rule hint | holdout, field, 60 | 0.867 (0.758 to 0.931) | 0.783 (0.664 to 0.869) | 5 : 0 | 0.0625 |
| AI verified vs baseline verified | test, 92 | 0.293 | 0.043 | 24 : 1 | < 0.0001 |
| AI verified vs baseline verified | holdout, field, 60 | 0.750 | 0.133 | 38 : 1 | < 0.0001 |
| Withheld-evidence probes abstained | test, 20 | 20 of 20 (0.839 to 1.000) | n/a | n/a | n/a |
| Citation support | test | 73 of 83 = 0.880 (0.792 to 0.933) | baseline 0.122 | n/a | n/a |
| Citation support | holdout | 54 of 59 = 0.915 (0.816 to 0.963) | baseline 0.222 | n/a | n/a |

The 60 holdout days come from 2 units, so they are not independent, and the intervals understate the real uncertainty.

## Holdout result (frozen run 3, scored once)

The case set is `data/processed/gate2_holdout_cases.jsonl`, and the results are in `reports/gate-2-holdout.json` and `reports/gate-2-holdout-cases.jsonl`. The diagnosis code, prompts, models, and manual index did not change from run 3 (`git diff 2b976cc` on `services/diagnosis`, `services/citation_verifier`, and the config files is empty).

| Measure | Value |
|---|---|
| Cases | 60 field days: 41 stage 2 compressor, 19 refrigerant undercharge |
| AI proposal accuracy | 0.867 (stage 2: 40 of 41; undercharge: 12 of 19) |
| Rule hint accuracy | 0.783 (stage 2: 39 of 41; undercharge: 8 of 19) |
| AI verified accuracy | 0.750 (stage 2: 35 of 41; undercharge: 10 of 19) |
| AI abstention | 0.133 |
| Citation support | 0.915 |
| Actionability (answered cases with at least one verified check) | 0.269 |
| Sourced lockout step | 0.654 |
| Cost per diagnosis | $0.00239 ($0.14 total) |
| Latency | p50 10.39 s, p95 14.93 s |

## No unverified output reaches a user (owner condition 3)

1. `services/diagnosis/policy.py` keeps only items whose verification passed. `tests/test_no_unverified_output.py` checks every recorded run 3 case and confirms that no failed quote appears in a final output. The recorded run contains failed items, so the test is not vacuous.
2. Work orders carry only the policy output. The `work_order_steps` table enforces `CHECK (verified)`, and a test confirms that an unverified insert fails.
3. `services/api/views.py` is the single read path for the console and the MCP tools. It reads steps only from `work_order_steps`. A test saves a work order for every recorded case and confirms that no failed quote is returned. The MCP tool handlers arrive in Gate 4, and they call this read path.

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
4. The AI significantly beats the keyword baseline on verified diagnoses, on both the test cases and the holdout.
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
| The LLM proposes the cause from sensor evidence | The rule hint | It is not shown to be better (p = 0.078 test, 0.0625 holdout). We keep it because the citation step needs a component and a search query, which the rule hint does not supply. The simpler path, the rule hint, would serve for naming the fault alone. |
| LLM citation selection with deterministic and entailment checks | The BM25 best sentence | It survives: 0.880 against 0.122 citation support. |
| Abstaining without a verified citation | Always answering | It survives: 20 of 20 probes abstain, and no unverified procedure is shown. |
| Operations routing gated by the rules | Trusting the LLM's operations label | It survives: misroutes fall from 9 of 81 to 1 of 81. |
