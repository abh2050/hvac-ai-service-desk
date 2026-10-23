"""Replay one recorded LBNL operating day into Kinesis (replay of recorded data).

Each Kinesis record is one hour of minute readings with the original recorded timestamps and
column names. An end-of-day marker follows the last hour. `hours_per_second` paces the replay
so a full day takes about 24 / hours_per_second seconds.
"""

from __future__ import annotations

import io
import json
import os
import time

import pandas as pd

from .common import bucket, catalog, client


def handler(event, _ctx):
    sc = catalog()[event["scenario_id"]]
    run_id, pace = event["run_id"], float(event.get("hours_per_second", 2.0))
    body = client("s3").get_object(Bucket=bucket(), Key=sc["s3_key"])["Body"].read()
    raw = pd.read_csv(io.BytesIO(body), low_memory=False, na_values=["NAN", "#VALUE!"])   # same as Gate 1
    ts = pd.to_datetime(raw.iloc[:, 0])
    day = pd.Timestamp(sc["day"])
    raw = raw[(ts >= day) & (ts < day + pd.Timedelta(days=1))]
    ts = pd.to_datetime(raw.iloc[:, 0])
    stream = os.environ["STREAM_NAME"]
    meta = {k: sc[k] for k in ("scenario_id", "family", "source_type", "unit", "asset_id", "equipment_class", "day")}
    hours = 0
    for hour, chunk in raw.groupby(ts.dt.floor("60min")):
        rec = {"type": "window", "run_id": run_id, **meta, "window_start": str(hour),
               "columns": list(chunk.columns), "data": json.loads(chunk.to_json(orient="values"))}
        client("kinesis").put_record(StreamName=stream, Data=json.dumps(rec).encode(), PartitionKey=run_id)
        hours += 1
        time.sleep(1.0 / pace)
    client("kinesis").put_record(StreamName=stream, PartitionKey=run_id, Data=json.dumps(
        {"type": "end_of_day", "run_id": run_id, **meta, "hours_sent": hours}).encode())
    return {"run_id": run_id, "scenario_id": sc["scenario_id"], "hours_sent": hours,
            "note": "replay of recorded data"}
