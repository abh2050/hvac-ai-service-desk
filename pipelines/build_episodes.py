"""Build data/episodes.csv: one row per recorded episode with its published LBNL label.

Labels are transcribed from the two LBNL inventory PDFs (page numbers given per table)
and cross-checked against the per-minute "Fault Detection Ground Truth" flag where a file
carries one. Disagreements are kept, not resolved: both values go into the output and
`label_conflict` is set.

Usage: .venv/bin/python -I pipelines/build_episodes.py data
"""

import sys
from pathlib import Path

import pandas as pd

FIGSHARE = "raw/figshare-ahu-rtu"
RTU_ZIP = "raw/lbnl-rtu-extracted"

# Figshare inventory (LBNLDataSynthesisInventory.pdf). (date, fault_type, intensity)
FIGSHARE_TABLES = {
    # Table 2-2 experimental, p.11-12. Drexel / ASHRAE RP-1312, ERS Ankeny Iowa, AHU-A.
    "MZVAV-2-1.csv": dict(
        unit="ERS-AHU-A", equipment_class="AHU-MZVAV", source_type="lab", table="Figshare inventory Table 2-2 p.11-12",
        rows=[("2007-08-28", "heating_valve_leak", "0.4 GPM"),
              ("2007-08-29", "heating_valve_leak", "1.0 GPM"),
              ("2007-08-30", "heating_valve_leak", "2.0 GPM")]
        + [(d, "unfaulted", "") for d in ["2008-08-19", "2008-08-25", "2008-09-04", "2009-01-19", "2009-02-16",
                                          "2009-02-17", "2009-05-03", "2009-05-04", "2009-05-05", "2009-05-06"]]),
    # Table 3-3, p.18. LBNL FLEXLAB X3A AHU in constant volume mode.
    "SZCAV.csv": dict(
        unit="FLEXLAB-X3A-AHU-CAV", equipment_class="AHU-SZCAV", source_type="lab", table="Figshare inventory Table 3-3 p.18",
        rows=[("2017-03-18", "oa_damper_stuck", "100% open"), ("2017-03-19", "oa_damper_stuck", "50% open"),
              ("2017-03-20", "oa_damper_leak", "20% of max flow"), ("2017-03-21", "oa_damper_leak", "50% of max flow"),
              ("2017-03-24", "heating_valve_stuck", "0% closed"), ("2017-03-25", "heating_valve_stuck", "100% open"),
              ("2017-03-26", "heating_valve_stuck", "50% open"), ("2017-03-22", "heating_valve_leak", "5% of max flow"),
              ("2017-03-23", "heating_valve_leak", "40% of max flow"), ("2017-03-11", "cooling_valve_stuck", "0% closed"),
              ("2017-03-12", "cooling_valve_stuck", "100% open"), ("2017-03-31", "cooling_valve_stuck", "50% open"),
              ("2017-03-15", "cooling_valve_leak", "5% of max flow"), ("2017-03-16", "cooling_valve_leak", "50% of max flow"),
              ("2017-04-01", "unfaulted", "")]),
    # Table 3-4, p.19. Same AHU in variable volume mode.
    "SZVAV.csv": dict(
        unit="FLEXLAB-X3A-AHU-VAV", equipment_class="AHU-SZVAV", source_type="lab", table="Figshare inventory Table 3-4 p.19",
        rows=[("2017-09-18", "oa_damper_stuck", "minimum position"), ("2017-09-19", "oa_damper_stuck", "100% open"),
              ("2017-09-14", "heating_valve_stuck", "100% open"), ("2017-09-15", "heating_valve_stuck", "50% open"),
              ("2017-09-12", "heating_valve_leak", "40% of max flow"), ("2017-09-22", "cooling_valve_stuck", "100% open"),
              ("2017-09-11", "cooling_valve_leak", "50% of max flow")]
        + [(d, "unfaulted", "") for d in ["2017-09-20", "2017-09-21", "2017-09-23", "2017-09-24"]]),
    # Table 4-3, p.24-25. Trane YCD150 12.5 ton RTU at ORNL FRP #2.
    # 2017-12-03 is listed both as a fault day and as unfaulted in the source table.
    "RTU.csv": dict(
        unit="ORNL-FRP2-RTU", equipment_class="RTU", source_type="lab", table="Figshare inventory Table 4-3 p.24-25",
        rows=[("2017-08-27", "condenser_fouling", "25% airflow reduction"),
              ("2017-08-29", "condenser_fouling", "50% airflow reduction"),
              ("2017-12-01", "hvac_setback_delayed_onset", "3 h"), ("2017-12-03", "hvac_setback_early_termination", "3 h"),
              ("2017-12-07", "excessive_infiltration", "+20%"), ("2017-12-14", "excessive_infiltration", "+40%"),
              ("2018-02-07", "lighting_setback_delayed_onset", "3 h"), ("2018-02-09", "lighting_setback_early_termination", "3 h"),
              ("2017-12-20", "no_overnight_hvac_setback", ""), ("2018-02-18", "no_overnight_lighting_setback", ""),
              ("2018-02-01", "thermostat_bias", "+4F core zone 103"), ("2018-01-31", "thermostat_bias", "-4F core zone 103"),
              ("2018-01-28", "thermostat_bias", "+4F perimeter zone 205"), ("2018-01-27", "thermostat_bias", "-4F perimeter zone 205")]
        + [(d, "unfaulted", "") for d in ["2017-09-01", "2017-11-30", "2017-12-03", "2017-12-09", "2017-12-24",
                                          "2018-02-04", "2018-02-05"]]),
    # Simulated files: listed for completeness, used only in a later release and always labeled simulated.
    "MZVAV-1.csv": dict(unit="PNNL-sim-MZVAV", equipment_class="AHU-MZVAV", source_type="simulated",
                        table="Figshare inventory Table 1-2", rows=None),
    "MZVAV-2-2.csv": dict(unit="ERS-AHU-A-sim", equipment_class="AHU-MZVAV", source_type="simulated",
                          table="Figshare inventory Table 2-2 (simulation)", rows=None),
}

