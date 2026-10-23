"""The live detection path (replay record -> detect Lambda code) matches Gate 1 on recorded windows."""

import json
import os

import pandas as pd
import pytest


@pytest.mark.parametrize("scenario_index", [0, 30, 60, 90, 120])
def test_live_window_matches_gate1(root, scenario_index, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", str(root / "data/models"))
    monkeypatch.setenv("APP_ROOT", str(root))
    from handlers import detect
    detect.model.cache_clear()
    cat = json.loads((root / "data/deploy/catalog.json").read_text())
    sc = cat[scenario_index]
    raw = pd.read_csv(root / "data/deploy" / sc["s3_key"], low_memory=False, na_values=["NAN", "#VALUE!"])
    ts = pd.to_datetime(raw.iloc[:, 0])
    day = pd.Timestamp(sc["day"])
    raw = raw[(ts >= day) & (ts < day + pd.Timedelta(days=1))]
    ts = pd.to_datetime(raw.iloc[:, 0])
    gate1 = pd.read_parquet(root / "data/processed/windows.parquet")
    g1 = gate1[(gate1.unit == sc["unit"]) & (gate1.day == sc["day"])].set_index("window_start")
    compared = 0
    for hour, chunk in raw.groupby(ts.dt.floor("60min")):
        rec = {"family": sc["family"], "source_type": sc["source_type"], "columns": list(chunk.columns),
               "data": json.loads(chunk.to_json(orient="values"))}
        live = detect.evaluate_window(rec)
        if hour not in g1.index:
            assert live is None
            continue
        ref = g1.loc[hour]
        assert live is not None
        assert live["rule_alarm"] == bool(ref.rule_alarm)
        assert (live["rules_fired"] or "") == (ref.rules_fired or "")
        compared += 1
    assert compared > 0


def test_booster_probability_equals_classifier(root, monkeypatch):
    """The Lambda loads a plain Booster; its probability must equal the trained classifier's."""
    import xgboost as xgb
    monkeypatch.setenv("MODEL_DIR", str(root / "data/models"))
    from handlers import detect
    detect.model.cache_clear()
    w = pd.read_parquet(root / "data/processed/windows.parquet")
    for fam in ("ahu", "econ", "refrig"):
        booster, cols = detect.model(fam)
        clf = xgb.XGBClassifier()
        clf.load_model(str(root / f"data/models/detector-{fam}.json"))
        x = w[w.family == fam].head(50).reindex(columns=cols).astype(float)
        assert abs(booster.predict(xgb.DMatrix(x)) - clf.predict_proba(x)[:, 1]).max() < 1e-6
