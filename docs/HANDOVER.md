# Handover: Uptime Desk, Gate 6

Written 2026-10-23 for the next coding agent (Codex). Read this file, `AGENTS.md`, and `.claude/skills/{brag,showcase}/SKILL.md` before starting.

## Where the project stands

- Gates 0 to 5 are done and approved by the owner. Each has `reports/gate-N.md` and `reports/gate-N.json`.
- The permanent public demo is **https://uptime-desk.vercel.app**. It is a static build: no sign-in, no backend.
  - It reads real API responses captured from one live run (`run-20261023211728-9a7178`) in `app/static-demo/snapshot/`.
  - The snapshot was captured with `pipelines/deploy/snapshot_demo.py`.
  - Vercel is connected to GitHub `main`. The root `vercel.json` runs `scripts/build-static-demo.sh`, so every push to `main` redeploys the site.
  - Run `node app/e2e/static-smoke.mjs` with `BASE=https://uptime-desk.vercel.app` after any change. The site must stay working.
- The AWS stacks (UptimeDesk-Foundation, UptimeDesk-Demo, Amplify app du00v4uwlekbh) are still up for the owner's hiring-manager week.
  - They will be torn down afterward. The owner runs the teardown.
  - The README must link the Vercel demo, not the Amplify URL.
- Repo: https://github.com/abh2050/hvac-ai-service-desk. It is public, so scan every push for secrets.

## Gate 6: what is left

1. **Diagrams (mostly done).** `diagrams/build_diagrams.py` writes 12 draw.io files. `scripts/export-diagrams.sh` exports PNG and SVG with the draw.io desktop CLI.
   - Visually checked and good: aws-architecture, network, case-state-machine, mcp-sequence, replay-sequence.
   - Not yet viewed after the last export: knowledge-base, security, system-context, fault-flow, data-model, deployment, observability.
   - Open each PNG and fix overlaps the same way. Use explicit `points=[...]` routes through gaps between icons. Keep labels off lines with the edge `label_dy` argument and the badge `at` argument.
   - The owner wants many AWS diagrams, because they show cloud depth. Keep all 12.
2. **README.md (not started; the current one is a stub).**
   - Required content: a 30-second summary, the Vercel demo link near the top, all diagrams, the gate scorecards (AI against baseline, including the gates the baseline won), the three result categories, the existing limitations section (keep it), run instructions, and a link to the showcase site.
   - The owner asked that it "really shine" for a hiring manager.
3. **docs/copilot.md (Release 3, not built).** Document how a Copilot Studio agent would call the API through a custom connector. State that it is planned and not built.
4. **Brag video.** Follow `.claude/skills/brag/SKILL.md`.
   - Narration uses ElevenLabs. The key is in SSM at `/uptime-desk/elevenlabs/api-key` (profile `awsnew`, region `us-east-2`). Never write it to disk or git.
   - Footage:
     - `reports/gate-5-e2e/artifacts-run2-colchester/.../video.webm` is 106 s of a real live run at 1080p;
     - the owner's screen recordings are `docs/Screen Recording 2026-10-23 at *.mov` (gitignored);
     - the Vercel static demo can be captured at 1920x1080 with Playwright.
   - Output goes to `video/out/`. Keep the MP4s out of git, or use a GitHub release.
5. **Showcase site.** Follow `.claude/skills/showcase/SKILL.md`. It produces `docs/index.html` and `docs/media/` for GitHub Pages.
   - Higgsfield is connected as an MCP connector in Claude. Its credentials are also in SSM at `/uptime-desk/higgsfield/credentials`.
   - Check the balance and report the storyboard cost to the owner **before** generating anything.
   - The owner wants it to impress a hiring manager.
6. **Close Gate 6.** Write `reports/gate-6.md` and `reports/gate-6.json`, commit, push, and stop for owner approval.
7. **After the owner's demo week:** they run `scripts/demo-down.sh`. Then measure idle cost in Cost Explorer for the gate-5 "idle cost" line, which is still marked not measured.

## Facts to use (all from reports/, with their category)

Every number in docs, the video, or the site needs its source and category: ground truth, measured, or not validated. Lab, field, and simulated results stay separate. Dispatch numbers are scenario model results.

- **Gate 1, detection** (`gate-1.json`, measured against LBNL ground-truth labels):

  | Equipment | Model recall | Rules recall |
  |---|---|---|
  | lab AHU | 0.957 | 0.739 |
  | lab econ | 0.958 | 1.0 (the rules win) |
  | field RTU | 0.187 | 0.648 (the rules win) |

  False alarms run 0.5 to 1.9 per unfaulted operating day. Rules are the primary detector, and disagreement goes to manager review.
- **Gate 2, diagnosis** (`gate-2.json`, run 3, 92 cases):

  | Measure | AI | Baseline |
  |---|---|---|
  | Verified fault type | 0.293 | 0.043 (keyword baseline) |
  | Proposal | 0.424 | 0.326 (rule hint; difference not significant, p 0.078) |
  | Citation support | 0.88 | 0.122 |

  On 60 held-out field days (`gate-2-holdout.json`): fault type 0.75, citation support 0.915.
- **Gate 3, dispatch** (`gate-3.json`, scenario model, 37 jobs):

  | Method | Total lateness | Late jobs |
  |---|---|---|
  | OR-Tools | 402 min | 4 |
  | Nearest qualified | 1343 min | 10 |
  | Earliest available | 402 min | 4 |

  Travel was 974, 853 and 1268 min respectively. Constraint violations were 0, and 10 of 10 policy tests passed.
- **Gate 4, assistant** (`gate-4.json`, 30 questions): accuracy 0.9, adversarial tests 12 of 12, unauthorized reads 0, p50 4.12 s, $0.00097 per question.
- **Gate 5, hosted** (`gate-5.json`):
  - The full flow passed 8 of 10 times. The 2 failures were blocked for "no sourced lockout step".
  - Median 39.4 s to a drafted work order and 77.3 s to dispatch.
  - Model cost averaged $0.00206 per incident.
  - The MCP checks passed.

## Rules (from the owner; they override defaults)

- **Writing:**
  - No em or en dashes in prose.
  - None of these words: delve, crucial, pivotal, robust, seamless, landscape, realm, tapestry, foundational, unlock; and no leverage or harness as verbs.
  - No emojis.
  - Never invent a metric.
- **AWS:** use profile `awsnew` and region `us-east-2` only. Use `~/.local/bin/aws`, because `/usr/local/bin/aws` is a broken Intel build. Never run `cdk deploy` or `cdk destroy`, or delete resources, without showing the diff and getting approval. The owner runs the teardown.
- **Spend:** write content yourself instead of calling paid model APIs. Ask before any spend over a few dollars.
- **Secrets:** they live only in SSM. Never print them or commit them.
- **Commits:** commit at gate boundaries. Stop after Gate 6 for approval.

## Useful commands

```
python3 diagrams/build_diagrams.py && scripts/export-diagrams.sh   # diagrams
scripts/build-static-demo.sh                                       # static demo into build/vercel/uptime-desk
BASE=https://uptime-desk.vercel.app node app/e2e/static-smoke.mjs  # check the live demo (run from app/)
.venv/bin/python -m pytest -q tests                                # unit tests (local Postgres: docker container uptime-pg, port 54329)
```
