"""Gate 3: work orders from recorded diagnoses, then dispatch with OR-Tools vs two baselines.

Work orders: one per Gate 2 normal case, drafted by deterministic code from the policy-checked
diagnosis (reports/gate-2-cases.jsonl). Measured: required field validity and unsourced instructions.

Dispatch scenarios (scenario model results, not field savings):
  - Each technician work order in "draft" is approved 15 minutes after creation (stated assumption).
  - Cases are spread round-robin over Mon 2026-10-26 to Fri 2026-10-30. Each keeps the hour of day
    of its first recorded alarm. Each day is planned separately (24 hour horizon).
  - A surge scenario puts every approved job on Monday to test capacity.
  - OR-Tools, nearest qualified, and earliest available all use the same hard constraints and travel model.

Usage: .venv/bin/python -I pipelines/evaluation/gate3_dispatch.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
from api import workorders as wo_mod  # noqa: E402
from dispatch import model as dm  # noqa: E402
from dispatch import optimizer as opt  # noqa: E402

SCENARIO_DAYS = [datetime(2026, 10, 26) + timedelta(days=i) for i in range(5)]
APPROVAL_DELAY = timedelta(minutes=15)
METHODS = ("ortools", "nearest_qualified", "earliest_available")


def run_methods(jobs, techs, sites, start, dispatch):
    out = {}
    for m in METHODS:
        t = time.time()
        res = (opt.plan_cpsat(jobs, techs, sites, start, dispatch) if m == "ortools"
               else opt.plan_greedy(jobs, techs, sites, start, dispatch, m))
        opt.add_runner_up(res, jobs, techs, sites, start, dispatch)
        sc = opt.score(res, jobs, techs)
        sc["constraint_violations"] = validate([a.__dict__ for a in res["assignments"]], jobs, techs, sites,
                                               start, dispatch)
        sc["solve_seconds"] = round(time.time() - t, 2)
        sc["solver_status"] = res["status"]
        out[m] = {"score": sc, "assignments": [a.__dict__ for a in res["assignments"]]}
    return out


ADDITIVE = ("jobs", "assigned", "escalated_unassigned", "reschedule_requested", "sla_lateness_total_min",
            "late_jobs", "travel_total_min", "solve_seconds", "constraint_violations")


def add(totals, sc):
    for k in ADDITIVE:
        totals[k] = round(totals.get(k, 0) + sc.get(k, 0), 2)
    totals.setdefault("daily_max_workload_min", []).append(sc["max_workload_min"])


def validate(assignments, jobs, techs, sites, start, dispatch) -> int:
    """Independent check of every assignment: eligibility, time windows, and no overlap per technician."""
    by_id = {j.work_order_id: j for j in jobs}
    horizon = dispatch["solver"]["planning_horizon_hours"] * 60
    bad, booked = 0, defaultdict(list)
    for a in assignments:
        if a["status"] != "assigned":
            continue
        j = by_id[a["work_order_id"]]
        t, site = techs[a["technician_id"]], sites[j.site_id]
        opts, _ = opt.options(j, techs, sites, start, horizon, dispatch["travel"]["average_speed_kmh"])
        fits = any(tid == t.technician_id and lo <= a["start_min"] <= hi for tid, _, lo, hi in opts)
        if dm.ineligibility(t, j, site) or not fits:
            bad += 1
        booked[t.technician_id].append((a["start_min"], a["start_min"] + a["travel_min"] + j.est_minutes))
    for spans in booked.values():
        spans.sort()
        bad += sum(1 for (s1, e1), (s2, _e2) in zip(spans, spans[1:]) if s2 < e1)
    return bad


def main():
    started = time.time()
    sites, techs, dispatch = dm.load_config(ROOT)
    pol = yaml.safe_load((ROOT / "config/policy.yaml").read_text())
    rules = yaml.safe_load((ROOT / "config/rules.yaml").read_text())
    site_cfg = yaml.safe_load((ROOT / "config/sites.yaml").read_text())
    asset_by_unit = {a["lbnl_unit"]: a for a in site_cfg["assets"]}
    inputs = {c["case_id"]: c for c in map(json.loads, (ROOT / "data/processed/gate2_cases.jsonl").read_text().splitlines())}
    rows = [json.loads(line) for line in (ROOT / "reports/gate-2-cases.jsonl").read_text().splitlines()]
    rows = sorted((r for r in rows if not r["probe"]), key=lambda r: r["case_id"])

    work_orders, gate_routes = [], defaultdict(int)
    for i, r in enumerate(rows):
        case = inputs[r["case_id"]]
        gate = wo_mod.detection_gate(case, pol["detection"]["min_confidence"], rules["day_alarm_min_windows"])
        gate_routes[gate["route"]] += 1
        if not gate["diagnose"]:
            continue
        asset = asset_by_unit[case["unit"]]
        site = sites[asset["site"]]
        hour = (case.get("operating_pattern") or {}).get("alarm_hours", [8])[0]
        created = SCENARIO_DAYS[i % len(SCENARIO_DAYS)] + timedelta(hours=hour)
        wo = wo_mod.draft(r["ai"]["final"], case, asset, site, dispatch, pol, created, gate["disagreement"])
        work_orders.append(wo)

    ids = [w.work_order_id for w in work_orders]
    assert len(ids) == len(set(ids)), "duplicate work order ids"
    validity = [not wo_mod.missing_fields(w) for w in work_orders]
    unsourced = sum(wo_mod.unsourced_steps(w) for w in work_orders)
    status_counts = defaultdict(int)
    for w in work_orders:
        status_counts[f"{w.route}/{w.status}"] += 1

    approved = []
    for w in work_orders:
        if w.status == "draft" and w.route == "technician":
            wo_mod.approve(w, "scenario-manager", w.created_at + APPROVAL_DELAY)
            approved.append(w)

    def job_of(w):
        return dm.Job(w.work_order_id, w.site_id, w.approved_at, w.sla_due_at, tuple(w.required_certs),
                      w.est_minutes, w.priority, {"fault": w.fault_type})

    per_day, totals = {}, {m: {} for m in METHODS}
    for day in SCENARIO_DAYS:
        jobs = [job_of(w) for w in approved if w.created_at.date() == day.date()]
        if not jobs:
            continue
        res = run_methods(jobs, techs, sites, day, dispatch)
        per_day[day.strftime("%Y-%m-%d %a")] = res
        for m in METHODS:
            add(totals[m], res[m]["score"])

    surge_start = SCENARIO_DAYS[0]
    surge_jobs = []
    for w in approved:
        j = job_of(w)
        shift = surge_start.date() - w.created_at.date()
        j.release_at += shift
        j.sla_due_at += shift
        surge_jobs.append(j)
    surge = run_methods(surge_jobs, techs, sites, surge_start, dispatch)
    w = dispatch["objective_weights"]

    def weighted(late, travel, maxload):
        return round(w["sla_lateness_per_min"] * late + w["travel_per_min"] * travel
                     + w["workload_imbalance_per_min"] * maxload, 1)

    for m in METHODS:
        totals[m]["weighted_cost"] = weighted(totals[m]["sla_lateness_total_min"], totals[m]["travel_total_min"],
                                              sum(totals[m]["daily_max_workload_min"]))
        sm = surge[m]["score"]
        sm["weighted_cost"] = weighted(sm["sla_lateness_total_min"], sm["travel_total_min"], sm["max_workload_min"])
        totals[m]["daily_solver_status"] = sorted({per_day[d][m]["score"]["solver_status"] for d in per_day})
    for m in METHODS:
        d = totals[m].pop("daily_max_workload_min", [])
        totals[m]["mean_daily_max_workload_min"] = round(sum(d) / len(d), 1) if d else None

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    report = {
        "gate": 3, "name": "work orders and dispatch",
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_commit": commit,
        "runtime_seconds": round(time.time() - started, 1),
        "categories": {"measured": "work order validity, unsourced instructions, and computed optimizer results",
                       "scenario_model": "every dispatch number is a scenario model result, not a field saving"},
        "inputs": {"diagnoses": "reports/gate-2-cases.jsonl", "cases": len(rows),
                   "detection_gate_routes": dict(gate_routes)},
        "work_orders": {"count": len(work_orders),
                        "required_field_validity": round(sum(validity) / len(validity), 3) if validity else None,
                        "unsourced_instructions": unsourced,
                        "by_route_and_status": dict(status_counts),
                        "approved_for_dispatch": len(approved)},
        "dispatch": {"assumptions": {"approval_delay_minutes": 15, "travel_model": dispatch["travel"],
                                     "weights": dispatch["objective_weights"],
                                     "sla_measured_on": "arrival", "visits_start_from": "home base"},
                     "daily_totals": totals,
                     "daily": {d: {m: v[m]["score"] for m in METHODS} for d, v in per_day.items()},
                     "surge_monday": {m: surge[m]["score"] for m in METHODS}},
    }
    (ROOT / "reports/gate-3.json").write_text(json.dumps(report, indent=1, default=str))
    detail = {"daily": per_day, "surge_monday": surge,
              "work_orders": [dict(w.__dict__) for w in work_orders]}
    (ROOT / "reports/gate-3-detail.json").write_text(json.dumps(detail, indent=1, default=str))
    print(json.dumps({k: report[k] for k in ("inputs", "work_orders")}, indent=1, default=str))
    print(json.dumps(report["dispatch"]["daily_totals"], indent=1))
    print(json.dumps(report["dispatch"]["surge_monday"], indent=1))


if __name__ == "__main__":
    main()
