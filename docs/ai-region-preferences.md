# AWS region preferences (paste into ChatGPT and Claude memory)

Copy the block below into ChatGPT (Settings, Personalization, Memory or Custom instructions) and into Claude (claude.ai project instructions or `~/.claude/CLAUDE.md`).

```text
AWS defaults for all of my projects (checked 2026-10-22):
- Use AWS CLI profile "awsnew" (account 054772656600) and region us-east-2 for every regional AWS service.
- My AWS Organization's service control policy denies regional services in us-west-2 and us-east-1. Lambda, RDS/Aurora, Kinesis, Step Functions, S3 Vectors, Bedrock Knowledge Bases, Guardrails, AgentCore, SageMaker, ECS/Fargate, Cognito, Amplify, and Polly were all denied in those two regions and all worked in us-east-2.
- Global services such as IAM, Budgets, and Cost Explorer work normally.
- If a spec, template, or tutorial names another region, use us-east-2 instead and tell me you changed it.
- For Claude on Bedrock, use the "us." or "global." cross-region inference profiles. Discover model IDs with "aws bedrock list-inference-profiles --region us-east-2" instead of hardcoding them. Check that the Anthropic model agreement is accepted before relying on Claude.
- Amazon Polly has no generative en-US voices in us-east-2. Use a neural voice or ElevenLabs.
- Credentials expire. When a call fails with an expired session, ask me to run "aws login" and then continue with "--profile awsnew".
```
