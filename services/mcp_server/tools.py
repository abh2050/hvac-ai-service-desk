"""MCP tool handlers. The same functions back the local MCP server and the AgentCore Gateway Lambda targets.

The caller comes from the authenticated session (Cognito JWT in production), never from tool
arguments. Each handler checks ownership through `authorize`, audits every denied call, and reads
work orders only through `api.views`, which returns verified quotes only.
"""

from __future__ import annotations

from api import db as dbmod
from api import views

from .authz import Caller, authorize


class ToolError(Exception):
    pass


def _deny(conn, caller: Caller, action: str, resource: str, why: str) -> dict:
    dbmod.audit(conn, caller.sub, caller.role, action, resource, False, {"reason": why})
    return {"denied": True, "reason": why}


def _owned(conn, caller: Caller) -> list[str]:
    rows = conn.execute("""SELECT DISTINCT ON (work_order_id) work_order_id, technician_id FROM dispatch_decisions
                           WHERE method = 'ortools' ORDER BY work_order_id, decided_at DESC""").fetchall()
    return [w for w, t in rows if t == caller.technician_id]


def get_work_order(conn, caller: Caller, work_order_id: str) -> dict:
    owner = views.owner_of(conn, work_order_id)
    ok, why = authorize(caller, "get_work_order", owner)
    if not ok:
        return _deny(conn, caller, "get_work_order", work_order_id, why)
    wo = views.get_work_order(conn, work_order_id)
    if wo is None:
        return {"found": False, "work_order_id": work_order_id}
    wo["assigned_technician"] = owner
    return {"found": True, "work_order": wo}


def list_my_jobs(conn, caller: Caller, technician_id: str | None = None) -> dict:
    target = technician_id or caller.technician_id
    if caller.role == "manager" and not target:
        return {"technician_id": None, "jobs": [],
                "note": "Managers have no assigned jobs. A manager can read any work order or asset history by id, "
                        "or list one technician's jobs by technician id."}
    if caller.role != "manager" and target != caller.technician_id:
        return _deny(conn, caller, "list_my_jobs", f"technician:{target}", "cannot list another technician's jobs")
    ids = _owned(conn, Caller(caller.sub, "technician", target)) if target else []
    jobs = []
    for wid in ids:
        wo = views.get_work_order(conn, wid)
        row = conn.execute("""SELECT d.start_at, d.travel_minutes, s.site_id, s.name, s.town FROM dispatch_decisions d
                              JOIN work_orders w USING (work_order_id) JOIN assets a USING (asset_id)
                              JOIN sites s ON s.site_id = a.site_id WHERE d.work_order_id = %s AND d.method = 'ortools'
                              ORDER BY d.decided_at DESC LIMIT 1""", (wid,)).fetchone()
        jobs.append({"work_order_id": wid, "asset_id": wo["asset_id"], "status": wo["status"],
                     "priority": wo["priority"], "fault_type": wo["fault_type"], "sla_due_at": str(wo["sla_due_at"]),
                     "start_at": str(row[0]) if row and row[0] else None, "site_id": row[2] if row else None,
                     "site_name": row[3] if row else None, "town": row[4] if row else None})
    jobs.sort(key=lambda j: j["start_at"] or "")
    return {"technician_id": target, "jobs": jobs}


def get_asset_history(conn, caller: Caller, asset_id: str, limit: int = 20) -> dict:
    owned_assets = frozenset(r[0] for r in conn.execute(
        "SELECT asset_id FROM work_orders WHERE work_order_id = ANY(%s)", (_owned(conn, caller),)).fetchall())
    ok, why = authorize(caller, "get_asset_history", None, owned_assets, asset_id)
    if not ok:
        return _deny(conn, caller, "get_asset_history", asset_id, why)
    rows = conn.execute("""SELECT occurred_at, kind, summary, source_ref FROM asset_history WHERE asset_id = %s
                           ORDER BY occurred_at DESC LIMIT %s""", (asset_id, limit)).fetchall()
    return {"asset_id": asset_id, "records": [{"occurred_at": str(r[0]), "kind": r[1], "summary": r[2],
                                               "source_ref": r[3]} for r in rows]}


def search_manuals(index, caller: Caller, query: str, equipment_class: str | None = None, k: int = 5) -> dict:
    ok, _ = authorize(caller, "search_manuals", None)
    if not ok:
        raise ToolError("not authorized")
    classes = [equipment_class] if equipment_class else ["RTU", "AHU-MZVAV"]
    seen, hits = set(), []
    for cls in classes:
        for p in index.search(query, cls, k=k):
            key = (p["manual_id"], p["page"], p["text"][:40])
            if key not in seen:
                seen.add(key)
                hits.append({"manual_id": p["manual_id"], "title": p["title"], "page": p["page"],
                             "match": p["match"], "text": p["text"][:1500], "score": round(p["score"], 3)})
    hits.sort(key=lambda h: -h["score"])
    return {"query": query, "passages": hits[:k]}
