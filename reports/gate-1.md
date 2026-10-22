# Gate 1: detection

Run 2, 2026-10-22, on code at commit `2c97944` plus the run 2 rule correction. Machine-readable results are in `reports/gate-1.json`. Per-window predictions are in `reports/gate-1-windows.csv.gz`. Run 1 and both rule files are kept in `reports/gate-1-runs/`.

## Summary

The model does not beat the rules baseline overall. The model finds more lab AHU faults than the rules, but it also raises more false alarms. On the economizer RTU and on the field RTUs, the rules win. Both methods raise too many false alarms for unattended production use: 0.5 to 1.9 alarm events per unfaulted operating day. Following rule 5 of the spec, we recommend the rules as the primary detector for RTUs. The AHU model is kept as a second opinion, and every disagreement goes to manager review.

## Method

- **Data.** We used the Release 1 episodes in `data/episodes.csv`: lab AHU, ORNL lab economizer RTU, lab RTU.csv, and field RTUs. Simulated data is excluded.
- **Windows.** We used 60-minute windows, and a window counts only when the fan runs for at least half of it. The run produced 6,424 windows.
- **Labels.** Labels come from the LBNL inventory tables. As approved at Gate 0, days with a label conflict are not scored. Operations faults (lighting, setback, infiltration, thermostat bias) are reported in their own category.
- **Rules baseline.** `services/detection/rules.py` with `config/rules.yaml`.
  - AHU: an APAR subset (House et al., 2001).
  - ORNL RTU: economizer checks.
  - Refrigerant RTUs: circuit balance, pressure ratio, and stage 2 checks.
- **Model.** One XGBoost classifier per equipment family on hourly physics residuals, from `services/detection/features.py` and `pipelines/training/train_detector.py`. Hyperparameters were fixed before the first run.
- **Split.** We split by episode, never by adjacent windows.
  - Lab data uses 5-fold StratifiedGroupKFold with the episode as the group (seed 7).
  - Field data is a cross-domain test: the refrigerant model trains on lab RTU.csv and runs unchanged on the field files.
- **Scoring unit: the operating day.**
  - A day is flagged when at least 2 windows alarm.
  - Recall is the share of faulted days that were flagged.
  - Precision is the share of flagged days that were faulted.
  - False alarms are counted as alarm events (runs of consecutive alarm windows) per unfaulted operating day.
  - The model alarms at probability 0.5 or higher.
- **Where it ran.** Everything ran on local CPU, and run 2 took about 24 seconds. The SageMaker training job has not run yet, because creating AWS resources still needs approval. The SageMaker entry point is the same script.

## Results (measured; ground truth is the LBNL labels)

### Lab data

| Segment | Method | Recall | Precision | False alarm events per unfaulted operating day | Unfaulted days flagged | Faulted days |
|---|---|---|---|---|---|---|
| Lab AHU | Rules | 0.739 | 0.680 | 1.333 | 8 of 15 | 23 |
| Lab AHU | Model | **0.957** | **0.710** | 1.933 | 9 of 15 | 23 |
| Lab economizer RTU (ORNL) | Rules | **1.000** | **0.857** | **1.643** | 8 of 14 | 48 |
| Lab economizer RTU (ORNL) | Model | 0.958 | 0.767 | 1.857 | 14 of 14 | 48 |
| Lab RTU.csv | Rules | 0.077 | n/a | n/a | no scorable day | 13 |
| Lab RTU.csv | Model | 1.000 | n/a | n/a | no scorable day | 13 |

The lab RTU.csv row has no valid comparison. Its 7 unfaulted days all carry a label conflict, so none is scored. The model also alarms on 80% of those unscored unfaulted windows, so its 1.000 recall shows no skill.

### Field data (cross-domain test)

| Segment | Method | Recall | Precision | False alarm events per unfaulted operating day | Unfaulted days flagged | Faulted days |
|---|---|---|---|---|---|---|
| Field RTUs (2 sites) | Rules | **0.648** | **0.401** | **0.476** | 88 of 231 | 91 |
| Field RTUs (2 sites) | Model | 0.187 | 0.212 | 0.628 | 63 of 231 | 91 |

The field results rest on 2 faulted episodes, one per site.

### Recall by fault type

