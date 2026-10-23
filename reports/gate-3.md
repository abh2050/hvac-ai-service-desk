# Gate 3: work orders and dispatch

Run on 2026-10-23. The results are in `reports/gate-3.json`. Every work order, assignment, and runner-up is in `reports/gate-3-detail.json`. The code is `pipelines/evaluation/gate3_dispatch.py`, `services/api/workorders.py`, `services/dispatch/`, and `tests/test_policies.py`.

## Summary

Deterministic code drafted 89 work orders from the Gate 2 diagnoses.
- 100% of them have every required field.
- They contain 0 unsourced instructions. The database schema also refuses to store one.
- All 10 decision policy branches pass their tests against a local Postgres 16 container.

In dispatch, OR-Tools reached the lowest weighted cost on every scenario. On the 5 daily scenarios it tied earliest-available on SLA lateness (402 minutes each). It cut travel from 1,268 to 974 minutes and cost 4.5% less in weighted terms. Against nearest-qualified, it cut lateness from 1,343 to 402 minutes. On the surge day it cut lateness by 54% (921 against 1,993 minutes). All dispatch numbers are scenario model results, not field savings.

## Work orders (measured)

| Measure | Value |
|---|---|
| Gate 2 cases in | 92 |
| Routed to manual review before diagnosis (policy 1) | 3 |
| Flagged for manager review because rules and model disagree (policy 2) | 24 |
| Work orders drafted | 89 |
| Required field validity | 1.000 |
| Unsourced instructions | **0** |
| Blocked: insufficient evidence (policy 3) | 31 |
| Blocked: no sourced lockout step (policy 6) | 20 |
| Draft, technician route | 37 |
| Draft, operations review | 1 |

Every instruction is a verbatim manual quote that passed the Gate 2 verifier, with its manual and page. The `work_order_steps` table enforces `CHECK (verified)`. A test confirms that inserting an unverified step fails.

## Decision policy tests (11 of 11 passed)

The tests ran against the local Postgres container. Fixtures are recorded outputs: Gate 2 diagnoses, LBNL cases, and manual page text. Policy 4 replaces the entailment model with a fixed stub, so the test exercises the deterministic logic alone.

| Policy | Test | Result |
|---|---|---|
| 1. Low detection confidence goes to manual review | `test_policy1_low_confidence_goes_to_manual_review` | passed |
| 2. Rules and model disagree, so manager review | `test_policy2_disagreement_requires_manager_review` | passed |
| 3. No supported passage gives insufficient evidence | `test_policy3_no_supported_passage_abstains` | passed |
| 4. A citation passes only with page text and entailment | `test_policy4_citation_needs_page_text_and_entailment` | passed |
| 5. A manual for another model gives compatibility uncertain | `test_policy5_class_match_flags_compatibility` | passed |
| 6. An unsourced safety step blocks approval | `test_policy6_unsourced_lockout_blocks_approval` | passed |
| 7. No qualified technician escalates unassigned with the reason | `test_policy7_no_qualified_technician_escalates` | passed |
| 8. No feasible plan returns the reason and requests rescheduling | `test_policy8_no_feasible_plan_requests_reschedule` | passed |
| 9. Approval expiry escalates and blocks dispatch | `test_policy9_expired_approval_escalates` | passed |
| 10. Reading another technician's job is denied and audited | `test_policy10_other_technicians_job_denied_and_audited` | passed |
| Schema refuses an unverified instruction | `test_db_rejects_unverified_instruction` | passed |

## Dispatch (scenario model results)

### Scenario construction

- **Jobs.** The 37 technician work orders in draft are approved 15 minutes after creation. This is a stated assumption.
- **Days.** Cases are spread round-robin over Monday 2026-10-26 to Friday 2026-10-30. Each case keeps the hour of its first recorded alarm. Each day is planned separately over a 24-hour horizon. A surge scenario puts all 37 jobs on Monday.
- **Hard constraints, the same for all three methods.** These are certifications (EPA 608 Universal covers Type II), site access, escort clearance, shift windows, and site allowed hours.
- **Travel model.** Straight-line distance from the technician's home base to the site at 40 km/h, with no road correction. Each visit starts from home base, and return travel is not counted.
- **SLA.** SLA lateness is measured on arrival against the site's response time (4 hours critical, 8 hours high, 24 hours standard).
- **Weighted cost.** It is the objective in `config/dispatch.yaml`: 10 × lateness minutes + 1 × travel minutes + 0.5 × maximum technician workload minutes. It is computed the same way for all three methods.
- **Independent check.** A validator re-checks every assignment from every method against eligibility, time windows, and per-technician overlap.

### Daily scenarios (5 days, 37 jobs)

| Method | Assigned | Rescheduled | Escalated | SLA lateness (min) | Late jobs | Travel (min) | Mean daily max workload (min) | Weighted cost | Constraint violations |
|---|---|---|---|---|---|---|---|---|---|
| OR-Tools CP-SAT (optimal every day) | 34 | 3 | 0 | **402** | **4** | 974 | 358.4 | **5,890** | 0 |
| Nearest qualified | 34 | 3 | 0 | 1,343 | 10 | **853** | 421.6 | 15,337 | 0 |
| Earliest available | 34 | 3 | 0 | **402** | **4** | 1,268 | **350.8** | 6,165 | 0 |

