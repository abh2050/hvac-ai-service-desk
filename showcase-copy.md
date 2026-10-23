# Uptime Desk showcase copy

This file fixes the page story before any Higgsfield media generation. Every measured number links to its gate report. The opening scene is illustrative and does not claim a customer deployment.

## Hero

# Uptime Desk

Uptime Desk helps an HVAC service manager turn a recorded sensor fault into a cited work order, a human decision, and a qualified dispatch.

Buttons: `View the source` and `Follow the incident`

## Scene

At 5:40 a.m., a facilities service manager stands beside an air handler while the building is still quiet. A supply-air trend has started to drift, but the alarm does not name the failed part or the safe service steps. The manager checks a trend on one screen, searches a manual on another, and compares the call with a dispatch sheet. The maintenance window keeps shrinking while each source tells only part of the story. A technician can move only after the manager can explain the fault, support the work with the right manual passage, and confirm that the assigned person has the required access and certification.

*This scenario is illustrative. The system evaluation uses recorded public LBNL data, not a live customer building.*

## Before

The sensor trend shows that something changed, but it does not carry the manual page needed for a safe repair. The manager has to match equipment context by hand, which consumes the same response window needed for the repair.

A plausible diagnosis can still contain an unsupported service step. If the source passage disappears during a handoff, the approver cannot tell which instruction came from the manual and which came from assumption.

The dispatch sheet adds another decision. A nearby technician may lack the required certification, site access, shift coverage, or time before the service window closes. A rushed assignment can move the problem without resolving it.

## After: the illustrated walkthrough

### 1. Replay the evidence

The manager starts a recorded LBNL fault day. Uptime Desk preserves the episode, asset, timestamp, and source rows so the rest of the workflow can be replayed and audited.

### 2. Detect the disagreement

Deterministic HVAC rules remain the primary detector. An XGBoost model supplies a second opinion, and the console shows both signals. A disagreement goes to manager review instead of becoming an automatic conclusion.

### 3. Build a cited diagnosis

Bedrock retrieves relevant manual pages and proposes a fault with quoted evidence. A second model checks whether each quotation supports its claim, and a literal page check confirms that the quotation exists in the source. The database rejects any unverified work-order step.

### 4. Keep the manager in control

Step Functions pauses on the draft. The manager can approve it, remove an optional step, or reject it with a reason. A case without a sourced lockout or disconnect step remains blocked.

### 5. Dispatch within policy

OR-Tools evaluates certification, shift, site access, travel, and SLA constraints. The dispatch board shows the selected technician, a runner-up, expected travel, lateness, and the reason for the choice.

### 6. Limit the assistant to assigned work

The technician assistant can read that technician's assigned jobs and verified manual passages. The MCP gateway replaces caller-supplied identity with claims from the verified token. A request for another technician's work is denied and audited.

## Why it matters

The evaluation keeps lab, field, and scenario results separate. The model reached 0.957 recall on the lab air handlers, while rules reached 0.739. Rules won on the lab economizer at 1.000 against 0.958 and on the field RTU at 0.648 against 0.187. The diagnosis run reached 0.880 citation support against a 0.122 keyword baseline. In the dispatch scenario, OR-Tools reduced total lateness from 1,343 to 402 minutes against nearest qualified, while earliest available also reached 402 minutes. These are measured evaluation and scenario results. They do not claim field savings. Sources: [Gate 1](reports/gate-1.json), [Gate 2](reports/gate-2.json), and [Gate 3](reports/gate-3.json).

## Workflow

Recorded sensor rows enter the replay. Rules and XGBoost score each operating window. A case opens only when the policy allows it. Retrieval supplies manual passages. Diagnosis proposes a fault. Verification checks every quotation. The database accepts only verified steps. The manager decides whether work can continue. OR-Tools then creates a policy-compliant dispatch, and the technician assistant exposes only authorized job context.

The human decision node stays visually distinct because approval is the boundary between a draft and dispatched work.

## Feedback loop

Each replay keeps the source rows, detector outputs, diagnosis, citations, manager action, dispatch result, assistant calls, and denied requests. Gate scripts score those artifacts against ground truth and fixed policy tests. A future release can use reviewed errors to improve retrieval, routing, and evaluation. Release 1 does not retrain from production outcomes.

## Technical deep dive

### Architecture

