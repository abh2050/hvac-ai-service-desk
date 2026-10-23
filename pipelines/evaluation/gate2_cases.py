"""Build the Gate 2 diagnosis cases from recorded Gate 1 detections. No label reaches the prompt.

One case per scored faulted Release 1 day that the detector flagged (rules or model, >= 2 alarm
windows). Field episodes span weeks, so 4 evenly spaced flagged days are taken per field episode.
A seeded sample of 20 cases is duplicated as "evidence withheld" probes: their passages come from
an unrelated query, so the correct output is "insufficient_evidence".

Usage: .venv/bin/python -I pipelines/evaluation/gate2_cases.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
from detection.rules import RULES  # noqa: E402

FEATURES = {
    "ahu": {"sat_err_mean": "supply air temp error vs setpoint band (F)", "coil_dt_mean": "supply minus mixed air temp (F)",
            "oaf_err_mean": "measured outdoor air fraction minus damper command", "dmpr_mean": "OA damper command (0-1)",
            "clg_mean": "cooling valve command (0-1)", "htg_mean": "heating valve command (0-1)",
            "heat_closed_mean": "supply minus mixed air temp while heating valve closed (F)",
            "cool_closed_mean": "mixed minus supply air temp while cooling valve closed (F)",
            "simul_mean": "share of minutes with heating and cooling valves both open"},
    "econ": {"sat_err_mean": "supply air temp minus 55 F setpoint (F)", "oaf_err_mean": "measured OA fraction minus damper command",
             "dmpr_mean": "OA damper command (%)", "oat_mean": "outdoor air temp (F)",
             "sat_minus_vav_mean": "supply air sensor minus VAV discharge temps with reheat off (F)",
             "econ_enabled_mean": "share of minutes economizer should be enabled (OAT < 50 F)",
             "comp_on_mean": "share of minutes a compressor runs", "mat_minus_oat_mean": "mixed minus outdoor air temp (F)",
             "zone_minus_csp_mean": "zone temp minus cooling setpoint (F)"},
    "refrig": {"on1_mean": "share of minutes circuit 1 runs", "on2_mean": "share of minutes circuit 2 runs",
               "pr1_mean": "circuit 1 discharge/suction pressure ratio", "pr2_mean": "circuit 2 discharge/suction pressure ratio",
               "suct_ratio_mean": "lower/higher suction pressure when both circuits run",
               "dt_suct_1_mean": "circuit 1 discharge minus suction temp (C)", "dt_suct_2_mean": "circuit 2 discharge minus suction temp (C)",
               "air_dt_mean": "return minus supply air temp while cooling (C)", "oat_mean": "outdoor air temp (C)"},
}
N_FIELD_DAYS = 4
N_PROBES = 20


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config/rules.yaml").read_text())
    feats = pd.read_parquet(ROOT / "data/processed/windows.parquet")
    pred = pd.read_csv(ROOT / "reports/gate-1-windows.csv.gz", parse_dates=["window_start"])
    w = feats.merge(pred[["file", "window_start", "model_prob", "model_alarm"]], on=["file", "window_start"], how="left")
    w["rule_alarm"] = w.rule_alarm.fillna(False).astype(bool)
    w["model_alarm"] = w.model_alarm.fillna(False).astype(bool)
    min_win = cfg["day_alarm_min_windows"]

    cases = []
    faulted = w[w.scored & (w.is_fault == 1)]
    for (ep, day), g in faulted.groupby(["episode_id", "day"]):
        alarm = g[g.rule_alarm | g.model_alarm]
        if len(alarm) < min_win:
            continue
        fam = g.family.iloc[0]
        fired = alarm.rules_fired.fillna("").str.split(",").explode()
        fired = fired[fired != ""].value_counts()
        evidence = {desc: round(float(alarm[col].mean()), 3) for col, desc in FEATURES[fam].items()
                    if col in alarm and alarm[col].notna().any()}
        cases.append({
            "case_id": f"{g.unit.iloc[0]}|{day}",
            "episode_id": ep, "day": day, "family": fam,
            "equipment_class": "RTU" if fam != "ahu" else g.file.iloc[0].split("/")[-1].startswith("MZVAV") and "AHU-MZVAV"
            or ("AHU-SZCAV" if "SZCAV" in g.file.iloc[0] else "AHU-SZVAV"),
            "unit": g.unit.iloc[0], "source_type": g.source_type.iloc[0],
            "detection": {
                "rules_alarm_windows": int(alarm.rule_alarm.sum()),
                "model_alarm_windows": int(alarm.model_alarm.sum()),
                "operating_windows": int(len(g)),
                "rules_fired": [{"rule": r, "windows": int(n), "description": RULES[r][0]} for r, n in fired.items()],
                "rule_hint": alarm.rule_hint.replace("", pd.NA).dropna().mode().iloc[0]
                if alarm.rule_hint.replace("", pd.NA).notna().any() else None,
                "model_probability_mean": round(float(alarm.model_prob.mean()), 3),
            },
            "sensor_evidence": evidence,
            "label": {"fault_type": g.fault_type.iloc[0], "category": g.category.iloc[0]},
            "probe": None,
        })

    # Field episodes span weeks: keep N evenly spaced flagged days per episode.
    df = pd.DataFrame(cases)
    keep = []
    for ep, g in df.groupby("episode_id"):
        g = g.sort_values("day")
        if g.source_type.iloc[0] == "field" and len(g) > N_FIELD_DAYS:
            idx = [round(i * (len(g) - 1) / (N_FIELD_DAYS - 1)) for i in range(N_FIELD_DAYS)]
            g = g.iloc[sorted(set(idx))]
        keep.extend(g.to_dict("records"))

    rng = random.Random(7)
    probes = [dict(c, case_id=c["case_id"] + "|withheld", probe="evidence_withheld") for c in rng.sample(keep, N_PROBES)]
    out = keep + probes
    (ROOT / "data/processed/gate2_cases.jsonl").write_text("\n".join(json.dumps(c, default=str) for c in out))
    summary = pd.DataFrame(out).assign(kind=lambda d: d.probe.fillna("normal"))
    print(summary.groupby(["kind", "source_type", "family"]).size().to_string())
    print("faulted scored days not flagged (not diagnosed):",
          faulted.groupby(["episode_id", "day"]).ngroups - len(cases))


if __name__ == "__main__":
    main()