# LBNL RTU inventory (LBNL_FDD_Data_Sets_RTU.pdf) Table E3 p.9-10: ORNL FRP lab, Trane YCD150, one-day faults.
ORNL_FAULTS = {"SA_temp_bias": "sa_temp_sensor_bias", "Inc_Eco_SP": "economizer_setpoint_incorrect",
               "OA_damper_stuck": "oa_damper_stuck", "ERTU": "unfaulted"}
# Table F2/F4 p.17-18: field RTUs in Connecticut, whole-file episodes.
FIELD = {"Site1_Staging_Fault.csv": ("compressor_stage2_not_engaging", "stage 2 will not engage", "Site1-Milford-7.5t"),
         "Site1_Unfaulted.csv": ("unfaulted", "", "Site1-Milford-7.5t"),
         "Site2_Undercharged40.csv": ("refrigerant_undercharge", "40% circuit B", "Site2-Colchester-10t"),
         "Site2_Unfaulted.csv": ("unfaulted", "", "Site2-Colchester-10t")}

GT = "Fault Detection Ground Truth"


def figshare_rows(root: Path) -> list[dict]:
    out = []
    for fname, meta in FIGSHARE_TABLES.items():
        if meta["rows"] is None:
            out.append(dict(file=f"{FIGSHARE}/{fname}", unit=meta["unit"], equipment_class=meta["equipment_class"],
                            source_type=meta["source_type"], start="", end="", fault_type="see source table",
                            intensity="", label_source=meta["table"], gt_flag="", label_conflict="", release=2))
            continue
        df = pd.read_csv(root / FIGSHARE / fname, usecols=lambda c: c in (GT, "Datetime", "Timestamp"))
        ts = pd.to_datetime(df.iloc[:, 0])
        flag_by_day = df.groupby(ts.dt.date)[GT].max()
        table_days = {}
        for day, fault, intensity in meta["rows"]:
            table_days.setdefault(day, []).append((fault, intensity))
        for day in sorted(set(table_days) | {str(d) for d in flag_by_day.index if flag_by_day.size}):
            entries = table_days.get(day, [("not in source table", "")])
            flag = flag_by_day.get(pd.Timestamp(day).date())
            if flag is None:
                continue
            faults = {f for f, _ in entries}
            table_faulted = any(f not in ("unfaulted", "not in source table") for f in faults)
            conflict = []
            if len(entries) > 1:
                conflict.append("day listed under more than one scenario")
            if "not in source table" in faults:
                conflict.append("day present in file but not in table")
            elif int(flag) != int(table_faulted):
                conflict.append(f"table says {'faulted' if table_faulted else 'unfaulted'}, flag says {int(flag)}")
            n_minutes = int((ts.dt.date == pd.Timestamp(day).date()).sum())
            if n_minutes < 60:
                conflict.append(f"only {n_minutes} rows (day boundary spill)")
            for fault, intensity in entries:
                out.append(dict(file=f"{FIGSHARE}/{fname}", unit=meta["unit"], equipment_class=meta["equipment_class"],
                                source_type=meta["source_type"], start=f"{day} 00:00", end=f"{day} 23:59",
                                fault_type=fault, intensity=intensity, label_source=meta["table"], gt_flag=int(flag),
                                label_conflict="; ".join(conflict), release=1))
    return out


