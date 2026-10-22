"""Gate 1: detection results for the rules baseline and the XGBoost model.

Split: episodes, never adjacent windows. Lab families use 5-fold StratifiedGroupKFold with the
episode as the group, so every lab episode is scored once by a model that never saw it.
Field RTUs are a cross-domain test: the refrigerant-family model trains on all lab RTU.csv
windows and is applied to the field files unchanged.

Scoring unit: operating day (a day with at least one operating window).
  - A day is flagged when at least `day_alarm_min_windows` windows alarm.
  - Recall by fault type = flagged faulted days / faulted days.
  - Precision = flagged faulted days / all flagged days.
  - False alarms per operating day = alarm events (runs of consecutive alarm windows) on
    unfaulted days / unfaulted operating days.
Only days with `scored == True` count (no label conflict).

Usage: .venv/bin/python -I pipelines/evaluation/gate1_detection.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipelines" / "training"))
from train_detector import feature_columns, fit, predict  # noqa: E402

MODEL_THRESHOLD = 0.5


def oof_predictions(df: pd.DataFrame) -> pd.Series:
    """Out-of-fold probability for every window of a lab family, grouped by episode."""
    prob = pd.Series(np.nan, index=df.index)
    train_pool = df[df.trainable]
    cols = feature_columns(train_pool)
    # One label per episode for stratification.
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=7)
    for tr_idx, te_idx in sgkf.split(train_pool, train_pool.is_fault, groups=train_pool.episode_id):
        test_eps = set(train_pool.iloc[te_idx].episode_id)
        model = fit(train_pool.iloc[tr_idx], cols)
        mask = df.episode_id.isin(test_eps)
        prob[mask] = predict(model, df[mask], cols)
    return prob


def alarm_events(flags: pd.Series) -> int:
    f = flags.astype(int).to_numpy()
    return int(((f[1:] == 1) & (f[:-1] == 0)).sum() + (f[0] == 1)) if len(f) else 0


def day_table(df: pd.DataFrame, alarm_col: str, min_windows: int) -> pd.DataFrame:
    rows = []
    for (ep, day), g in df[df.scored].groupby(["episode_id", "day"]):
        g = g.sort_values("window_start")
        rows.append(dict(episode_id=ep, day=day, fault_type=g.fault_type.iloc[0], category=g.category.iloc[0],
                         is_fault=int(g.is_fault.iloc[0]), flagged=int(g[alarm_col].sum() >= min_windows),
                         events=alarm_events(g[alarm_col]), windows=len(g)))
    return pd.DataFrame(rows)


def metrics(days: pd.DataFrame) -> dict:
    if days.empty:
        return {}
    f, u = days[days.is_fault == 1], days[days.is_fault == 0]
    tp, fp = int(f.flagged.sum()), int(u.flagged.sum())
    out = {
        "faulted_days": int(len(f)), "unfaulted_days": int(len(u)),
        "recall": round(tp / len(f), 3) if len(f) else None,
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else None,
        "false_alarm_events_per_operating_day": round(u.events.sum() / len(u), 3) if len(u) else None,
        "unfaulted_days_flagged": fp,
        "by_fault_type": {},
    }
    for ft, g in f.groupby("fault_type"):
        out["by_fault_type"][ft] = {"days": int(len(g)), "recall": round(g.flagged.mean(), 3),
                                    "category": g.category.iloc[0]}
    return out


def main() -> None:
    started = time.time()
    cfg = yaml.safe_load((ROOT / "config/rules.yaml").read_text())
    w = pd.read_parquet(ROOT / "data/processed/windows.parquet")
    w["rule_alarm"] = w.rule_alarm.fillna(False).astype(bool)
    min_win = cfg["day_alarm_min_windows"]

    w["model_prob"] = np.nan
    for fam in w.family.unique():
        lab = w[(w.family == fam) & (w.source_type == "lab")]
        w.loc[lab.index, "model_prob"] = oof_predictions(lab)

    # Field cross-domain test: train on every trainable lab refrigerant window, score field.
    lab_ref = w[(w.family == "refrig") & (w.source_type == "lab") & w.trainable]
    cols = feature_columns(lab_ref)
    field = w[w.source_type == "field"]
    w.loc[field.index, "model_prob"] = predict(fit(lab_ref, cols), field, cols)
    w["model_alarm"] = w.model_prob >= MODEL_THRESHOLD

    results, window_auc = {}, {}
    for (fam, src), g in w.groupby(["family", "source_type"]):
        key = f"{src}/{fam}"
        results[key] = {"rules": metrics(day_table(g, "rule_alarm", min_win)),
                        "model": metrics(day_table(g, "model_alarm", min_win))}
        s = g[g.scored & g.model_prob.notna()]
        window_auc[key] = round(roc_auc_score(s.is_fault, s.model_prob), 3) if s.is_fault.nunique() == 2 else None

    # Rule hint agreement with the LBNL fault type on flagged faulted windows.
    hits = w[w.scored & (w.is_fault == 1) & w.rule_alarm]
    hint_match = round((hits.rule_hint == hits.fault_type).mean(), 3) if len(hits) else None

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    report = {
        "gate": 1, "name": "detection",
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": commit,
        "runtime_seconds": round(time.time() - started, 1),
        "where": "local CPU (SageMaker training job pending CDK bootstrap approval)",
        "split": "lab: 5-fold StratifiedGroupKFold by episode (seed 7); field: train on lab RTU.csv, test on field",
        "scoring_unit": "operating day; flagged when >= %d alarm windows of %d minutes" % (min_win, cfg["window_minutes"]),
        "model_threshold": MODEL_THRESHOLD,
        "category": {"ground_truth": "LBNL inventory labels in data/episodes.csv",
                     "measured": "all metrics below"},
        "results": results,
        "model_window_auc": window_auc,
        "rule_hint_matches_lbnl_fault_type": hint_match,
        "windows": int(len(w)), "scored_windows": int(w.scored.sum()),
    }
    (ROOT / "reports/gate-1.json").write_text(json.dumps(report, indent=1))
    w[["file", "window_start", "family", "source_type", "fault_type", "category", "is_fault", "scored",
       "rules_fired", "rule_alarm", "rule_hint", "model_prob", "model_alarm"]].to_csv(
        ROOT / "reports/gate-1-windows.csv.gz", index=False)
    print(json.dumps({k: {m: {kk: v[m].get(kk) for kk in ("recall", "precision", "false_alarm_events_per_operating_day", "faulted_days", "unfaulted_days")}
                          for m in ("rules", "model")} for k, v in results.items()}, indent=1))
    print("window AUC", window_auc, "hint match", hint_match)


if __name__ == "__main__":
    main()
