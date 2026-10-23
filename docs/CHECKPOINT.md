# Checkpoint: 2026-10-23, Gate 2 in progress

## Done
- Gate 0 (setup) and Gate 1 (detection) are committed with reports in `reports/`.
- Owner decisions:
  - The region is us-east-2.
  - Interface endpoints are always on.
  - Bedrock models: gpt-oss-120b for diagnosis, gpt-oss-20b for entailment. GPT Luna is not available to this account.
  - The detector trains locally (no SageMaker).
  - Rules are the primary detector. The model runs beside them, and disagreement goes to manager review.
- The AWS account verification hold is cleared. Bedrock quotas returned to default on 2026-10-23.

## Gate 2 state
- The manual page chunks (616) are built: `pipelines/training/manual_pages.py`.
- The Titan v2 embedding of the chunks was running at checkpoint time: `pipelines/training/embed_manuals.py`. It is resumable from `data/processed/manual_vectors.cache.json` and limited to 55 requests per minute.
- Case set: 92 flagged fault days plus 20 evidence-withheld probes, in `data/processed/gate2_cases.jsonl`, built by `pipelines/evaluation/gate2_cases.py`.
- Code is written but has not been run yet:
  - diagnosis: `services/diagnosis/diagnose.py`
  - verifier: `services/citation_verifier/verify.py`
  - policy: `services/diagnosis/policy.py`
  - evaluation runner: `pipelines/evaluation/gate2_diagnosis.py`

## Resume
1. If `data/processed/manual_vectors.npy` is missing, run `.venv/bin/python -I pipelines/training/embed_manuals.py`.
2. Run a smoke test with `.venv/bin/python -I pipelines/evaluation/gate2_diagnosis.py --limit 3`. It writes `reports/gate-2-smoke.json`, which is not reported.
3. Run the full evaluation with `.venv/bin/python -I pipelines/evaluation/gate2_diagnosis.py`. The estimated cost is under $1.
4. Write `reports/gate-2.md`, commit, and stop for approval.

## Open items for the owner
- The CDK bootstrap and deploy are blocked for the agent. The owner runs them or adds a permission rule.
- The $50 budget needs an alert email address.
- Disk space was about 4.6 GB free at Gate 0.
