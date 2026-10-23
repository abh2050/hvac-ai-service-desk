# Gate 2: diagnosis

Run on 2026-10-23 in us-east-2 with Bedrock. Results are in `reports/gate-2.json`, and each case's full output is in `reports/gate-2-cases.jsonl`. The run took 281 seconds and cost $0.21 in model calls.

## Summary

The AI names the fault more accurately than the rule hint in 3 of 4 data segments. Its citations pass verification far more often than the keyword baseline's: 0.804 against 0.122. Once the policy requires a verified manual citation, though, the AI abstains on 55% of cases. Of its 51 abstentions, 38 occur because no manual page covers the component involved, such as the supply air temperature sensor or the cooling coil valve. The manual set limits the result more than the model does. Both paths abstained on all 20 cases where the evidence was withheld.

## Method

- **Cases.** The cases come from `data/processed/gate2_cases.jsonl`, built by `pipelines/evaluation/gate2_cases.py`. There is one case for each scored faulted Release 1 day that Gate 1 detection flagged. Field episodes contribute 4 evenly spaced days each.
  - 92 cases: 84 lab and 8 field.
  - 20 evidence-withheld probes. Their passages come from an unrelated query, so the correct answer is to abstain.
  - 23 faulted days that detection did not flag are not diagnosed.
  - The LBNL label never enters a prompt.
- **AI path.** `services/diagnosis/`, `services/citation_verifier/`.
  1. gpt-oss-120b proposes a cause from the sensor evidence and rule results, choosing from a closed list for the equipment class. It also writes a search query about the component involved.
  2. Titan Text Embeddings v2 retrieves the 6 best manual chunks from manuals for that equipment class.
  3. gpt-oss-120b quotes what those pages say about the component, plus checks and safety steps. It abstains if no page concerns the component.
  4. The verifier runs a trigram match of each quote on the cited page (threshold 0.6) and a gpt-oss-20b entailment check. A citation passes only when both pass.
  5. The policy (`services/diagnosis/policy.py`) drops every unverified item. It returns "insufficient evidence" when no citation survives, and it flags manuals that match only the equipment class.
- **Baseline (no AI).**
  - The cause is the Gate 1 rule hint.
  - BM25 keyword retrieval finds a passage, and the citation is the sentence there that best matches the component name.
  - The same verifier and the same component claim judge it.
- **Not in this run.** Two pieces of the planned architecture were missing:
  - Bedrock Guardrails were not attached, because the Guardrail resource is not deployed yet.
  - Retrieval used a local index of the same Titan v2 vectors, not a Bedrock Knowledge Base, which is not deployed yet.

## Results (measured; ground truth is the LBNL labels)

### Naming the fault

| Segment | Cases | AI proposal accuracy | Rule hint accuracy | AI final accuracy (verified) | Baseline final accuracy (verified) | AI abstention |
|---|---|---|---|---|---|---|
| Lab AHU | 23 | **0.174** | 0.087 | 0.087 | 0.000 | 0.739 |
| Lab economizer RTU | 48 | **0.562** | 0.458 | 0.188 | 0.021 | 0.625 |
| Lab RTU.csv | 13 | 0.000 | **0.077** | 0.000 | 0.077 | 0.154 |
| Field RTUs | 8 | **0.750** | 0.625 | 0.625 | 0.125 | 0.250 |
| All | 92 | **0.402** | 0.326 | 0.174 | 0.033 | 0.554 |

Final accuracy counts an abstention as wrong. When the AI does answer, it is right on 0.390 of all cases (0.314 lab, 0.833 field).

On lab RTU.csv the AI never proposed a building operations fault. Those faults make up 11 of the 13 cases, and the AI proposed stage 2 compressor faults or undercharge instead. That is the weak result in this gate.

### Citations and actions

| Metric | AI | Baseline |
|---|---|---|
| Citation support rate (both checks pass) | **0.804** (56 citations) | 0.122 |
| Quotes found word for word on the cited page | 1.000 | n/a (copied from the page) |
| Actionability: answered cases with at least one verified check | 0.585 | 1.000 on the 9 cases it answered |
| Answered cases with a sourced lockout or disconnect step | 0.902 | not produced |
| Compatibility warning rate on answered cases | 1.000 | not produced |

