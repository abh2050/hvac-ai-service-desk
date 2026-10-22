# Gate 0: setup

Run date: 2026-10-22. Machine-readable results are in `reports/gate-0.json`.

## Summary

The repo skeleton, data downloads, source register, episode index, seed configuration, CDK scaffold, and profile scripts are in place. Nothing has been deployed. The CDK bootstrap and the budget are prepared but not run, because both create resources and need your approval.

## Region change

The spec says us-west-2. Read-only calls with profile `awsnew` showed that the organization's service control policy denies Lambda, RDS, Kinesis, Step Functions, S3 Vectors, Bedrock Knowledge Bases, Guardrails, AgentCore, SageMaker, ECS, Cognito, Amplify, and Polly in us-west-2 and in us-east-1. All of them respond in us-east-2. The project uses us-east-2.

## Passed

1. The repo layout matches the spec. `.claude/skills/brag/SKILL.md` holds the spec skill, with step 3 changed to ElevenLabs narration at your request.
2. Downloads finished, and all 99 files pass `shasum -a 256 -c data/checksums.sha256`. The Figshare files also matched their published MD5 values.
3. `data/SOURCES.md` records the URL, download date, license note, and SHA256 for each source, plus the manual compatibility table.
4. The field-measured RTU data exists. The LBNL zip holds 4 field files from 2 Connecticut sites.
5. Brick models exist for the ORNL lab RTU and the simulated RTU. No Brick model exists for the field RTUs or the Figshare AHUs.
6. `data/episodes.csv` lists 150 episodes. Of these, 123 are in Release 1 (119 lab, 4 field), and 27 simulated files are held for Release 2.
7. Seed configuration is written in `config/` with a configuration header. It holds 16 technicians, 5 sites, 7 assets, dispatch weights, and policy thresholds.
8. `npx cdk synth` succeeds for both the idle and the demo profile. `npx tsc --noEmit` passes.
9. `cdk diff` for `UptimeDesk-Foundation` lists 30 new resources and no NAT gateway. The full diff is in `reports/gate-0-cdk-diff-foundation.txt`.
10. `shellcheck` passes on all five scripts.

## Failed or blocked

1. **The Claude model agreement is not accepted in this account.** Bedrock reports `agreementAvailability: NOT_AVAILABLE`, and the Anthropic use-case form has not been submitted. Gate 2 cannot call Claude until you submit the form in the Bedrock console (Model access, us-east-2).
2. **No exact manual match exists for any Release 1 unit.** LBNL names the lab RTU (Trane YCD150) but does not name the maker of any AHU or field RTU. All five manuals are class matches. As a result, every Release 1 diagnosis will carry "compatibility uncertain" under policy 5. This is a true limit of public data, and we will report it as such.
3. The general Trane CSAA air handler manual (CLCH-SVX07R) returned HTTP 404. We used the gas heat CSAA manual, which covers fewer of the AHU valve faults.

## Not verified yet

1. Whether Claude, Titan, S3 Vectors, and AgentCore work end to end in us-east-2. The list calls succeed, but no resource has been created.
2. Whether Amplify Gen 2 hosting works under the SCP. It uses CloudFront, a global service.
3. Real idle cost. The estimate is $33 to $35 per month, based on 4 interface endpoints in 1 AZ at $7.30 each plus storage. Gate 5 measures it from Cost Explorer.
4. Polly generative voices. None are listed for en-US in us-east-2. This no longer matters, because narration moved to ElevenLabs.

## Data findings that shape Gate 1

1. **Label conflicts.** We keep the published labels, and 16 Release 1 rows carry a `label_conflict` note. In RTU.csv, the ground truth flag is 1 on every day, including the 7 days that the inventory lists as unfaulted. In MZVAV-2-1.csv, the inventory lists 2007-08-30 as a 2.0 GPM heating valve leak, but the flag is 0. Gate 1 will state one scoring rule for these days. The proposed rule: use the inventory table for the fault type, and exclude days with conflicting labels from scoring.
2. **The field set is small.** The field set holds 2 faulted episodes (a stage 2 compressor fault over about 2 months, and a 40% undercharge over 1 month) and 2 unfaulted baselines. An episode-level train and test split inside the field data leaves too little to learn from. The proposed approach: train on lab data, test on field data, and report field results as a cross-domain test with the episode count stated.
3. **Fault types with few episodes.** Several lab fault types have 1 or 2 episodes, such as condenser fouling (2) and the lighting and setback faults (1 each). An episode-level split cannot put every type in both train and test. Gate 1 will report per-type results only where the test set holds the type.
4. **Faults that are not equipment faults.** Five RTU.csv fault types are building operation faults, not HVAC equipment faults: lighting setback errors, excessive infiltration, and missing setbacks. A technician dispatch does not fix them. The proposal: detect them but route them to "operations review", not to a work order.

## Design choices and their baselines

| Choice | Simpler baseline | Why the choice survived |
|---|---|---|
| Interface endpoints in 1 AZ, no NAT | NAT gateway (about $33 per month plus data charges, 1 AZ) | You chose in-VPC Lambdas with endpoints that are always on. Four endpoints in 1 AZ cost about the same as one NAT gateway, but they keep traffic private and add no per-GB NAT charge. The RDS Data API option (about $3 to $5 idle) was offered and declined. |
| Replay and detection Lambdas outside the VPC | Everything in the VPC | They never touch Aurora, so they need no endpoints. That avoids a Kinesis endpoint ($7.30 per month). |
| Fargate optimizer in a public subnet with a public IP and no inbound rules | Fargate in an isolated subnet with ECR and Logs endpoints | It avoids 3 more endpoints ($21.90 per month). The public IP costs about $0.005 per hour, and only while a task runs. |
| One provisioned Kinesis shard in the demo profile only | On-demand stream | One shard costs about $0.015 per hour. demo-down destroys it, so idle cost is $0. |
| Budget scoped to the `project=uptime-desk` tag | Account-wide budget | Your account already has a $20 account-wide budget. A tag-scoped budget tracks this project only. |

## Actions waiting for your approval

1. **CDK bootstrap.** Command: `cd infra && npx cdk bootstrap aws://054772656600/us-east-2 --profile awsnew`. It creates the `CDKToolkit` stack: a staging S3 bucket, an ECR repository, 5 IAM roles, and one SSM parameter. Cost is near $0 per month until assets are stored.
2. **Budget.** Run `BUDGET_EMAIL=<your address> scripts/create-budget.sh`. It creates `uptime-desk-monthly` at $50 per month with alerts at 80% actual and 100% forecast. It is scoped to the tag `project=uptime-desk`. Activate `project` as a cost allocation tag in the Billing console, or the filtered budget reads $0. Your existing $20 account budget is left as is, but the expected idle cost will exceed it.
3. **Claude model access.** Submit the Anthropic use-case form in the Bedrock console for us-east-2.
4. The **Gate 1 scoring rules** for label conflicts, the field cross-domain test, and operation faults, as listed above.

## Files written in this gate

`.gitignore`, `pyproject.toml`, `uv.lock`, `.claude/skills/brag/SKILL.md`, `data/SOURCES.md`, `data/checksums.sha256`, `data/episodes.csv`, `pipelines/build_episodes.py`, `config/{sites,technicians,dispatch,policy}.yaml`, `infra/` (CDK app, foundation and demo stacks), `scripts/{lib,demo-up,demo-down,teardown,create-budget}.sh`, `docs/ai-region-preferences.md`, `reports/gate-0.{md,json}`, and `reports/gate-0-cdk-diff-foundation.txt`.
