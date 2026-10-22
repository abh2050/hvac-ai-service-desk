"""Rules baseline: deterministic fault rules evaluated per minute and persisted per window.

Each rule returns (applicable, violated) per minute. A rule fires for a window when it was
applicable for at least MIN_APPLICABLE operating minutes and violated in at least the
configured persistence fraction of those minutes. Each rule names the fault type it points to,
which the console shows next to the model result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_APPLICABLE = 10

# rule id -> (description, fault type hint)
RULES = {
    "A1": ("Heating mode: supply air not warmer than mixed air", "heating_valve_stuck"),
    "A2": ("Heating valve fully open but supply air below setpoint", "heating_valve_stuck"),
    "A3": ("Economizer mode: supply air warmer than return air", "oa_damper_stuck"),
    "A4h": ("Coils off: supply air warmer than mixed air plus fan heat", "heating_valve_leak"),
    "A4c": ("Coils off: supply air cooler than mixed air", "cooling_valve_leak"),
    "A5": ("100% outdoor air mode: mixed air differs from outdoor air", "oa_damper_stuck"),
    "A6": ("Cooling mode: supply air warmer than mixed air plus fan heat", "cooling_valve_stuck"),
    "A7": ("Minimum outdoor air mode: outdoor air fraction differs from damper command", "oa_damper_leak"),
    "A8": ("Heating and cooling valves open together", "heating_valve_stuck"),
    "A9": ("Cooling valve fully open but supply air above setpoint", "cooling_valve_stuck"),
    "E1": ("Economizer enabled and supply air above setpoint, damper at minimum", "economizer_setpoint_incorrect"),
    "E2": ("Economizer disabled (OAT above changeover), damper above minimum", "economizer_setpoint_incorrect"),
    "E3": ("Measured outdoor air fraction differs from damper command", "oa_damper_stuck"),
    "E4": ("Supply air sensor differs from VAV discharge air (reheat off)", "sa_temp_sensor_bias"),
    "E5": ("Damper command fixed above minimum for the whole window", "oa_damper_stuck"),
    "F1": ("High load hour with circuit 1 running and circuit 2 off", "compressor_stage2_not_engaging"),
    "F2": ("Running circuits: suction pressure imbalance", "refrigerant_undercharge"),
    "F3": ("High discharge to suction pressure ratio", "condenser_fouling"),
}


def _ahu(m: pd.DataFrame, c: dict) -> dict[str, tuple[pd.Series, pd.Series]]:
    closed, opened = c["valve_closed"], c["valve_open"]
    eps, fh = c["eps_t"], c["fan_heat"]
    htg_on, clg_on = m.htg > closed, m.clg > closed
    heating = htg_on & ~clg_on
    coils_off = ~htg_on & ~clg_on
    cooling = clg_on & ~htg_on
    full_oa = cooling & (m.dmpr >= c["damper_open"])
    min_oa = cooling & (m.dmpr <= c["min_oa_damper"])
    sat_err = np.where(m.sat < m.sp_lo, m.sat - m.sp_lo, np.where(m.sat > m.sp_hi, m.sat - m.sp_hi, 0.0))
    gap = m.oat - m.rat
    oaf = ((m.mat - m.rat) / gap).where(gap.abs() >= c["min_oat_rat_gap"])
    return {
        "A1": (heating, m.sat < m.mat + fh - eps),
        "A2": (heating & (m.htg >= opened), pd.Series(sat_err < -eps, index=m.index)),
        "A3": (coils_off & (m.dmpr > c["min_oa_damper"]), m.sat > m.rat + eps),
        "A4h": (coils_off, m.sat > m.mat + fh + eps),
        "A4c": (coils_off, m.sat < m.mat - eps),
        "A5": (full_oa, (m.oat - m.mat).abs() > eps),
        "A6": (cooling, m.sat > m.mat + fh + eps),
        "A7": (min_oa & oaf.notna(), (oaf - m.dmpr).abs() > c["eps_f"]),
        "A8": (pd.Series(True, index=m.index), htg_on & clg_on),
        "A9": (m.clg >= opened, pd.Series(sat_err > eps, index=m.index)),
    }


def _econ(m: pd.DataFrame, c: dict) -> dict[str, tuple[pd.Series, pd.Series]]:
    band = c["changeover_band"]
    enabled = (m.oat < c["econ_changeover_oat"] - band) & (m.mat > c["econ_min_mat"])
    disabled = m.oat > c["econ_changeover_oat"] + band
    at_min = m.dmpr <= c["min_damper_pct"] + 2
    gap = m.oat - m.rat
    oaf = ((m.mat - m.rat) / gap).where(gap.abs() >= c["min_oat_rat_gap"])
    # Damper command that never moves inside the window, above the documented 10% minimum.
    win = m.ts.dt.floor("60min")
    fixed = m.dmpr.groupby(win).transform(lambda s: s.max() - s.min()) < 0.5
    return {
        "E1": (enabled & (m.sat > c["sat_setpoint"] + c["sat_tolerance"]), at_min),
        "E2": (disabled, m.dmpr > c["min_damper_pct"] + c["excess_damper_margin_pct"]),
        "E3": (oaf.notna(), (oaf - m.dmpr / 100.0).abs() > c["oaf_tolerance"]),
        "E4": (m.vav_sat.notna() & m.sat.notna(), (m.sat - m.vav_sat).abs() > c["sat_vs_vav_tolerance"]),
        "E5": (m.dmpr.notna(), fixed & ~at_min),
    }


def _refrig(m: pd.DataFrame, c: dict) -> dict[str, tuple[pd.Series, pd.Series]]:
    on1 = (m.pd1 - m.ps1) > c["circuit_on_lift_bar"]
    on2 = (m.pd2 - m.ps2) > c["circuit_on_lift_bar"]
    high_load = np.where(m.oat.notna(), m.oat > c["stage2_high_load_oat_c"], m.rat > c["stage2_high_load_rat_c"])
    high_load = pd.Series(high_load, index=m.index)
    ratio = np.minimum(m.ps1, m.ps2) / np.maximum(m.ps1, m.ps2)
    pr = np.maximum((m.pd1 / m.ps1).where(on1, 0), (m.pd2 / m.ps2).where(on2, 0))
    return {
        "F1": (on1 & high_load, ~on2),
        "F2": (on1 & on2, ratio < c["suction_imbalance_ratio"]),
        "F3": (on1 | on2, pr > c["high_pressure_ratio"]),
    }


FAMILY_RULES = {"ahu": (_ahu, "ahu_apar"), "econ": (_econ, "rtu_economizer"), "refrig": (_refrig, "rtu_refrigerant")}


def evaluate(m: pd.DataFrame, family: str, cfg: dict) -> pd.DataFrame:
    """Return one row per operating window: fired rule ids, alarm flag, and a fault type hint."""
    fn, key = FAMILY_RULES[family]
    minutes, persist = cfg["window_minutes"], cfg["alarm_persistence_fraction"]
    rules = fn(m, cfg[key])
    win = m.ts.dt.floor(f"{minutes}min")
    run = m.fan_on.astype(bool)
    rows = {}
    for rid, (applicable, violated) in rules.items():
        a = (applicable.fillna(False).astype(bool) & run)
        v = (a & violated.fillna(False).astype(bool))
        n_a = a.groupby(win).sum()
        n_v = v.groupby(win).sum()
        rows[rid] = (n_a >= MIN_APPLICABLE) & (n_v >= persist * n_a)
    fired = pd.DataFrame(rows)
    fan_frac = run.groupby(win).mean()
    fired = fired[fan_frac >= cfg["operating_fraction_min"]]
    out = pd.DataFrame(index=fired.index)
    out["rules_fired"] = fired.apply(lambda r: ",".join(k for k, v in r.items() if v), axis=1)
    out["rule_alarm"] = fired.any(axis=1)
    out["rule_hint"] = fired.apply(
        lambda r: next((RULES[k][1] for k, v in r.items() if v), ""), axis=1)
    out.index.name = "window_start"
    return out.reset_index()
