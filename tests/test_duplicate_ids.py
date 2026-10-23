"""Regression tests for the Gate 3 duplicate work order id bug (double assignment by the optimizer)."""

from datetime import timedelta

import pytest

from api import workorders as wo_mod
from dispatch import model as dm
from dispatch import optimizer as opt


def _root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]


def test_same_asset_same_minute_gets_distinct_ids(recorded_cases, input_cases, cfg, t0):
    sites, _, dispatch = dm.load_config(_root())
    asset_by_unit = {a["lbnl_unit"]: a for a in cfg["sites"]["assets"]}
    same_unit = [r for r in recorded_cases if not r["probe"] and r["case_id"].startswith("ORNL-FRP-RTU-YCD150")][:2]
    ids = set()
    for r in same_unit:
        case = input_cases[r["case_id"]]
        asset = asset_by_unit[case["unit"]]
        ids.add(wo_mod.draft(r["ai"]["final"], case, asset, sites[asset["site"]], dispatch, cfg["policy"],
                             t0, False).work_order_id)
    assert len(ids) == 2


@pytest.mark.parametrize("method", ["ortools", "nearest_qualified", "earliest_available"])
def test_planner_rejects_duplicate_job_ids(method, t0):
    sites, techs, dispatch = dm.load_config(_root())
    job = dm.Job("WO-DUP", "SITE-HTF-DC1", t0, t0 + timedelta(hours=4), ("HVAC",), 120)
    jobs = [job, dm.Job("WO-DUP", "SITE-HTF-DC1", t0, t0 + timedelta(hours=4), ("HVAC",), 120)]
    with pytest.raises(ValueError, match="duplicate"):
        if method == "ortools":
            opt.plan_cpsat(jobs, techs, sites, t0.replace(hour=0), dispatch)
        else:
            opt.plan_greedy(jobs, techs, sites, t0.replace(hour=0), dispatch, method)


def test_one_job_is_never_assigned_twice(t0):
    sites, techs, dispatch = dm.load_config(_root())
    jobs = [dm.Job(f"WO-{i}", "SITE-HTF-DC1", t0, t0 + timedelta(hours=4), ("HVAC",), 120) for i in range(6)]
    res = opt.plan_cpsat(jobs, techs, sites, t0.replace(hour=0), dispatch)
    ids = [a.work_order_id for a in res["assignments"]]
    assert sorted(ids) == sorted(j.work_order_id for j in jobs)


def test_database_rejects_duplicate_work_order_id(db, recorded_cases, input_cases, cfg, t0):
    import psycopg
    sites, _, dispatch = dm.load_config(_root())
    r = next(x for x in recorded_cases if not x["probe"])
    case = input_cases[r["case_id"]]
    asset = {a["lbnl_unit"]: a for a in cfg["sites"]["assets"]}[case["unit"]]
    wo = wo_mod.draft(r["ai"]["final"], case, asset, sites[asset["site"]], dispatch, cfg["policy"], t0, False)
    db.execute("INSERT INTO work_orders (work_order_id, asset_id, case_id, created_at, status, priority, sla_due_at, "
               "fault_type, route, required_certs, est_minutes, compatibility_uncertain, detection_disagreement) "
               "VALUES (%s,%s,%s,%s,'draft','P1',%s,'x','technician','{}',0,false,false)",
               (wo.work_order_id, wo.asset_id, wo.case_id, t0, t0))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute("INSERT INTO work_orders (work_order_id, asset_id, case_id, created_at, status, priority, sla_due_at, "
                   "fault_type, route, required_certs, est_minutes, compatibility_uncertain, detection_disagreement) "
                   "VALUES (%s,%s,%s,%s,'draft','P1',%s,'x','technician','{}',0,false,false)",
                   (wo.work_order_id, wo.asset_id, wo.case_id, t0, t0))