The deployment runs in AWS `us-east-2`. API Gateway and Cognito protect the manager and technician paths. Kinesis carries replayed sensor rows. Lambda performs replay, detection, diagnosis, verification, and MCP checks. Step Functions keeps the case state and waits for approval. Bedrock supplies diagnosis and entailment models. A Knowledge Base retrieves passages from S3 vectors. Aurora PostgreSQL stores cases, citations, work orders, assignments, and audit records. OR-Tools runs in an ECS Fargate task. CloudWatch records metrics and alarms. The VPC has no NAT gateway. Private traffic uses four interface endpoints and one S3 gateway endpoint.

### Data

Release 1 uses 123 public LBNL episodes: 119 lab episodes and 4 field files from 2 Connecticut sites. Another 27 simulated files remain held for Release 2. Preparation scripts normalize timestamps, operating windows, fault labels, asset families, and manual metadata. Raw source files stay outside git. The public manuals match equipment classes rather than exact units, so every diagnosis carries a compatibility warning.

### Models and agents

Deterministic rules remain the primary detector. Local XGBoost provides the second detector. `openai.gpt-oss-120b-1:0` proposes diagnoses on Amazon Bedrock. `openai.gpt-oss-20b-1:0` checks entailment. Titan Text Embeddings v2 and S3 Vectors support retrieval. OR-Tools CP-SAT solves the dispatch scenario. MCP handlers expose job, asset, manual, and audit tools through AgentCore Gateway.

### Evaluation

Gate 1 compares detector outputs with published LBNL labels. Gate 2 scores 92 diagnosis cases and a frozen pipeline on 60 unused field days. Gate 3 compares OR-Tools with nearest-qualified and earliest-available baselines across 37 scenario jobs. Gate 4 tests the technician assistant with written, adversarial, and authorization cases. Gate 5 runs the hosted workflow from replay through dispatch.

The weak results remain visible. Rules beat XGBoost on the lab economizer and field RTU. The model identified 0 of 11 building-operations fault cases. The lab AHU slice produced no verified diagnoses because the public manual set lacks the required coil-valve service documents. The model's lead over the rule hint for proposed fault type was not statistically significant.

### Performance and cost

The hosted Gate 5 batch passed 8 of 10 runs. The other 2 runs stopped because the case had no sourced lockout step. Replay to work-order draft took a median 39.4 seconds, and replay to dispatch took a median 77.3 seconds. Diagnosis and entailment averaged $0.00206 in model cost per incident. Infrastructure cost per incident was not isolated. The technician assistant measured p50 latency of 4.12 seconds, p95 latency of 9.05 seconds, and model cost of $0.00097 per question. Sources: [Gate 4](reports/gate-4.json) and [Gate 5](reports/gate-5.json).

### Guardrails and failure modes

Cognito JWT validation protects the API. Separate IAM roles scope each Lambda to named resources. The gateway discards caller-supplied identity. Literal page checks and a second-model entailment check protect citations. A PostgreSQL constraint blocks unverified work-order steps. The case machine blocks approval without a sourced lockout or disconnect step. Every denied request enters the audit log and emits a metric. A manager remains the only actor who can approve, edit, or reject a draft.

### Deployment

AWS CDK defines the foundation and demo profiles in TypeScript. The foundation contains the API, identity, database, retrieval, storage, and observability resources. The demo profile adds replay, detection, case orchestration, and the Fargate dispatch task. The permanent Vercel demo is a static build from GitHub `main` and never calls the AWS backend.

### Run it yourself

1. Clone the repository and run `uv sync`.
2. Start PostgreSQL on port `54329` with the command in the README.
3. Run `.venv/bin/python -m pytest -q tests`.
4. Run `npm ci`, `npm run lint`, and `npm run build` in `app/`.
5. Run `npm ci`, `npm run build`, `npx cdk synth --profile awsnew`, and `npx cdk diff --profile awsnew` in `infra/`.
6. Open [the permanent recorded demo](https://uptime-desk.vercel.app) for a backend-free walkthrough.

## What I would build next

- Add exact equipment manuals and coil-valve service documents, then score a new episode-level holdout.
- Train a separate router for building-operations faults before any equipment diagnosis or dispatch.
- Replace straight-line travel with road travel time and live technician location constraints.
- Make mixed assistant questions resolve the user's assigned job before manual search.

## Close

The manager returns to the same air handler with the full decision trail on one screen. The recorded incident now carries its source rows, verified manual passages, approval, dispatch rationale, and audit events. The result is a work order that another operator can inspect from alarm to assignment.

## About the builder

Abhishek Shah built Uptime Desk as an evidence-backed AWS service workflow. View more work at [abh2050.github.io/abhishek-shah-portfolio](https://abh2050.github.io/abhishek-shah-portfolio/) and the source at [github.com/abh2050](https://github.com/abh2050).
