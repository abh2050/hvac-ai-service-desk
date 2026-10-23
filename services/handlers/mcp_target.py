"""AgentCore Gateway Lambda target: the four Uptime Desk MCP tools.

Runs the same handlers as the local MCP server (mcp_server.tools): ownership checks, audit of
denied calls, verified-quote read path. The identity comes only from `caller_context`, which the
request interceptor sets from the validated token. Without it the call fails closed.
"""

from __future__ import annotations

import json
import os

from diagnosis.retrieval import KbIndex
from mcp_server import tools
from mcp_server.authz import Caller

from .common import db, param


def _tool_name(ctx) -> str:
    name = (getattr(getattr(ctx, "client_context", None), "custom", None) or {}).get("bedrockAgentCoreToolName", "")
    return name.split("___", 1)[1] if "___" in name else name


def handler(event, ctx):
    event = dict(event or {})
    cc = event.pop("caller_context", None) or {}
    if not cc.get("sub") or cc.get("role") not in ("manager", "technician"):
        return {"error": "no verified caller identity; request refused"}
    caller = Caller(cc["sub"], cc["role"], cc.get("technician_id"))
    name = _tool_name(ctx)
    with db() as conn:
        if name == "get_work_order":
            out = tools.get_work_order(conn, caller, event.get("work_order_id", ""))
        elif name == "list_my_jobs":
            out = tools.list_my_jobs(conn, caller)
        elif name == "get_asset_history":
            out = tools.get_asset_history(conn, caller, event.get("asset_id", ""))
        elif name == "search_manuals":
            kb = KbIndex(os.environ.get("KB_ID") or param("/uptime-desk/kb/id"))
            out = tools.search_manuals(kb, caller, event.get("query", ""), event.get("equipment_class") or None)
        else:
            out = {"error": f"unknown tool {name}"}
    return json.loads(json.dumps(out, default=str))
