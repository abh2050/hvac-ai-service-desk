# Uptime Desk explainer

Voice: Matilda, ElevenLabs premade voice `XrExE9yKIg1WjnnlVkGX`.

## Scene 1, hook, 0:00 to 0:12

An air handler starts drifting in a critical building. The alarm is easy. The hard question is what failed, which instructions are safe, and who can reach it before the service window closes.

## Scene 2, problem, 0:12 to 0:25

Sensor trends sit in one system. Equipment manuals sit in another. Dispatch rules live in spreadsheets and experience. Each handoff creates another place for evidence or time to disappear.

## Scene 3, architecture, 0:25 to 0:50

Uptime Desk joins that path on AWS. Recorded LBNL data streams through Kinesis. Rules stay primary while XGBoost supplies a second opinion. Bedrock proposes a diagnosis from manual pages, then a second model verifies each quotation. PostgreSQL rejects unverified steps. Step Functions waits for a manager, then OR-Tools assigns a qualified technician. Cognito and the MCP gateway bind requests to a verified identity.

## Scene 4, live demo, 0:50 to 1:35

The manager launches a recorded field scenario and watches each stage complete. The diagnosis shows rules, model, and disagreement. Every accepted check opens the source manual at the cited page. The manager keeps control: approve the draft, remove an optional step, or reject it with a reason. Approval resumes the case machine. The dispatch board shows the selected technician, a runner-up, travel, lateness, and rationale. The assistant can list that technician's jobs and answer from verified passages. A request for another technician's order is denied and audited. A passing hosted run reached a draft in a median 39.4 seconds and dispatch in 77.3. If the case has no sourced lockout step, the pipeline stops. In the hosted batch, that policy blocked 2 of 10 runs instead of sending unsupported work.

## Scene 5, results, 1:35 to 1:52

The measured results keep their boundaries. On lab air handlers, model recall was 0.957 against 0.739 for rules. Rules won on the lab economizer and field RTU. Citation support was 0.880 against 0.122. In the dispatch scenario, OR-Tools cut lateness from 1,343 to 402 minutes against nearest qualified, while earliest available also reached 402.

## Scene 6, close, 1:52 to 2:00

Explore the recorded demo, inspect every gate report on GitHub, and see the rest of Abhishek Shah's work in the linked portfolio.
