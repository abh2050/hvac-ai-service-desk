"""Kinesis consumer: rules baseline first, then the detector model, per hourly window.

Uses the same feature and rule code as Gate 1. Publishes one EventBridge event per window and
one per end-of-day marker; the case state machine aggregates them.
"""

from __future__ import annotations

import base64
import functools
import json
import os
from pathlib import Path

import pandas as pd
import xgboost as xgb

from detection import features, rules

from .common import bucket, client, config

SOURCE = "uptime-desk.detection"


@functools.lru_cache(maxsize=None)
def model(family: str):
    local = os.environ.get("MODEL_DIR")       # tests and local runs read the same files from disk
    if local:
        meta = json.loads((Path(local) / "detector-meta.json").read_text())
        path = str(Path(local) / f"detector-{family}.json")
    else:
        meta = json.loads(client("s3").get_object(Bucket=bucket(), Key="models/detector-meta.json")["Body"].read())
        path = f"/tmp/detector-{family}.json"
        client("s3").download_file(bucket(), f"models/detector-{family}.json", path)
    # Plain Booster: the binary:logistic output is the same probability XGBClassifier.predict_proba
    # returns, without scikit-learn in the image (tests/test_live_detection.py checks this).
    m = xgb.Booster()
    m.load_model(path)
    return m, meta[family]["features"]


def evaluate_window(rec: dict) -> dict | None:
    cfg = config("rules")
    raw = pd.DataFrame(rec["data"], columns=rec["columns"])
    m = features.canonical(raw, rec["family"], rec["source_type"])
    d = features.minute_derived(m, rec["family"], cfg)
    w = features.hourly_windows(d, cfg["window_minutes"], cfg["operating_fraction_min"])
    if w.empty:
        return None                      # fan mostly off: not an operating window
    r = rules.evaluate(m, rec["family"], cfg)
    row = w.iloc[0]
    rr = r.iloc[0] if not r.empty else None
    mdl, cols = model(rec["family"])
    x = pd.DataFrame([row]).reindex(columns=cols).astype(float)
    prob = float(mdl.predict(xgb.DMatrix(x))[0])
    feats = {k: (None if pd.isna(v) else round(float(v), 4)) for k, v in row.items() if k != "window_start"}
    return {"rule_alarm": bool(rr is not None and rr.rule_alarm), "rules_fired": (rr.rules_fired if rr is not None else ""),
            "rule_hint": (rr.rule_hint if rr is not None else "") or None, "model_prob": round(prob, 4),
            "model_alarm": prob >= 0.5, "features": feats}


def handler(event, _ctx):
    entries = []
    for r in event["Records"]:
        rec = json.loads(base64.b64decode(r["kinesis"]["data"]))
        base = {k: rec[k] for k in ("run_id", "scenario_id", "family", "source_type", "unit", "asset_id",
                                    "equipment_class", "day")}
        if rec["type"] == "end_of_day":
            entries.append({"Source": SOURCE, "DetailType": "EndOfDay", "Detail": json.dumps({**base, "hours_sent": rec["hours_sent"]})})
            continue
        result = evaluate_window(rec)
        detail = {**base, "window_start": rec["window_start"], "operating": result is not None, **(result or {})}
        entries.append({"Source": SOURCE, "DetailType": "Window", "Detail": json.dumps(detail, default=str)})
    for i in range(0, len(entries), 10):
        batch = [dict(e, EventBusName=os.environ.get("EVENT_BUS", "default")) for e in entries[i:i + 10]]
        resp = client("events").put_events(Entries=batch)
        if resp.get("FailedEntryCount"):
            raise RuntimeError(f"EventBridge rejected {resp['FailedEntryCount']} entries")
    return {"events": len(entries)}
