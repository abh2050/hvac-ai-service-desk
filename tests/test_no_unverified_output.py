"""Citations, checks, and safety steps that fail verification never reach a user-facing output.

User-facing outputs are the policy result, the work order, and the shared read path
(api.views) that the console and the MCP tools use.
"""

from api import views
from api import workorders as wo_mod
from dispatch import model as dm

SECTIONS = (("citations", "raw_citations"), ("recommended_checks", "raw_checks"), ("safety_steps", "raw_safety"))


def _failed_quotes(r):
    out = set()
    for vkey, rkey in SECTIONS:
        for item, v in zip(r["ai"][rkey], r["ai"]["verified"][vkey]):
            if not v["pass"]:
                out.add(item.get("quote", ""))
    return out - {""}


def _passed_quotes(r):
    out = set()
    for vkey, rkey in SECTIONS:
        for item, v in zip(r["ai"][rkey], r["ai"]["verified"][vkey]):
            if v["pass"]:
                out.add(item.get("quote", ""))
    return out


def test_failed_items_absent_from_every_recorded_final(recorded_cases):
    checked = 0
    for r in recorded_cases:
        final = r["ai"]["final"]
        shown = {i["quote"] for k in ("citations", "recommended_checks", "safety_steps") for i in final.get(k, [])}
        leaked = (_failed_quotes(r) - _passed_quotes(r)) & shown
        assert not leaked, f"{r['case_id']}: unverified text reached the final output"
        checked += len(_failed_quotes(r))
    assert checked > 0      # the recorded run does contain failed items, so this test is not vacuous


def test_work_orders_and_read_path_hold_only_verified_steps(db, recorded_cases, input_cases, cfg, t0):
    from api import db as dbmod
    sites, _, dispatch = dm.load_config(cfg_root())
    asset_by_unit = {a["lbnl_unit"]: a for a in cfg["sites"]["assets"]}
    stored = 0
    for i, r in enumerate(x for x in recorded_cases if not x["probe"]):
        case = input_cases[r["case_id"]]
        asset = asset_by_unit[case["unit"]]
        wo = wo_mod.draft(r["ai"]["final"], case, asset, sites[asset["site"]], dispatch, cfg["policy"],
                          t0, False)
        assert wo_mod.unsourced_steps(wo) == 0
        dbmod.save_work_order(db, wo)
        view = views.get_work_order(db, wo.work_order_id)
        bad = _failed_quotes(r) - _passed_quotes(r)
        assert not ({s["quote"] for s in view["steps"]} & bad)
        assert all(s["manual_id"] and s["page"] for s in view["steps"])
        stored += len(view["steps"])
    assert stored > 0
    assert db.execute("SELECT count(*) FROM work_order_steps WHERE NOT verified").fetchone()[0] == 0


def cfg_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]
