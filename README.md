# Uptime Desk

Uptime Desk is an AI service desk for HVAC maintenance in buildings that cannot go down. It detects equipment faults in recorded building sensor data and drafts a diagnosis that cites the equipment manuals. It then drafts a work order for a manager to approve and assigns a qualified technician. Deterministic code checks every citation, approval, and assignment.

The full README, the diagrams, and the run instructions arrive in Gate 6. The gate reports in `reports/` hold every result.

## Result categories

- **Ground truth** means the published LBNL fault labels.
- **Measured** means detection accuracy, citation support, latency, cost, and computed optimizer results.
- **Not validated** means downtime avoided, field visits saved, and dollar savings. This project claims none of these.

Lab, field, and simulated results are always reported separately. All dispatch numbers are scenario model results, not field savings.

## Limitations

1. **Building operations faults go undetected by the diagnosis step.** The lab RTU.csv data has 11 operations fault cases, such as lighting schedule errors, setback errors, and infiltration. The AI proposed an equipment fault for all 11 and identified 0 of them (`reports/gate-2.json`, run 3, `operations_routing`). The pipeline still routes an operations proposal to operations review when no equipment rule fired. It never dispatches a technician for one.
2. **No manual covers the coil valves of the lab air handlers.** The public manual set has no hot water or chilled water coil valve service manual. The added Honeywell document covers the valve actuator only. Lab AHU diagnoses therefore abstain on 82.6% of cases and produce 0 verified answers (`reports/gate-2.json`, run 3, `by_family`).
3. **No manual matches any unit exactly.** LBNL does not name the makers of the AHUs or the field RTUs. Every manual is a class match, so every diagnosis carries "compatibility uncertain" (`data/SOURCES.md`).
4. **The AI's lead over the rule hint is not statistically significant.** In naming the fault, the AI scored 0.424 (95% CI 0.328 to 0.526) and the rule hint 0.326 (0.239 to 0.427). That gives 15 against 6 discordant cases and an exact McNemar p of 0.078 (`reports/gate-2-stats.json`). The AI's lead in verified diagnoses over the keyword baseline is significant (0.293 against 0.043, p < 0.0001).
5. **The diagnosis prompt was chosen after seeing test results.** Run 3 was selected after runs 1 and 2 were scored on the same cases. Every lab episode was used in those runs, so no lab holdout exists. The frozen run 3 pipeline was scored once on 60 unused days of the 2 field episodes (`reports/gate-2-holdout.json`). These are unused days, not unused episodes.
6. **Field data is small.** The field set has 2 faulted episodes, one per site. Field results rest on those 2 units.
7. **Detection raises too many false alarms for unattended use.** Gate 1 measured 0.5 to 1.9 alarm events per unfaulted operating day (`reports/gate-1.json`).
8. **The travel model is simple.** Dispatch uses straight-line distance at 40 km/h from each technician's home base, with no road network.
