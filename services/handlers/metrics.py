"""CloudWatch embedded metric format: one JSON log line per metric, no extra AWS call or endpoint."""

from __future__ import annotations

import json
import os
import time

NAMESPACE = "UptimeDesk"


def emit(name: str, value: float, unit: str = "None", **dims: str) -> None:
    if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME") and not os.environ.get("ECS_CONTAINER_METADATA_URI_V4"):
        return                       # local runs and tests: no metric
    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
        "Namespace": NAMESPACE, "Dimensions": [list(dims)] if dims else [[]],
        "Metrics": [{"Name": name, "Unit": unit}]}]}, name: value, **dims}))
