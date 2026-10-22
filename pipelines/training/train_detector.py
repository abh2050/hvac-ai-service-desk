"""Train one XGBoost window classifier per equipment family.

Runs locally (called by the Gate 1 evaluation) and as a SageMaker script-mode entry point:
SageMaker passes the training channel in SM_CHANNEL_TRAIN and the output dir in SM_MODEL_DIR.
Hyperparameters are fixed here and were set before any Gate 1 result was computed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

PARAMS = dict(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
              colsample_bytree=0.8, min_child_weight=2, eval_metric="logloss", random_state=7)
NON_FEATURES = {"window_start", "episode_id", "file", "family", "source_type", "unit", "fault_type",
                "category", "is_fault", "trainable", "scored", "day", "rules_fired", "rule_alarm", "rule_hint"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    return sorted(c for c in df.columns if c not in NON_FEATURES and df[c].notna().any())


def fit(train: pd.DataFrame, cols: list[str]) -> xgb.XGBClassifier:
    y = train.is_fault.to_numpy()
    pos = max(int(y.sum()), 1)
    neg = max(int((1 - y).sum()), 1)
    model = xgb.XGBClassifier(**PARAMS, scale_pos_weight=neg / pos)
    model.fit(train[cols].astype(float), y)
    return model


def predict(model: xgb.XGBClassifier, df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return model.predict_proba(df.reindex(columns=cols).astype(float))[:, 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "data/processed"))
    ap.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "data/models"))
    args = ap.parse_args()
    windows = pd.read_parquet(Path(args.train) / "windows.parquet")
    lab = windows[(windows.source_type == "lab") & windows.trainable]
    out = Path(args.model_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = {}
    for fam, df in lab.groupby("family"):
        cols = feature_columns(df)
        model = fit(df, cols)
        model.save_model(out / f"detector-{fam}.json")
        meta[fam] = {"features": cols, "train_windows": int(len(df)), "train_positive": int(df.is_fault.sum()),
                     "params": PARAMS}
    (out / "detector-meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: {kk: v[kk] for kk in ("train_windows", "train_positive")} for k, v in meta.items()}))


if __name__ == "__main__":
    main()
