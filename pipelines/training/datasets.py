"""Turn the Release 1 episode index into hourly windows with features, rule results, and labels.

Label rules (owner approved at Gate 0):
  - Fault type comes from the LBNL inventory tables (data/episodes.csv).
  - Days with a label conflict are not scored. They are also left out of training when the
    label itself is unknown ("not in source table") or contradictory (one day, two scenarios).
    Days where only the per-minute flag disagrees with the table train on the table label.
  - Building operation faults (lighting, setback, infiltration) are detected but routed to
    operations review, not to a work order. They are reported in their own category.

Usage: .venv/bin/python -I pipelines/training/datasets.py   (writes data/processed/windows.parquet)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
from detection import features, rules  # noqa: E402

OPERATIONS_FAULTS = {
    "hvac_setback_delayed_onset", "hvac_setback_early_termination", "excessive_infiltration",
    "lighting_setback_delayed_onset", "lighting_setback_early_termination",
    "no_overnight_hvac_setback", "no_overnight_lighting_setback", "thermostat_bias",
}


def family_of(row) -> tuple[str, str]:
    """Return (family, unit source) for an episode row."""
    if row.equipment_class.startswith("AHU"):
        return "ahu", "lab"
    if "ORNL_RTU" in row.file:
        return "econ", "lab"
    return "refrig", row.source_type


def category_of(fault: str) -> str:
    if fault == "unfaulted":
        return "unfaulted"
    return "operations" if fault in OPERATIONS_FAULTS else "equipment"


def build(root: Path = ROOT) -> pd.DataFrame:
    cfg = yaml.safe_load((root / "config/rules.yaml").read_text())
    ep = pd.read_csv(root / "data/episodes.csv", dtype=str).fillna("")
    ep = ep[ep.release == "1"].copy()

    # A day listed under two scenarios or missing from the table has no usable label.
    unusable = ep.label_conflict.str.contains("more than one scenario|not in source table")
    ep["trainable"] = ~unusable
    ep["scored"] = ep.label_conflict == ""
    ep["episode_id"] = ep.file + "|" + ep.start

    frames = []
    for file, group in ep.groupby("file"):
        fam, src = family_of(group.iloc[0])
        raw = pd.read_csv(root / "data" / file, low_memory=False, na_values=["NAN", "#VALUE!"])
        m = features.canonical(raw, fam, src)
        d = features.minute_derived(m, fam, cfg)
        w = features.hourly_windows(d, cfg["window_minutes"], cfg["operating_fraction_min"])
        r = rules.evaluate(m, fam, cfg)
        w = w.merge(r, on="window_start", how="left")
        for _, e in group.iterrows():
            if e.start:  # per-day episodes in multi-day files; whole-file episodes have start/end too
                lo, hi = pd.Timestamp(e.start), pd.Timestamp(e.end) + pd.Timedelta(minutes=1)
                sel = w[(w.window_start >= lo) & (w.window_start < hi)].copy()
            else:
                sel = w.copy()
            if sel.empty:
                continue
            sel["episode_id"] = e.episode_id
            sel["file"] = file
            sel["family"] = fam
            sel["source_type"] = e.source_type
            sel["unit"] = e.unit
            sel["fault_type"] = e.fault_type
            sel["category"] = category_of(e.fault_type)
            sel["is_fault"] = int(e.fault_type != "unfaulted")
            sel["trainable"] = bool(e.trainable)
            sel["scored"] = bool(e.scored)
            frames.append(sel)
    out = pd.concat(frames, ignore_index=True)
    out["day"] = out.window_start.dt.strftime("%Y-%m-%d")
    # A conflicting day can appear twice (two scenarios); keep one copy and mark it untrainable.
    dup = out.duplicated(["file", "window_start"], keep=False)
    out.loc[dup, ["trainable", "scored"]] = False
    out = out.drop_duplicates(["file", "window_start"])
    return out


if __name__ == "__main__":
    w = build()
    dest = ROOT / "data/processed"
    dest.mkdir(parents=True, exist_ok=True)
    w.to_parquet(dest / "windows.parquet", index=False)
    print(len(w), "windows")
    print(w.groupby(["family", "source_type", "category"]).agg(
        windows=("window_start", "size"), episodes=("episode_id", "nunique"),
        scored_days=("day", lambda s: s[w.loc[s.index, "scored"]].nunique())).to_string())
