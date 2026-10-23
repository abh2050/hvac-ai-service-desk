"""MCP tool handlers: ownership checks, audit of denied calls, and the verified-only read path."""

from datetime import timedelta

from api import db as dbmod
from api import workorders as wo_mod
from dispatch import model as dm
from mcp_server import tools
from mcp_server.authz import Caller


def _root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]


def _seed_one(db, recorded_cases, input_cases, cfg, t0, tech="T01"):
    sites, _, dispatch = dm.load_config(_root())
    r = next(x for x in recorded_cases if not x["probe"] and x["ai"]["final"].get("route") == "technician"
             and x["ai"]["final"]["lockout_sourced"])
    case = input_cases[r["case_id"]]
    asset = {a["lbnl_unit"]: a for a in cfg["sites"]["assets"]}[case["unit"]]
    wo = wo_mod.draft(r["ai"]["final"], case, asset, sites[asset["site"]], dispatch, cfg["policy"], t0, False)
    dbmod.save_work_order(db, wo)
    db.execute("""INSERT INTO dispatch_decisions (work_order_id, decided_at, method, technician_id, start_at, reason)
                  VALUES (%s, %s, 'ortools', %s, %s, 'test')""", (wo.work_order_id, t0, tech, t0 + timedelta(hours=1)))
    db.execute("""INSERT INTO asset_history (asset_id, occurred_at, kind, summary, source_ref)
                  VALUES (%s, %s, 'note', 'test record', 'test')""", (wo.asset_id, t0))
    return wo


def test_owner_reads_own_work_order_with_verified_steps_only(db, recorded_cases, input_cases, cfg, t0):
    wo = _seed_one(db, recorded_cases, input_cases, cfg, t0)
    res = tools.get_work_order(db, Caller("sub-T01", "technician", "T01"), wo.work_order_id)
    assert res["found"] and res["work_order"]["assigned_technician"] == "T01"
    assert res["work_order"]["steps"] and all(s["manual_id"] and s["page"] for s in res["work_order"]["steps"])


def test_other_technician_denied_and_audited(db, recorded_cases, input_cases, cfg, t0):
    wo = _seed_one(db, recorded_cases, input_cases, cfg, t0)
    res = tools.get_work_order(db, Caller("sub-T03", "technician", "T03"), wo.work_order_id)
    assert res == {"denied": True, "reason": "work order is assigned to another technician"}
    hist = tools.get_asset_history(db, Caller("sub-T03", "technician", "T03"), wo.asset_id)
    assert hist["denied"]
    jobs = tools.list_my_jobs(db, Caller("sub-T03", "technician", "T03"), technician_id="T01")
    assert jobs["denied"]
    assert db.execute("SELECT count(*) FROM audit_log WHERE NOT allowed AND actor = 'sub-T03'").fetchone()[0] == 3


def test_list_my_jobs_returns_only_callers_jobs(db, recorded_cases, input_cases, cfg, t0):
    wo = _seed_one(db, recorded_cases, input_cases, cfg, t0)
    mine = tools.list_my_jobs(db, Caller("sub-T01", "technician", "T01"))
    other = tools.list_my_jobs(db, Caller("sub-T03", "technician", "T03"))
    assert [j["work_order_id"] for j in mine["jobs"]] == [wo.work_order_id]
    assert other["jobs"] == []


def test_manager_reads_all(db, recorded_cases, input_cases, cfg, t0):
    wo = _seed_one(db, recorded_cases, input_cases, cfg, t0)
    res = tools.get_work_order(db, Caller("sub-m", "manager"), wo.work_order_id)
    assert res["found"]
