"""The only read path for work orders. The console API and every MCP tool call these functions.

Instructions come from `work_order_steps`, which the schema restricts to verified quotes
(CHECK (verified)). Nothing here reads raw LLM output.
"""

from __future__ import annotations


def get_work_order(conn, work_order_id: str) -> dict | None:
    row = conn.execute("""SELECT work_order_id, asset_id, status, status_reason, priority, sla_due_at, fault_type,
                          route, required_certs, compatibility_uncertain, detection_disagreement
                          FROM work_orders WHERE work_order_id = %s""", (work_order_id,)).fetchone()
    if not row:
        return None
    keys = ("work_order_id", "asset_id", "status", "status_reason", "priority", "sla_due_at", "fault_type", "route",
            "required_certs", "compatibility_uncertain", "detection_disagreement")
    wo = dict(zip(keys, row))
    steps = conn.execute("""SELECT kind, seq, quote, manual_id, page FROM work_order_steps
                            WHERE work_order_id = %s AND verified ORDER BY kind, seq""", (work_order_id,)).fetchall()
    wo["steps"] = [dict(zip(("kind", "seq", "quote", "manual_id", "page"), s)) for s in steps]
    return wo


def owner_of(conn, work_order_id: str) -> str | None:
    # Latest OR-Tools decision, live or from the labeled demo scenario week.
    row = conn.execute("""SELECT technician_id FROM dispatch_decisions WHERE work_order_id = %s AND method = 'ortools'
                          ORDER BY decided_at DESC LIMIT 1""", (work_order_id,)).fetchone()
    return row[0] if row else None
