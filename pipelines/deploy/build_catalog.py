"""Build the scenario catalog the app offers, and stage the recorded files the replay reads.

Each scenario is one Release 1 operating day (lab or field) with its published LBNL label.
Only days without a label conflict are offered. Field episodes span weeks, so the catalog lists
each flagged field day separately. Output: data/deploy/catalog.json and data/deploy/episodes/.

Usage: .venv/bin/python -I pipelines/deploy/build_catalog.py
"""

import json
import shutil
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/deploy"


def main():
    sites = yaml.safe_load((ROOT / "config/sites.yaml").read_text())
    asset_by_unit = {a["lbnl_unit"]: a for a in sites["assets"]}
    w = pd.read_parquet(ROOT / "data/processed/windows.parquet")
    w = w[w.scored & (w.source_type.isin(["lab", "field"]))]
    rows = []
    for (ep, day), g in w.groupby(["episode_id", "day"]):
        first = g.iloc[0]
        asset = asset_by_unit[first.unit]
        rows.append({
            "scenario_id": f"{first.unit}|{day}",
            "episode_id": ep, "file": first.file, "day": day,
            "source_type": first.source_type, "family": first.family,
            "unit": first.unit, "asset_id": asset["id"], "site_id": asset["site"],
            "equipment_class": asset["equipment_class"],
            "label": {"fault_type": first.fault_type, "category": first.category,
                      "source": "published LBNL label (ground truth)"},
            "operating_windows": int(len(g)),
        })
    cat = pd.DataFrame(rows)
    # Keep the app list readable: every lab day, and 6 evenly spaced days per field episode.
    keep = []
    for ep, g in cat.groupby("episode_id"):
        g = g.sort_values("day")
        if g.source_type.iloc[0] == "field" and len(g) > 6:
            g = g.iloc[[round(i * (len(g) - 1) / 5) for i in range(6)]]
        keep.append(g)
    cat = pd.concat(keep).sort_values(["source_type", "family", "scenario_id"])
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "episodes").mkdir(parents=True)
    for f in sorted(cat.file.unique()):
        dest = OUT / "episodes" / f.replace("raw/", "").replace(" ", "_")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "data" / f, dest)
    cat["s3_key"] = "episodes/" + cat.file.str.replace("raw/", "").str.replace(" ", "_")
    (OUT / "catalog.json").write_text(json.dumps(cat.drop(columns=["file"]).to_dict("records"), indent=1))
    size = sum(p.stat().st_size for p in (OUT / "episodes").rglob("*") if p.is_file())
    print(len(cat), "scenarios;", cat.groupby(["source_type", "family"]).size().to_dict(), f"; files {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
