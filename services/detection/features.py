"""Canonical sensor frames and hourly window features for the three equipment families.

The same code runs in training (pipelines/) and in the detection Lambda, so a replayed
minute of data turns into exactly the features the model saw during training.

Families:
  ahu      Figshare lab AHUs (MZVAV-2-1, SZCAV, SZVAV). Degrees F, signals as 0..1.
  econ     ORNL FRP RTU with economizer (LBNL RTU zip, ORNL_RTU/). Degrees F, damper in %.
  refrig   RTUs with refrigerant circuit sensors: Figshare RTU.csv (psi, F) and the field
           RTUs (bar, C). Both are converted to bar and C.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PSI_TO_BAR = 0.0689476


def f_to_c(x):
    return (x - 32.0) / 1.8


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce") if col in df else pd.Series(np.nan, index=df.index)


def canonical(raw: pd.DataFrame, family: str, source: str) -> pd.DataFrame:
    """Map one raw LBNL file to the family's canonical minute columns."""
    raw = raw.rename(columns=lambda c: c.strip())
    ts = pd.to_datetime(raw.iloc[:, 0])
    if family == "ahu":
        sp = _num(raw, "AHU: Supply Air Temperature Set Point")
        out = pd.DataFrame({
            "sat": _num(raw, "AHU: Supply Air Temperature"),
            "sp_lo": _num(raw, "AHU: Supply Air Temperature Heating Set Point").fillna(sp),
            "sp_hi": _num(raw, "AHU: Supply Air Temperature Cooling Set Point").fillna(sp),
            "oat": _num(raw, "AHU: Outdoor Air Temperature"),
            "mat": _num(raw, "AHU: Mixed Air Temperature"),
            "rat": _num(raw, "AHU: Return Air Temperature"),
            "fan_on": _num(raw, "AHU: Supply Air Fan Status") > 0.5,
            "dmpr": _num(raw, "AHU: Outdoor Air Damper Control Signal"),
            "clg": _num(raw, "AHU: Cooling Coil Valve Control Signal"),
            "htg": _num(raw, "AHU: Heating Coil Valve Control Signal"),
        })
    elif family == "econ":
        vav_sat = raw.filter(like="VAV_RM_SAT_").apply(pd.to_numeric, errors="coerce")
        vav_w = raw.filter(like="VAV_RM_WATT_").apply(pd.to_numeric, errors="coerce")
        no_reheat = vav_sat.where(vav_w.values < 50.0)
        zone = raw.filter(like="TERM_RM_TEMP_").drop(columns=["TERM_RM_TEMP_CSPT", "TERM_RM_TEMP_HSPT"], errors="ignore")
        out = pd.DataFrame({
            "sat": _num(raw, "RTU_SA_TEMP"),
            "oat": _num(raw, "RTU_OA_TEMP"),
            "mat": _num(raw, "RTU_MA_TEMP"),
            "rat": _num(raw, "RTU_RA_TEMP"),
            "fan_on": _num(raw, "RTU_SA_FAN_WATT") > 100.0,
            "dmpr": _num(raw, "RTU_OA_DMPR_DM"),
            "comp1_w": _num(raw, "RTU_COMP_WATT_1"),
            "comp2_w": _num(raw, "RTU_COMP_WATT_2"),
            "vav_sat": no_reheat.mean(axis=1),
            "zone_t": zone.apply(pd.to_numeric, errors="coerce").mean(axis=1),
            "csp": _num(raw, "TERM_RM_TEMP_CSPT"),
            "occ": _num(raw, "OCCU_MOD"),
        })
    elif family == "refrig":
        if source == "lab":  # Figshare RTU.csv: psi and degrees F
            g = lambda c: _num(raw, f"RTU: {c}")
            out = pd.DataFrame({
                "sat": f_to_c(g("Supply Air Temperature")),
                "rat": f_to_c(g("Return Air Temperature")),
                "oat": np.nan,
                "fan_on": g("Supply Air Fan Status") > 0.5,
                "pd1": g("Circuit 1 Discharge Pressure") * PSI_TO_BAR,
                "ps1": g("Circuit 1 Suction Pressure") * PSI_TO_BAR,
                "pd2": g("Circuit 2 Discharge Pressure") * PSI_TO_BAR,
                "ps2": g("Circuit 2 Suction Pressure") * PSI_TO_BAR,
                "td1": f_to_c(g("Circuit 1 Discharge Temperature")),
                "tsuc1": f_to_c(g("Circuit 1 Suction Temperature")),
                "td2": f_to_c(g("Circuit 2 Discharge Temperature")),
                "tsuc2": f_to_c(g("Circuit 2 Suction Temperature")),
            })
        else:  # field RTUs: bar and degrees C
            out = pd.DataFrame({
                "sat": _num(raw, "RTU_SA_TEMP"),
                "rat": _num(raw, "RTU_RA_TEMP"),
                "oat": _num(raw, "RTU_OA_TEMP"),
                "fan_on": _num(raw, "RTU_SA_FAN_WATT") > 100.0,
                "pd1": _num(raw, "RTU_REFG_DISC_PRES_1"),
                "ps1": _num(raw, "RTU_REFG_SUCT_PRES_1"),
                "pd2": _num(raw, "RTU_REFG_DISC_PRES_2"),
                "ps2": _num(raw, "RTU_REFG_SUCT_PRES_2"),
                "td1": _num(raw, "RTU_REFG_DISC_TEMP_1"),
                "tsuc1": _num(raw, "RTU_REFG_SUCT_TEMP_1"),
                "td2": _num(raw, "RTU_REFG_DISC_TEMP_2"),
                "tsuc2": _num(raw, "RTU_REFG_SUCT_TEMP_2"),
            })
    else:
        raise ValueError(f"unknown family {family}")
    out.insert(0, "ts", ts)
    return out