The compatibility warning rate is 1.000 as expected, because no Release 1 unit has an exact manual match (see `data/SOURCES.md`).

### Abstention when evidence is missing

There were 20 probes. The AI abstained on 20 of 20, and the model itself chose to abstain on 20 of 20. The baseline also abstained on 20 of 20.

### Why the AI abstained on normal cases

| Reason | Cases (of 51 abstentions) |
|---|---|
| No retrieved page concerned the component | 38 |
| The verifier rejected every citation | 11 |
| The proposal reply could not be used | 2 |

The components the manuals do not cover most often are the supply air temperature sensor (17 cases), the cooling coil valve (9), and the heating coil valve (8).

### Cost and latency

| Measure | Value |
|---|---|
| Cost per diagnosis, all model calls | $0.00187 |
| Diagnosis model (gpt-oss-120b) | 221 calls, 476,558 input and 159,738 output tokens, $0.1673 |
| Entailment model (gpt-oss-20b) | 244 calls, 290,819 input and 71,539 output tokens, $0.0418 |
| Latency, AI path | p50 8.89 s, p95 17.25 s (4 parallel workers) |
| Latency, baseline | p50 0.72 s |
| Diagnosis replies cut off at the token limit | 4 of 221 |

Prices are from the AWS Pricing API for us-east-2. gpt-oss-120b costs $0.15 per million input tokens and $0.60 per million output tokens. gpt-oss-20b costs $0.07 and $0.30.

### Policy 1 check

30.4% of the cases have a mean model probability below the 0.70 threshold. In the deployed pipeline, those cases go to manual review before diagnosis.

## Changes made during smoke tests, before the recorded run

Smoke tests on 3 and 5 cases are not reported. They led to three changes before the full run:

1. **Propose, retrieve, cite.** The first design asked the quotes to prove the cause. These manuals cover installation and maintenance, not fault signatures, so the model abstained on everything. In the new design, the cause comes from the sensor evidence, and the citations cover what the manual says about the component.
2. **The entailment judge's token limit went from 400 to 3,000, and its reasoning effort was set to low.** gpt-oss counts reasoning tokens against the limit, and some replies came back empty.
3. **Tolerant parsing of the judge's reply.** Any reply that still cannot be parsed counts as unsupported.

## Passed

1. No unverified quote, check, or safety step reaches the final output. The policy drops 11 cases' worth of rejected citations.
2. Abstention under missing evidence is 20 of 20.
3. Every quote the AI cited appears on the cited page (deterministic pass rate 1.000).
4. The cost per diagnosis is under $0.002.

## Failed

1. The verified accuracy for naming the fault is low, at 0.174 overall. The main cause is manual coverage, not the model.
2. The AI does not recognize building operations faults (0 of 11).
3. The AI abstains on 55% of real cases, which is too often for a service desk.

## Not verified

1. Bedrock Guardrails on the diagnosis call.
2. The Bedrock Knowledge Base on S3 Vectors. The same embeddings are used, but the index was local.
3. Whether a manual set with sensor, valve, and controls manuals would lower the abstention rate.

## Design choices and their baselines

| Choice | Baseline | Outcome |
|---|---|---|
| The LLM proposes the cause from sensor evidence | The rule hint | It survives. It is more accurate in 3 of 4 segments (0.402 against 0.326 overall), but it loses on lab RTU.csv operations faults. |
| LLM citation selection, then deterministic and entailment checks | The BM25 best sentence | It survives. Citation support is 0.804 against 0.122. |
| Abstaining when no verified citation exists | Always answering | It survives. 20 of 20 withheld-evidence probes abstain, and no unverified procedure is shown. |

## Proposals for your approval

1. **Add 2 to 4 public manuals for the components with no coverage,** such as a duct temperature sensor, a hot water or chilled water control valve actuator, and a BAS controller. Then re-run Gate 2. This is the change most likely to cut the 38 abstentions for missing components. Each manual must be public and logged in `data/SOURCES.md`, and I stop and ask if one cannot be found.
2. **Treat operations faults separately.** When the rules or the proposal point to a building schedule or envelope problem, send the case to operations review with no technician dispatch. This matches the Gate 1 decision.
3. **Then proceed to Gate 3** (work orders and dispatch).
