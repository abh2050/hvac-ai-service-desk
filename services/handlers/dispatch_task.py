"""Fargate dispatch task: plan every approved, unassigned technician work order with OR-Tools.

Writes one dispatch decision per work order (assignment with reason and runner-up, or escalation
or reschedule with the reason) and an asset history row. Run: python -m handlers.dispatch_task
"""

from __future__ import annotations

import json
from datetime import timedelta

from api import db as dbmod
from dispatch import model as dm
from dispatch import optimizer as opt

from .case import _now_local, dbmod_history
from .common import APP_ROOT, db


def main() -> dict:
    sites, techs, dispatch = dm.load_config(APP_ROOT)
    now = _now_local()
    # Live dispatch plans the next 24 hours from the current hour. (The Gate 3 scenario evaluation
    # plans whole calendar days and does not use this task.)
    start = now.replace(minute=0)
    with db() as conn:
        rows = conn.execute("""SELECT w.work_order_id, a.site_id, w.approved_at, w.sla_due_at, w.required_certs,
                               w.est_minutes, w.priority, w.asset_id FROM work_orders w JOIN assets a USING (asset_id)
                               WHERE w.status = 'approved' AND w.route = 'technician'""").fetchall()
        jobs = [dm.Job(r[0], r[1], max(now, r[2].replace(tzinfo=None)), r[3].replace(tzinfo=None), tuple(r[4]), r[5], r[6],
                       {"asset_id": r[7]}) for r in rows]
        if not jobs:
            return {"planned": 0}
        res = opt.plan_cpsat(jobs, techs, sites, start, dispatch)
        opt.add_runner_up(res, jobs, techs, sites, start, dispatch)
        by_id = {j.work_order_id: j for j in jobs}
        for a in res["assignments"]:
            dbmod.save_assignment(conn, a, "ortools", now)
            if a.status == "assigned":
                start_at = start + timedelta(minutes=a.start_min)
                conn.execute("""UPDATE dispatch_decisions SET start_at = %s WHERE work_order_id = %s
                                AND decided_at = %s AND method = 'ortools'""", (start_at, a.work_order_id, now))
                msg = (f"Assigned to {a.technician_id} (runner-up {a.runner_up_id}); arrival "
                       f"{start_at + timedelta(minutes=a.travel_min):%Y-%m-%d %H:%M} local; {a.reason}.")
            else:
                msg = f"{a.status.replace('_', ' ')}: {a.reason}"
            dbmod_history(conn, by_id[a.work_order_id].meta["asset_id"], "dispatch", msg, f"work_order:{a.work_order_id}")
    return {"planned": len(jobs), "solver_status": res["status"],
            "assigned": sum(a.status == "assigned" for a in res["assignments"])}


if __name__ == "__main__":
    print(json.dumps(main()))