def _oaf(mat, rat, oat, min_gap):
    gap = oat - rat
    return ((mat - rat) / gap).where(gap.abs() >= min_gap).clip(-0.5, 1.5)


def minute_derived(m: pd.DataFrame, family: str, cfg: dict) -> pd.DataFrame:
    """Physics residuals per minute. Relative quantities keep weather and unit size out of the model."""
    d = pd.DataFrame({"ts": m.ts, "fan_on": m.fan_on})
    if family == "ahu":
        c = cfg["ahu_apar"]
        d["sat_err"] = np.where(m.sat < m.sp_lo, m.sat - m.sp_lo, np.where(m.sat > m.sp_hi, m.sat - m.sp_hi, 0.0))
        d["coil_dt"] = m.sat - m.mat
        d["oaf_err"] = _oaf(m.mat, m.rat, m.oat, c["min_oat_rat_gap"]) - m.dmpr
        d["mat_minus_mix"] = m.mat - (m.dmpr * m.oat + (1 - m.dmpr) * m.rat)
        d["dmpr"], d["clg"], d["htg"] = m.dmpr, m.clg, m.htg
        d["heat_closed"] = d.coil_dt.where(m.htg <= c["valve_closed"])
        d["cool_closed"] = (-d.coil_dt).where(m.clg <= c["valve_closed"])
        d["simul"] = ((m.htg > c["valve_closed"]) & (m.clg > c["valve_closed"])).astype(float)
    elif family == "econ":
        c = cfg["rtu_economizer"]
        d["oaf_err"] = _oaf(m.mat, m.rat, m.oat, c["min_oat_rat_gap"]) - m.dmpr / 100.0
        d["sat_minus_vav"] = m.sat - m.vav_sat
        d["dmpr"] = m.dmpr
        d["econ_enabled"] = ((m.oat < c["econ_changeover_oat"]) & (m.mat > c["econ_min_mat"])).astype(float)
        d["comp_on"] = ((m.comp1_w > 500) | (m.comp2_w > 500)).astype(float)
        d["mat_minus_oat"] = m.mat - m.oat
        d["mat_minus_rat"] = m.mat - m.rat
        d["sat_err"] = m.sat - c["sat_setpoint"]
        d["oat_minus_changeover"] = m.oat - c["econ_changeover_oat"]
        d["zone_minus_csp"] = m.zone_t - m.csp
        d["oat"] = m.oat
    else:
        c = cfg["rtu_refrigerant"]
        lift1, lift2 = m.pd1 - m.ps1, m.pd2 - m.ps2
        on1, on2 = lift1 > c["circuit_on_lift_bar"], lift2 > c["circuit_on_lift_bar"]
        both = on1 & on2
        d["on1"], d["on2"] = on1.astype(float), on2.astype(float)
        d["pr1"] = (m.pd1 / m.ps1).where(on1)
        d["pr2"] = (m.pd2 / m.ps2).where(on2)
        d["suct_ratio"] = (np.minimum(m.ps1, m.ps2) / np.maximum(m.ps1, m.ps2)).where(both)
        d["disc_ratio"] = (np.minimum(m.pd1, m.pd2) / np.maximum(m.pd1, m.pd2)).where(both)
        d["dt_suct_1"] = (m.td1 - m.tsuc1).where(on1)
        d["dt_suct_2"] = (m.td2 - m.tsuc2).where(on2)
        d["air_dt"] = (m.rat - m.sat).where(on1 | on2)
        d["rat"], d["oat"] = m.rat, m.oat
    return d


def hourly_windows(d: pd.DataFrame, minutes: int, operating_min: float) -> pd.DataFrame:
    """Aggregate per-minute residuals to fixed windows; keep windows where the fan mostly runs."""
    key = d.ts.dt.floor(f"{minutes}min")
    run = d[d.fan_on]
    num = run.drop(columns=["ts", "fan_on"])
    agg = num.groupby(key[d.fan_on]).agg(["mean", "std"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    frac = d.groupby(key).fan_on.mean().rename("fan_frac")
    w = agg.join(frac, how="right")
    w = w[w.fan_frac >= operating_min].copy()
    w.index.name = "window_start"
    return w.reset_index()
