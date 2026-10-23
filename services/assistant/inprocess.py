"""The technician assistant inside the API Lambda: same prompt, tools, and checks as the MCP
version (agent.py), with tool handlers called directly instead of over a stdio MCP session.
The caller identity comes from the validated Cognito token, never from the model.
"""

from __future__ import annotations

import json
import os
import time

from citation_verifier.verify import Verifier
from diagnosis.llm import LLM
from diagnosis.retrieval import KbIndex
from handlers.common import APP_ROOT, config, guardrail, param
from mcp_server import tools
from mcp_server.authz import Caller

from .agent import MAX_TURNS, SYSTEM, finalize

TOOL_SPECS = [
    {"name": "get_work_order", "description": "Get one work order by id: status, priority, SLA, fault, and verified manual steps with sources.",
     "schema": {"type": "object", "properties": {"work_order_id": {"type": "string"}}, "required": ["work_order_id"]}},
    {"name": "list_my_jobs", "description": "List the signed-in technician's assigned work orders with site, start time, and SLA.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "get_asset_history", "description": "Get recorded history for an asset on one of your jobs.",
     "schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
    {"name": "search_manuals", "description": "Search the equipment manuals. Returns passages with manual id and page. equipment_class: RTU or AHU-MZVAV.",
     "schema": {"type": "object", "properties": {"query": {"type": "string"}, "equipment_class": {"type": "string"}},
                "required": ["query"]}},
]
TOOL_CONFIG = {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"],
                                       "inputSchema": {"json": t["schema"]}}} for t in TOOL_SPECS]}


def _call(name: str, args: dict, caller: Caller, conn, kb) -> dict:
    if name == "get_work_order":
        return tools.get_work_order(conn, caller, args.get("work_order_id", ""))
    if name == "list_my_jobs":
        return tools.list_my_jobs(conn, caller)
    if name == "get_asset_history":
        return tools.get_asset_history(conn, caller, args.get("asset_id", ""))
    if name == "search_manuals":
        return tools.search_manuals(kb, caller, args.get("query", ""), args.get("equipment_class") or None)
    return {"error": f"unknown tool {name}"}


def ask_inprocess(question: str, caller: Caller, conn) -> dict:
    models = config("models")
    llm = LLM("openai.gpt-oss-120b-1:0", max_tokens=models["assistant"]["max_tokens"], guardrail=guardrail())
    ent = LLM("openai.gpt-oss-20b-1:0", max_tokens=models["entailment"]["max_tokens"])
    verifier = Verifier.from_jsonl(APP_ROOT / "data/processed/manual_pages.jsonl", ent, 0.6)
    kb = KbIndex(os.environ.get("KB_ID") or param("/uptime-desk/kb/id"))
    trace, t0 = [], time.time()
    messages = [{"role": "user", "content": [{"text": question}]}]
    final_text = ""
    for _ in range(MAX_TURNS):
        resp = llm.converse_raw(SYSTEM, messages, TOOL_CONFIG)
        content = resp["output"]["message"]["content"]
        messages.append({"role": "assistant", "content": content})
        uses = [b["toolUse"] for b in content if "toolUse" in b]
        if not uses:
            final_text = "".join(b.get("text", "") for b in content)
            break
        results = []
        for u in uses:
            entry = {"tool": u["name"], "input": u.get("input", {})}
            try:
                text, entry["error"] = json.dumps(_call(u["name"], u.get("input") or {}, caller, conn, kb), default=str), False
            except Exception as e:
                text, entry["error"] = json.dumps({"error": f"{u['name']} failed: {e}"}), True
            entry["result"] = text
            trace.append(entry)
            results.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"text": text[:12000]}],
                                           "status": "error" if entry["error"] else "success"}})
        messages.append({"role": "user", "content": results})
    r = finalize(question, {"sub": caller.sub, "role": caller.role, "technician_id": caller.technician_id},
                 final_text, trace, verifier, t0)
    r["cost_usd"] = round(llm.usage.cost_usd + ent.usage.cost_usd, 5)
    r["tool_trace"] = [{"tool": t["tool"], "input": t["input"], "error": t["error"],
                        "denied": '"denied": true' in t["result"]} for t in trace]
    for k in ("model_answer", "citations_checked", "caller"):
        r.pop(k, None)
    return r
