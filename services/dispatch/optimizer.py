"""Dispatch planning: OR-Tools CP-SAT and two greedy baselines under identical hard constraints.

Time unit: whole minutes from the scenario start. A visit occupies the technician for
travel + work and starts no earlier than the job's release time. Work must fall inside one
shift window of the technician and inside the site's allowed hours. SLA lateness is measured on
arrival (start + travel) against the response deadline. Objective (config/dispatch.yaml):
  w_sla * total lateness + w_travel * total travel + w_balance * max technician workload,
plus a large penalty per unassigned job so the solver assigns every job it can.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from ortools.sat.python import cp_model

from .model import Job, Site, Technician, ineligibility, shift_windows, site_windows, travel_minutes

UNASSIGNED_PENALTY = 100_000


@dataclass
class Assignment:
    work_order_id: str
    technician_id: str | None
    status: str                      # assigned | escalated_unassigned | reschedule_requested
    start_min: int | None = None
    travel_min: int | None = None
    arrival_min: int | None = None
    lateness_min: int | None = None
    runner_up_id: str | None = None
    reason: str = ""


def _minutes(t: datetime, start: datetime) -> int:
    return int(math.floor((t - start).total_seconds() / 60))


def options(job: Job, techs: dict[str, Technician], sites: dict[str, Site], start: datetime, horizon_min: int,
            speed: float) -> tuple[list, dict]:
    """Feasible (tech, travel, earliest_start, latest_start) options per job, plus ineligibility reasons."""
    site = sites[job.site_id]
    end = start + timedelta(minutes=horizon_min)
    rel = max(0, _minutes(job.release_at, start))
    opts, reasons = [], {}
    for t in techs.values():
        why = ineligibility(t, job, site)
        if why:
            reasons[t.technician_id] = why
            continue
        trav = int(math.ceil(travel_minutes(t, site, speed)))
        found = False
        for ws, we in shift_windows(t, start, end):
            for ss, se in site_windows(site, start, end):
                lo, hi = max(ws, ss), min(we, se)
                lo_m, hi_m = max(_minutes(lo, start), 0), min(_minutes(hi, start), horizon_min)
                # Work [s + trav, s + trav + est] must sit inside [lo_m, hi_m]; the trip may start earlier.
                earliest = max(rel, lo_m - trav)
                latest = hi_m - trav - job.est_minutes
                if latest >= earliest:
                    opts.append((t.technician_id, trav, earliest, latest))
                    found = True
        if not found:
            reasons[t.technician_id] = "qualified but no shift time inside site hours in the horizon"
    return opts, reasons


def _unassigned(job: Job, reasons: dict) -> Assignment:
    if all(r != "qualified but no shift time inside site hours in the horizon" for r in reasons.values()):
        counts = {}
        for r in reasons.values():
            counts[r.split(" [")[0]] = counts.get(r.split(" [")[0], 0) + 1
        return Assignment(job.work_order_id, None, "escalated_unassigned",
                          reason=f"no technician meets the hard constraints: {counts}")
    return Assignment(job.work_order_id, None, "reschedule_requested",
                      reason="qualified technicians exist but none has capacity in the planning horizon")


def plan_cpsat(jobs: list[Job], techs, sites, start: datetime, cfg: dict) -> dict:
    w = cfg["objective_weights"]
    horizon = cfg["solver"]["planning_horizon_hours"] * 60
    speed = cfg["travel"]["average_speed_kmh"]
    m = cp_model.CpModel()
    per_job, per_tech, why = {}, {t: [] for t in techs}, {}
    for j in jobs:
        opts, reasons = options(j, techs, sites, start, horizon, speed)
        why[j.work_order_id] = reasons
        lits = []
        for k, (tid, trav, lo, hi) in enumerate(opts):
            x = m.NewBoolVar(f"x_{j.work_order_id}_{tid}_{k}")
            s = m.NewIntVar(lo, hi, f"s_{j.work_order_id}_{tid}_{k}")
            iv = m.NewOptionalFixedSizeIntervalVar(s, trav + j.est_minutes, x, f"i_{j.work_order_id}_{tid}_{k}")
            due = _minutes(j.sla_due_at, start)
            late = m.NewIntVar(0, horizon + 24 * 60, f"l_{j.work_order_id}_{tid}_{k}")
            m.Add(late >= s + trav - due).OnlyEnforceIf(x)
            m.Add(late == 0).OnlyEnforceIf(x.Not())
            lits.append((x, s, trav, late, tid))
            per_tech[tid].append((iv, x, trav + j.est_minutes))
        m.Add(sum(x for x, *_ in lits) <= 1)
        per_job[j.work_order_id] = lits
    loads = []
    for tid, items in per_tech.items():
        if items:
            m.AddNoOverlap([iv for iv, _, _ in items])
        load = m.NewIntVar(0, horizon * 4, f"load_{tid}")
        m.Add(load == sum(x * dur for _, x, dur in items))
        loads.append(load)
    max_load = m.NewIntVar(0, horizon * 4, "max_load")
    if loads:
        m.AddMaxEquality(max_load, loads)
    scale = 10  # weights may be fractional; scale to integers
    obj = []
    for j in jobs:
        lits = per_job[j.work_order_id]
        assigned = sum(x for x, *_ in lits)
        obj.append(UNASSIGNED_PENALTY * scale * (1 - assigned))
        for x, s, trav, late, _ in lits:
            obj.append(int(w["sla_lateness_per_min"] * scale) * late)
            obj.append(int(w["travel_per_min"] * scale * trav) * x)
    obj.append(int(w["workload_imbalance_per_min"] * scale) * max_load)
    m.Minimize(sum(obj))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg["solver"]["time_limit_seconds"]
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 7
    status = solver.Solve(m)
    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Policy 8: no feasible plan -> return the reason and request rescheduling.
        return {"status": status_name, "assignments": [
            Assignment(j.work_order_id, None, "reschedule_requested",
                       reason=f"optimizer found no feasible plan (solver status {status_name})") for j in jobs]}
    out = []
    for j in jobs:
        chosen = [(x, s, trav, late, tid) for x, s, trav, late, tid in per_job[j.work_order_id] if solver.Value(x)]
        if not chosen:
            out.append(_unassigned(j, why[j.work_order_id]))
            continue
        x, s, trav, late, tid = chosen[0]
        sv = solver.Value(s)
        out.append(Assignment(j.work_order_id, tid, "assigned", sv, trav, sv + trav, solver.Value(late),
                              reason="lowest weighted cost of lateness, travel, and workload"))
    return {"status": status_name, "objective": solver.ObjectiveValue(), "assignments": out}


def plan_greedy(jobs: list[Job], techs, sites, start: datetime, cfg: dict, rule: str) -> dict:
    """Baselines. rule = nearest_qualified (least travel) or earliest_available (earliest arrival)."""
    horizon = cfg["solver"]["planning_horizon_hours"] * 60
    speed = cfg["travel"]["average_speed_kmh"]
    busy = {t: [] for t in techs}           # list of (start, end) minutes
    out = []
    for j in sorted(jobs, key=lambda j: (j.release_at, j.priority)):
        opts, reasons = options(j, techs, sites, start, horizon, speed)
        cands = []
        for tid, trav, lo, hi in opts:
            s = lo
            for bs, be in sorted(busy[tid]):    # earliest start that does not overlap booked visits
                if s + trav + j.est_minutes <= bs:
                    break
                if s < be:
                    s = be
            if s <= hi and all(s + trav + j.est_minutes <= bs or s >= be for bs, be in busy[tid]):
                cands.append((tid, trav, s))
        if not cands:
            out.append(_unassigned(j, reasons))
            continue
        key = (lambda c: (c[1], c[2])) if rule == "nearest_qualified" else (lambda c: (c[2] + c[1], c[1]))
        best = min(cands, key=key)
        tid, trav, s = best
        busy[tid].append((s, s + trav + j.est_minutes))
        due = _minutes(j.sla_due_at, start)
        out.append(Assignment(j.work_order_id, tid, "assigned", s, trav, s + trav, max(0, s + trav - due),
                              reason="nearest qualified technician" if rule == "nearest_qualified"
                              else "earliest available qualified technician"))
    return {"status": "GREEDY", "assignments": out}


def add_runner_up(result: dict, jobs: list[Job], techs, sites, start: datetime, cfg: dict) -> None:
    """Runner-up: the eligible technician with the lowest stand-alone cost other than the chosen one."""
    w = cfg["objective_weights"]
    horizon = cfg["solver"]["planning_horizon_hours"] * 60
    by_id = {j.work_order_id: j for j in jobs}
    for a in result["assignments"]:
        if a.status != "assigned":
            continue
        j = by_id[a.work_order_id]
        opts, _ = options(j, techs, sites, start, horizon, cfg["travel"]["average_speed_kmh"])
        due = _minutes(j.sla_due_at, start)
        best = {}
        for tid, trav, lo, _hi in opts:
            if tid == a.technician_id:
                continue
            cost = w["sla_lateness_per_min"] * max(0, lo + trav - due) + w["travel_per_min"] * trav
            best[tid] = min(cost, best.get(tid, float("inf")))
        a.runner_up_id = min(best, key=best.get) if best else None


def score(result: dict, jobs: list[Job], techs) -> dict:
    asg = result["assignments"]
    done = [a for a in asg if a.status == "assigned"]
    loads = {t: 0 for t in techs}
    est = {j.work_order_id: j.est_minutes for j in jobs}
    for a in done:
        loads[a.technician_id] += a.travel_min + est[a.work_order_id]
    used = [v for v in loads.values() if v > 0]
    return {
        "jobs": len(asg), "assigned": len(done),
        "escalated_unassigned": sum(a.status == "escalated_unassigned" for a in asg),
        "reschedule_requested": sum(a.status == "reschedule_requested" for a in asg),
        "sla_lateness_total_min": sum(a.lateness_min for a in done),
        "late_jobs": sum(a.lateness_min > 0 for a in done),
        "travel_total_min": sum(a.travel_min for a in done),
        "max_workload_min": max(loads.values()) if loads else 0,
        "workload_std_min_active_techs": round(statistics.pstdev(used), 1) if len(used) > 1 else 0.0,
        "technicians_used": len(used),
    }
