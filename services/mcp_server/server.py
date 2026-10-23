"""Local MCP server (stdio) exposing the four Uptime Desk tools.

The caller identity is fixed for the session from the environment (UPTIME_CALLER_SUB, _ROLE,
_TECH). In production, AgentCore Gateway validates the Cognito JWT and passes the same identity
to the same handlers; the model never chooses who it is.

Run: UPTIME_CALLER_SUB=... UPTIME_CALLER_ROLE=technician UPTIME_CALLER_TECH=T03 \
     .venv/bin/python -m mcp_server.server  (with services/ on PYTHONPATH)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))

import numpy as np  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

from api import db as dbmod  # noqa: E402
from diagnosis.retrieval import Embedder, VectorIndex, load_chunks  # noqa: E402

from . import tools  # noqa: E402
from .authz import Caller  # noqa: E402

CALLER = Caller(os.environ["UPTIME_CALLER_SUB"], os.environ["UPTIME_CALLER_ROLE"],
                os.environ.get("UPTIME_CALLER_TECH") or None)
CONN = dbmod.connect(os.environ.get("UPTIME_DSN", "postgresql://postgres:localtest@localhost:54329/uptime_demo"))
INDEX = VectorIndex(load_chunks(ROOT / "data/processed/manual_chunks.jsonl"),
                    np.load(ROOT / "data/processed/manual_vectors.npy"),
                    Embedder(profile=os.environ.get("AWS_PROFILE", "awsnew")))
FAIL = set(filter(None, os.environ.get("UPTIME_FAIL_TOOLS", "").split(",")))   # fault injection for Gate 4 tests

app = MCPServer("uptime-desk")


def _maybe_fail(name: str):
    if name in FAIL:
        raise RuntimeError(f"{name} is temporarily unavailable")


@app.tool()
def get_work_order(work_order_id: str) -> str:
    """Get one work order by id: status, priority, SLA, fault, and verified manual steps with sources."""
    _maybe_fail("get_work_order")
    return json.dumps(tools.get_work_order(CONN, CALLER, work_order_id), default=str)


@app.tool()
def list_my_jobs() -> str:
    """List the signed-in technician's assigned work orders with site, start time, and SLA."""
    _maybe_fail("list_my_jobs")
    return json.dumps(tools.list_my_jobs(CONN, CALLER), default=str)


@app.tool()
def get_asset_history(asset_id: str) -> str:
    """Get recorded history (detections, diagnoses, work orders, dispatch) for an asset on one of your jobs."""
    _maybe_fail("get_asset_history")
    return json.dumps(tools.get_asset_history(CONN, CALLER, asset_id), default=str)


@app.tool()
def search_manuals(query: str, equipment_class: str = "") -> str:
    """Search the equipment manuals. Returns passages with manual id and page. equipment_class: RTU or AHU-MZVAV."""
    _maybe_fail("search_manuals")
    return json.dumps(tools.search_manuals(INDEX, CALLER, query, equipment_class or None), default=str)


if __name__ == "__main__":
    app.run()