def ornl_rows(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / RTU_ZIP / "ORNL_RTU").glob("*.csv")):
        stem = path.stem
        season = "_".join(stem.split("_")[-2:])
        body = stem[: -len(season) - 1]
        prefix = next(p for p in ORNL_FAULTS if body.startswith(p))
        intensity = body[len(prefix):].strip("_")
        ts = pd.to_datetime(pd.read_csv(path, usecols=[0]).iloc[:, 0])
        out.append(dict(file=str(path.relative_to(root)), unit="ORNL-FRP-RTU-YCD150", equipment_class="RTU",
                        source_type="lab", start=ts.min().strftime("%Y-%m-%d %H:%M"), end=ts.max().strftime("%Y-%m-%d %H:%M"),
                        fault_type=ORNL_FAULTS[prefix], intensity=intensity, label_source="LBNL RTU inventory Table E3 p.9-10",
                        gt_flag="", label_conflict="", release=1))
    return out


def field_rows(root: Path) -> list[dict]:
    out = []
    for fname, (fault, intensity, unit) in FIELD.items():
        path = root / RTU_ZIP / "Field RTU" / fname
        ts = pd.to_datetime(pd.read_csv(path, usecols=[0]).iloc[:, 0])
        out.append(dict(file=str(path.relative_to(root)), unit=unit, equipment_class="RTU", source_type="field",
                        start=ts.min().strftime("%Y-%m-%d %H:%M"), end=ts.max().strftime("%Y-%m-%d %H:%M"),
                        fault_type=fault, intensity=intensity, label_source="LBNL RTU inventory Table F4 p.18",
                        gt_flag="", label_conflict="", release=1))
    return out


def simulated_rtu_rows(root: Path) -> list[dict]:
    return [dict(file=str(p.relative_to(root)), unit="NREL-sim-Precedent-5t", equipment_class="RTU", source_type="simulated",
                 start="", end="", fault_type=p.stem.removeprefix("RTU_sim_"), intensity="",
                 label_source="LBNL RTU inventory Table S3", gt_flag="", label_conflict="", release=2)
            for p in sorted((root / RTU_ZIP / "Simulated RTU").glob("*.csv"))]


def main(root: Path) -> None:
    rows = figshare_rows(root) + ornl_rows(root) + field_rows(root) + simulated_rtu_rows(root)
    df = pd.DataFrame(rows)
    df.to_csv(root / "episodes.csv", index=False)
    r1 = df[df.release == 1]
    print(f"{len(df)} episodes, {len(r1)} in release 1")
    print(r1.groupby(["source_type", "equipment_class"]).size().to_string())
    print(f"{(r1.label_conflict != '').sum()} release 1 rows carry a label conflict")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