| Segment | Fault type | Days | Rules | Model |
|---|---|---|---|---|
| Lab AHU | cooling valve leak | 3 | 0.667 | 1.000 |
| Lab AHU | cooling valve stuck | 4 | 1.000 | 1.000 |
| Lab AHU | heating valve leak | 5 | 0.600 | 0.800 |
| Lab AHU | heating valve stuck | 5 | 1.000 | 1.000 |
| Lab AHU | OA damper leak | 2 | 0.000 | 1.000 |
| Lab AHU | OA damper stuck | 4 | 0.750 | 1.000 |
| Lab economizer RTU | economizer setpoint incorrect | 16 | 1.000 | 1.000 |
| Lab economizer RTU | OA damper stuck | 16 | 1.000 | 0.875 |
| Lab economizer RTU | supply air sensor bias | 16 | 1.000 | 1.000 |
| Field RTU, site 1 | compressor stage 2 not engaging | 62 | 0.726 | 0.000 |
| Field RTU, site 2 | refrigerant undercharge (40%) | 29 | 0.483 | 0.586 |
| Lab RTU.csv | condenser fouling | 2 | 0.500 | 1.000 |
| Lab RTU.csv | operations faults (8 types) | 11 | 0.000 | 1.000 |

Fault types with 1 to 5 days give anecdotal recall values only. The rule's fault-type hint matched the LBNL fault type on 51.7% of flagged faulted windows.

### Window-level ranking quality of the model (AUC, scored windows)

The model's AUC is 0.826 on lab AHU data, 0.552 on lab economizer data, and 0.609 on field data. Below about 0.6, the model ranks windows close to chance.

## What changed between run 1 and run 2

Run 1 used an economizer high limit of 65 °F, and its rule E5 treated the "correct economizer setpoint of 10 °C (50 °F)" as a supply air target. Section E1.2 of the LBNL RTU inventory says something different. The economizer is enabled when outdoor air is below 50 °F and mixed air is above 45 °F, the supply air setpoint is 55 °F, and the damper minimum is 10%.

Run 2 corrects rules E1, E2, and E5 and two economizer model features to match that documentation. No AHU or refrigerant threshold changed. On economizer data, the rules went from flagging 14 of 14 unfaulted days (precision 0.774) to 8 of 14 (precision 0.857). The correction came from reading the documentation, not from tuning on results, but we report both runs because the change happened after run 1 results existed.

## Passed

1. The split is by episode in every segment, and no window from a test episode trains its own model.
2. Rules and model are both scored on the same days with the same scoring rule.
3. Lab, field, and simulated results are kept apart. No simulated data was used.
4. Every number in this report comes from `reports/gate-1.json` (run 2) or `reports/gate-1-runs/run1-gate-1.json`.

## Failed

1. **The AI path does not beat the baseline on RTUs.** The rules win on the economizer RTU and on the field RTUs.
2. **False alarm rates are too high for production.** They range from 0.476 (field rules) to 1.933 (lab AHU model) alarm events per unfaulted operating day.
3. **The lab-trained refrigerant model does not transfer to field units.** It missed every stage 2 fault day (recall 0.000).
4. **The rules miss every lab operations fault.** Lighting and setback faults leave little trace in RTU sensor points.

## Not verified

1. The SageMaker training job and the Lambda that serves the model. Both need approval to create AWS resources.
2. Per-type results for types with 1 to 5 days.
3. Whether the rule thresholds suit the field units. Rules F2 and F3 cause most field false alarms (352 and 394 alarm windows on unfaulted days). The field units' refrigerant and gauge conventions are not documented.

## Design choices and their baselines

| Choice | Baseline | Outcome |
|---|---|---|
| XGBoost on hourly physics residuals | APAR and economizer rules | It survives only for lab AHU data, as a second opinion with higher recall. Rules are primary elsewhere. |
| Episode-grouped cross-validation | A random window split | We kept it, because a window split would leak adjacent minutes into training and overstate results. |
| A field cross-domain test | Training on field data | We kept it, as approved. It shows that the lab-trained model does not transfer. |
| Day-level scoring with 2 alarm windows | Window-level scoring | We kept it, because a dispatcher acts per day per unit. Window AUC is also reported. |

## Proposals for your approval before Gate 2

1. **Detector policy.**
   - Use the rules as the primary detector for RTUs.
   - Run the rules and the model on AHUs. When both alarm, the case proceeds. When they disagree, the case goes to manager review, as policy 2 requires.
   - Show the model's probability as the detection confidence.
2. **A per-unit calibration run (Gate 1 run 3, optional).** Each unit would get alarm thresholds from its own fault-free training episodes, before any test day is scored. This is standard commissioning practice and should cut false alarms. It needs a new, pre-registered run. It does not change Gates 2 to 4, so it can follow later.
3. **The SageMaker training job.** Run `pipelines/training/train_detector.py` as a SageMaker script-mode job on `ml.m5.large`. The estimated cost is under $0.05. It needs an IAM role and the data bucket, so it depends on the CDK bootstrap and the foundation deploy.
