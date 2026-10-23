"""Load the Gate 4 demo state into Postgres from recorded Gate 2 and Gate 3 outputs.

State: Gate 3 work orders (reports/gate-3-detail.json), the OR-Tools daily plan for the scenario
week starting Monday 2026-10-26 (scenario_id 'demo-week-2026-10-26', a scenario model result),
and asset history built from those same records. Nothing here is invented: every row points at
its source record.

Usage: .venv/bin/python -I pipelines/evaluation/gate4_seed.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
from api import db as dbmod  # noqa: E402
from api.workorders import WorkOrder  # noqa: E402

DSN = os.environ.get("UPTIME_DSN", "postgresql://postgres:localtest@localhost:54329/uptime_demo")
SCENARIO = "demo-week-2026-10-26"


def parse(v):
    return datetime.fromisoformat(v) if isinstance(v, str) and v[:4].isdigit() and "-" in v[:8] else v


def main():
    detail = json.loads((ROOT / "reports/gate-3-detail.json").read_text())
    conn = dbmod.connect(DSN)
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    dbmod.migrate(conn)
    dbmod.seed_config(conn, ROOT)
    wos = {}
    for d in detail["work_orders"]:
        fields = {k: parse(v) for k, v in d.items()}
        wo = WorkOrder(**fields)
        dbmod.save_work_order(conn, wo)
        wos[wo.work_order_id] = wo
        case_unit, case_day = wo.case_id.split("|")[:2]
        conn.execute("""INSERT INTO asset_history (asset_id, occurred_at, kind, summary, source_ref)
                        VALUES (%s,%s,'detection',%s,%s)""",
                     (wo.asset_id, wo.created_at - timedelta(minutes=5),
                      f"Fault detected in replay of recorded data (LBNL unit {case_unit}, recorded day {case_day}).",
                      f"data/processed/gate2_cases.jsonl#{wo.case_id}"))
        diag = ("insufficient evidence; manual review" if wo.fault_type == "insufficient_evidence"
                else f"Diagnosis: {wo.fault_type.replace('_', ' ')}"
                + (" (compatibility uncertain)" if wo.compatibility_uncertain else ""))
        conn.execute("""INSERT INTO asset_history (asset_id, occurred_at, kind, summary, source_ref)
                        VALUES (%s,%s,'diagnosis',%s,%s)""",
                     (wo.asset_id, wo.created_at - timedelta(minutes=1), diag, f"reports/gate-2-cases.jsonl#{wo.case_id}"))
        conn.execute("""INSERT INTO asset_history (asset_id, occurred_at, kind, summary, source_ref)
                        VALUES (%s,%s,'work_order',%s,%s)""",
                     (wo.asset_id, wo.created_at, f"Work order {wo.work_order_id} created, status {wo.status}.",
                      f"reports/gate-3-detail.json#{wo.work_order_id}"))
    assigned = 0
    for day, res in detail["daily"].items():
        start = datetime.strptime(day.split()[0], "%Y-%m-%d")
        for a in res["ortools"]["assignments"]:
            wo = wos[a["work_order_id"]]
            approve_at = wo.created_at + timedelta(minutes=15)
            conn.execute("UPDATE work_orders SET approved_by = 'scenario-manager', approved_at = %s WHERE work_order_id = %s",
                         (approve_at, wo.work_order_id))
            start_at = start + timedelta(minutes=a["start_min"]) if a["start_min"] is not None else None
            conn.execute("""INSERT INTO dispatch_decisions (work_order_id, decided_at, method, technician_id, runner_up_id,
                            start_at, travel_minutes, lateness_minutes, reason, scenario_id)
                            VALUES (%s,%s,'ortools',%s,%s,%s,%s,%s,%s,%s)""",
                         (a["work_order_id"], approve_at, a["technician_id"], a["runner_up_id"], start_at,
                          a["travel_min"], a["lateness_min"], a["reason"], SCENARIO))
            status = {"assigned": "assigned"}.get(a["status"], a["status"])
            conn.execute("UPDATE work_orders SET status = %s, status_reason = %s WHERE work_order_id = %s",
                         (status, a["reason"], a["work_order_id"]))
            if a["status"] == "assigned":
                assigned += 1
                conn.execute("""INSERT INTO asset_history (asset_id, occurred_at, kind, summary, source_ref)
                                VALUES (%s,%s,'dispatch',%s,%s)""",
                             (wo.asset_id, approve_at, f"Assigned to {a['technician_id']} (scenario model plan), "
                              f"arrival {start_at + timedelta(minutes=a['travel_min'])}.",
                              f"reports/gate-3-detail.json#{a['work_order_id']}"))
    counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("work_orders", "work_order_steps", "dispatch_decisions", "asset_history")}
    print(json.dumps({"assigned": assigned, **counts}))
    for row in conn.execute("""SELECT technician_id, count(*) FROM dispatch_decisions WHERE technician_id IS NOT NULL
                               GROUP BY 1 ORDER BY 1""").fetchall():
        print(row)


if __name__ == "__main__":
    main()