### Surge scenario (all 37 jobs on Monday)

| Method | Assigned | Rescheduled | SLA lateness (min) | Late jobs | Travel (min) | Max workload (min) | Weighted cost |
|---|---|---|---|---|---|---|---|
| OR-Tools CP-SAT (optimal) | **17** | 20 | **921** | **6** | 675 | 560 | **10,165** |
| Nearest qualified | 16 | 21 | 2,129 | 10 | **627** | **546** | 22,190 |
| Earliest available | 16 | 21 | 1,993 | 10 | 675 | 560 | 20,885 |

The surge is limited by capacity. Few technicians on Monday's shifts hold both the certifications and the site clearance that these jobs need, so every method requests rescheduling for about 20 jobs. The weighted cost excludes the unassigned job penalty. OR-Tools assigned one more job than the baselines.

### Seeded surge days (10 days; added at the owner's request)

A single surge day is one sample, so we ran 10 seeded surge days. Each seed:
- picks the weekday, which changes who is on shift;
- shuffles the recorded alarm hours across the 37 jobs;
- seeds the CP-SAT search.

Values are the mean, with the range in parentheses.

| Method | Assigned | Rescheduled | Escalated | SLA lateness (min) | Late jobs | Travel (min) | Max workload (min) | Weighted cost |
|---|---|---|---|---|---|---|---|---|
| OR-Tools CP-SAT | **20.0** (19 to 24) | **16.8** (12 to 18) | **0.2** (0 to 1) | **1,083** (486 to 2,241) | **5.6** (4 to 11) | 695.4 (665 to 745) | 534 (486 to 546) | **11,792** (5,798 to 23,379) |
| Nearest qualified | 18.7 (17 to 22) | 17.8 (13 to 20) | 0.5 (0 to 3) | 2,137 (1,412 to 4,377) | 9.2 (7 to 14) | 683.9 (661 to 726) | 530.9 (486 to 546) | 22,316 (15,058 to 44,720) |
| Earliest available | 18.8 (17 to 23) | 17.7 (12 to 20) | 0.5 (0 to 3) | 1,938 (1,294 to 3,674) | 8.7 (7 to 14) | **675.7** (579 to 790) | 530.9 (486 to 546) | 20,324 (13,820 to 37,618) |

- OR-Tools had the lowest weighted cost on 10 of 10 surge days.
- It reached proven optimality on 8 days. On the 2 Friday surges it stopped at the 10-second limit with a feasible but unproven plan.
- Every method had 0 constraint violations on every day.
- An escalation means no technician qualified. This happens when the seeded day has no technician on shift with the needed certifications and clearance.

## Passed

1. Required field validity is 1.000 and there are 0 unsourced instructions.
2. All 10 policy branches pass their tests against Postgres.
3. OR-Tools has the lowest weighted cost on the daily scenarios and on 10 of 10 seeded surge days, with 0 constraint violations.
4. Every daily solve reached proven optimality in under a second.

## Failed or limited

1. On the daily scenarios, OR-Tools gains only 4.5% over earliest-available, because the load is light. A simple greedy rule is close enough on a normal day.
2. Nearest-qualified travels the least (853 minutes) but runs 1,343 minutes late. Minimizing travel alone hurts the SLA.
3. 51 of 89 work orders are blocked: 31 for insufficient evidence and 20 for a missing lockout source. Most of these trace back to the Gate 2 manual coverage gaps.

## Defects found and fixed in this gate

The independent validator found 10 OR-Tools assignments that broke the constraints in the first evaluation run. The cause was work order IDs built from the asset and the creation minute. Cases on the same asset at the same scenario hour collided, which overwrote the one-assignment-per-job constraint. All numbers above come from the run after the fix. The faulty run was never reported.

The fix left these safeguards behind, as the owner requested:
1. Work order IDs now include a hash of the case ID, and the evaluation asserts that they are unique.
2. Every planner (OR-Tools and both baselines) raises an error on duplicate job IDs.
3. `work_orders.work_order_id` is the primary key, so the database rejects a duplicate.
4. `tests/test_duplicate_ids.py` holds 6 regression tests:
   - same asset, same minute gives distinct IDs;
   - each planner rejects duplicates (3 tests);
   - a job is never assigned twice;
   - the database rejects a duplicate ID.

All 19 tests in `tests/` pass against the local Postgres container.

## Not verified

1. Dispatch on real road travel times. Straight-line distance at 40 km/h underestimates urban travel.
2. A Step Functions task token with a timeout for approval. Policy 9 is tested in code, and the Step Functions version arrives with the deploy in Gate 5.
3. Aurora itself. The tests ran on Postgres 16 with the same schema.

## Design choices and their baselines

| Choice | Baseline | Outcome |
|---|---|---|
| OR-Tools CP-SAT with a weighted objective | Nearest qualified; earliest available | It survives. It has the lowest weighted cost: 5,890 against 6,165 and 15,337 daily, and a mean of 11,792 against 20,324 and 22,316 over 10 surge days. On light days, earliest-available is close and would be acceptable. |
| Instructions only as verified quotes, enforced in the schema | Free-text instructions | It survives: 0 unsourced instructions, and the database rejects unverified steps. |
| Rules as the primary detector, with disagreement sent to review | Model only | It survives the Gate 1 results. 24 of 92 cases get flagged for manager review. |
