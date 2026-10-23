"""Sensor evidence shown to the diagnosis model: hourly feature means with plain descriptions.

Shared by the Gate 2 case builder and the live pipeline so both build cases the same way.
"""

from __future__ import annotations

from collections import Counter

from detection.rules import RULES

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


def build_case(case_id: str, windows: list[dict], family: str, equipment_class: str, unit: str, source_type: str,
               day: str, min_windows: int) -> dict:
    """windows: operating windows with rule_alarm, model_alarm, rules_fired, rule_hint, model_prob, features."""
    alarm = [w for w in windows if w["rule_alarm"] or w["model_alarm"]]
    fired = Counter(r for w in alarm for r in (w.get("rules_fired") or "").split(",") if r)
    hints = Counter(w["rule_hint"] for w in alarm if w.get("rule_hint"))
    evidence = {}
    for col, desc in FEATURES[family].items():
        vals = [w["features"].get(col) for w in alarm if w["features"].get(col) is not None]
        if vals:
            evidence[desc] = round(sum(vals) / len(vals), 3)
    probs = [w["model_prob"] for w in alarm if w.get("model_prob") is not None]
    hours = sorted(int(str(w["window_start"])[11:13]) for w in windows)
    return {
        "case_id": case_id, "family": family, "equipment_class": equipment_class, "unit": unit,
        "source_type": source_type, "day": day,
        "flagged": len(alarm) >= min_windows,
        "detection": {
            "rules_alarm_windows": sum(1 for w in alarm if w["rule_alarm"]),
            "model_alarm_windows": sum(1 for w in alarm if w["model_alarm"]),
            "operating_windows": len(windows),
            "rules_fired": [{"rule": r, "windows": n, "description": RULES[r][0]} for r, n in fired.most_common()],
            "rule_hint": hints.most_common(1)[0][0] if hints else None,
            "model_probability_mean": round(sum(probs) / len(probs), 3) if probs else 0.0,
        },
        "sensor_evidence": evidence,
        "operating_pattern": {
            "first_operating_hour": hours[0] if hours else None, "last_operating_hour": hours[-1] if hours else None,
            "operating_hours": len(windows),
            "alarm_hours": sorted({int(str(w["window_start"])[11:13]) for w in alarm}),
        },
    }
