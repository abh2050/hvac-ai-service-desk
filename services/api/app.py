"""Uptime Desk HTTP API (FastAPI on Lambda through Mangum, behind API Gateway HTTP API).

API Gateway's JWT authorizer validates the Cognito ID token on every route. The handler reads the
caller's identity only from the validated claims: `sub`, `cognito:groups`, and
`custom:technician_id`. Ownership checks reuse mcp_server.authz, and work orders are read only
through api.views (verified quotes only).
"""

from __future__ import annotations

import io
import json
import os
import uuid
from datetime import datetime

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from handlers.common import bucket, catalog, client, config, db
from mcp_server import tools
from mcp_server.authz import Caller

from . import db as dbmod
from . import views

app = FastAPI(title="Uptime Desk API", version="1.0")
TREND_COLUMNS = {
    "ahu": ["AHU: Supply Air Temperature", "AHU: Mixed Air Temperature", "AHU: Outdoor Air Temperature",
            "AHU: Return Air Temperature"],
    "econ": ["RTU_SA_TEMP", "RTU_MA_TEMP", "RTU_OA_TEMP", "RTU_RA_TEMP", "RTU_OA_DMPR_DM"],
    "refrig": ["RTU_SA_TEMP", "RTU_RA_TEMP", "RTU_REFG_SUCT_PRES_1", "RTU_REFG_SUCT_PRES_2",
               "RTU: Supply Air Temperature", "RTU: Return Air Temperature",
               "RTU: Circuit 1 Suction Pressure", "RTU: Circuit 2 Suction Pressure"],
}


@app.options("/{path:path}", include_in_schema=False)
def preflight(path: str) -> Response:
    """CORS preflight (no token). API Gateway adds the allowed-origin headers from its CORS settings."""
    return Response(status_code=204)


def caller(request: Request) -> Caller:
    """Identity from the API Gateway JWT authorizer claims. Requests without claims never reach here."""
    claims = (request.scope.get("aws.event", {}).get("requestContext", {}).get("authorizer", {})
              .get("jwt", {}).get("claims", {}))
    if not claims and os.environ.get("ALLOW_TEST_CALLER") == "1":       # unit tests only
        claims = json.loads(request.headers.get("x-test-claims", "{}"))
    if not claims.get("sub"):
        raise HTTPException(401, "missing identity")
    groups = claims.get("cognito:groups", "")
    groups = groups if isinstance(groups, list) else str(groups).strip("[]").replace(",", " ").split()
    role = "manager" if "manager" in groups else "technician" if "technician" in groups else "none"
    if role == "none":
        raise HTTPException(403, "user is in no Uptime Desk group")
    return Caller(claims["sub"], role, claims.get("custom:technician_id") or None)


def manager_only(c: Caller = Depends(caller)) -> Caller:
    if c.role != "manager":
        with db() as conn:
            dbmod.audit(conn, c.sub, c.role, "manager_endpoint", "api", False, {"reason": "manager role required"})
        raise HTTPException(403, "manager role required")
    return c


@app.get("/me")
def me(c: Caller = Depends(caller)):
    return {"sub": c.sub, "role": c.role, "technician_id": c.technician_id}


@app.get("/scenarios")
def scenarios(c: Caller = Depends(caller)):
    """Recorded LBNL days the replay can play. Labels are ground truth, shown after a run finishes."""
    return [{k: v for k, v in s.items() if k != "label"} | {"note": "replay of recorded data"}
            for s in catalog().values()]


class RunRequest(BaseModel):
    scenario_id: str
    hours_per_second: float = 4.0


@app.post("/runs")
def start_run(body: RunRequest, c: Caller = Depends(manager_only)):
    if body.scenario_id not in catalog():
        raise HTTPException(404, "unknown scenario")
    sc = catalog()[body.scenario_id]
    run_id = f"run-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"
    with db() as conn:
        conn.execute("""INSERT INTO pipeline_runs (run_id, episode_id, source_type, started_by)
                        VALUES (%s,%s,%s,%s)""", (run_id, body.scenario_id, sc["source_type"], c.sub))
    ex = client("stepfunctions").start_execution(
        stateMachineArn=os.environ["REPLAY_MACHINE_ARN"], name=run_id,
        input=json.dumps({"scenario_id": body.scenario_id, "run_id": run_id,
                          "hours_per_second": max(0.5, min(body.hours_per_second, 12))}))
    with db() as conn:
        conn.execute("UPDATE pipeline_runs SET replay_execution_arn = %s WHERE run_id = %s", (ex["executionArn"], run_id))
    return {"run_id": run_id, "scenario_id": body.scenario_id, "source_type": sc["source_type"],
            "note": "replay of recorded data"}


def _stages(execution_arn: str) -> list[dict]:
    """Stage status and timing from the case state machine history."""
    hist = client("stepfunctions").get_execution_history(executionArn=execution_arn, maxResults=500)["events"]
    stages, open_ = [], {}
    for e in hist:
        if e["type"].endswith("StateEntered"):
            name = e["stateEnteredEventDetails"]["name"]
            open_[name] = e["timestamp"]
            stages.append({"stage": name, "status": "running", "started": e["timestamp"].isoformat()})
        elif e["type"].endswith("StateExited"):
            name = e["stateExitedEventDetails"]["name"]
            for s in reversed(stages):
                if s["stage"] == name and s["status"] == "running":
                    s["status"] = "done"
                    s["seconds"] = round((e["timestamp"] - open_[name]).total_seconds(), 2)
                    out = e["stateExitedEventDetails"].get("output") or "{}"
                    try:
                        o = json.loads(out)
                        cost = (o.get("llm_usage") or {}).get("cost_usd", 0) + (o.get("entailment_cost_usd") or 0)
                        if cost:
                            s["model_cost_usd"] = round(cost, 5)
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    break
        elif "Failed" in e["type"] or "TimedOut" in e["type"]:
            if stages:
                stages[-1]["status"] = "failed" if "Failed" in e["type"] else "timed_out"
    return stages


@app.get("/runs/{run_id}")
def run_status(run_id: str, c: Caller = Depends(caller)):
    with db() as conn:
        run = conn.execute("SELECT episode_id, source_type, started_at, replay_execution_arn FROM pipeline_runs WHERE run_id=%s",
                           (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "unknown run")
        win = conn.execute("""SELECT count(*), count(*) FILTER (WHERE rule_alarm), count(*) FILTER (WHERE model_alarm)
                              FROM detection_windows WHERE run_id=%s""", (run_id,)).fetchone()
        case = conn.execute("SELECT case_id, route, detection, execution_arn FROM cases WHERE run_id=%s", (run_id,)).fetchone()
        wo = conn.execute("SELECT work_order_id, status, status_reason FROM work_orders WHERE run_id=%s", (run_id,)).fetchone()
    replay = client("stepfunctions").describe_execution(executionArn=run[3]) if run[3] else {}
    sc = catalog().get(run[0], {})
    done = bool(case)
    return {
        "run_id": run_id, "scenario_id": run[0], "source_type": run[1], "note": "replay of recorded data",
        "replay": {"status": replay.get("status"), "started": str(replay.get("startDate", "")),
                   "stopped": str(replay.get("stopDate", ""))},
        "detection": {"operating_windows": win[0], "rule_alarm_windows": win[1], "model_alarm_windows": win[2]},
        "case": {"case_id": case[0], "route": case[1], "gate": case[2].get("gate")} if case else None,
        "stages": _stages(case[3]) if case and case[3] else [],
        "work_order": {"work_order_id": wo[0], "status": wo[1], "status_reason": wo[2]} if wo else None,
        "ground_truth_label": sc.get("label") if done else None,
    }


@app.get("/runs/{run_id}/trend")
def trend(run_id: str, c: Caller = Depends(caller)):
    """Recorded sensor trend for the replayed day (10-minute means) plus the detected alarm windows."""
    with db() as conn:
        run = conn.execute("SELECT episode_id FROM pipeline_runs WHERE run_id=%s", (run_id,)).fetchone()
        wins = conn.execute("""SELECT window_start, rule_alarm, model_alarm, model_prob, rules_fired, rule_hint
                               FROM detection_windows WHERE run_id=%s ORDER BY window_start""", (run_id,)).fetchall()
    if not run:
        raise HTTPException(404, "unknown run")
    sc = catalog()[run[0]]
    raw = pd.read_csv(io.BytesIO(client("s3").get_object(Bucket=bucket(), Key=sc["s3_key"])["Body"].read()),
                      low_memory=False, na_values=["NAN", "#VALUE!"])
    raw.columns = [x.strip() for x in raw.columns]
    ts = pd.to_datetime(raw.iloc[:, 0])
    day = pd.Timestamp(sc["day"])
    raw = raw[(ts >= day) & (ts < day + pd.Timedelta(days=1))].copy()
    cols = [x for x in TREND_COLUMNS[sc["family"]] if x in raw.columns]
    raw["t"] = pd.to_datetime(raw.iloc[:, 0]).dt.floor("10min")
    series = raw.groupby("t")[cols].mean(numeric_only=True).round(2).reset_index()
    series["t"] = series["t"].astype(str)
    return {"scenario_id": sc["scenario_id"], "family": sc["family"], "columns": cols,
            "series": json.loads(series.to_json(orient="records")),
            "windows": [{"window_start": str(w[0]), "rule_alarm": w[1], "model_alarm": w[2], "model_prob": w[3],
                         "rules_fired": w[4], "rule_hint": w[5]} for w in wins],
            "note": "replay of recorded data"}


@app.get("/runs/{run_id}/diagnosis")
def diagnosis(run_id: str, c: Caller = Depends(caller)):
    with db() as conn:
        row = conn.execute("SELECT diagnosis, detection, route FROM cases WHERE run_id=%s", (run_id,)).fetchone()
    if not row or not row[0]:
        return {"ready": False}
    diag = row[0]
    final = diag["final"]

    def link(item):
        url = client("s3").generate_presigned_url(
            "get_object", Params={"Bucket": bucket(), "Key": f"manuals/{item['manual_id']}.pdf"}, ExpiresIn=900)
        return {**item, "url": f"{url}#page={item['page']}"}

    citations = []
    for section, key in (("citation", "citations"), ("check", "recommended_checks"), ("safety", "safety_steps")):
        for item in final.get(key, []):
            citations.append({**link(item), "kind": section, "support": "passed: quote on page and entailed"})
    removed = {k: sum(1 for v in vs if not v["pass"]) for k, vs in diag["verified"].items()}
    return {"ready": True, "probable_cause": final["probable_cause"], "llm_proposed_cause": final.get("llm_proposed_cause"),
            "confidence": final.get("confidence"), "explanation": diag["proposed"].get("explanation"),
            "abstained": final["abstained"], "route": final.get("route"),
            "compatibility_uncertain": final.get("compatibility_uncertain"), "lockout_sourced": final.get("lockout_sourced"),
            "citations": citations, "removed_unverified": removed, "detection": row[1]["detection"],
            "rules_vs_model": {"rules_alarm_windows": row[1]["detection"]["rules_alarm_windows"],
                               "model_alarm_windows": row[1]["detection"]["model_alarm_windows"],
                               "disagreement": row[1].get("gate", {}).get("disagreement", False)}}


@app.get("/work-orders")
def work_orders(c: Caller = Depends(caller)):
    with db() as conn:
        rows = conn.execute("""SELECT work_order_id FROM work_orders ORDER BY created_at DESC LIMIT 200""").fetchall()
        out = []
        for (wid,) in rows:
            if c.role != "manager" and views.owner_of(conn, wid) != c.technician_id:
                continue
            out.append(views.get_work_order(conn, wid))
    return out


class Approval(BaseModel):
    keep_step_indexes: list[int] | None = None


@app.post("/work-orders/{work_order_id}/approve")
def approve(work_order_id: str, body: Approval, c: Caller = Depends(manager_only)):
    with db() as conn:
        row = conn.execute("""SELECT status, approval_task_token, approval_deadline_at FROM work_orders
                              WHERE work_order_id=%s""", (work_order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown work order")
        if row[0] != "draft":
            raise HTTPException(409, f"work order is {row[0]}; only drafts can be approved")
        if body.keep_step_indexes is not None:
            steps = conn.execute("""SELECT step_id, kind FROM work_order_steps WHERE work_order_id=%s
                                    ORDER BY kind, seq""", (work_order_id,)).fetchall()
            keep = [steps[i] for i in body.keep_step_indexes if 0 <= i < len(steps)]
            if not any(k == "safety" for _, k in keep) and any(k == "safety" for _, k in steps):
                raise HTTPException(422, "an edit cannot remove every sourced safety step")
            drop = [sid for sid, _ in steps if sid not in {s for s, _ in keep}]
            if drop:
                conn.execute("DELETE FROM work_order_steps WHERE step_id = ANY(%s)", (drop,))
                conn.execute("UPDATE work_orders SET edited = true WHERE work_order_id=%s", (work_order_id,))
        conn.execute("""UPDATE work_orders SET status='approved', status_reason='approved by manager', approved_by=%s,
                        approved_at=now() WHERE work_order_id=%s""", (c.sub, work_order_id))
        dbmod.audit(conn, c.sub, c.role, "approve", work_order_id, True, {})
    if row[1]:
        client("stepfunctions").send_task_success(taskToken=row[1], output=json.dumps({"approved_by": c.sub}))
    return {"work_order_id": work_order_id, "status": "approved", "dispatch": "started" if row[1] else "no running pipeline"}


class Rejection(BaseModel):
    reason: str


@app.post("/work-orders/{work_order_id}/reject")
def reject(work_order_id: str, body: Rejection, c: Caller = Depends(manager_only)):
    with db() as conn:
        row = conn.execute("SELECT status, approval_task_token FROM work_orders WHERE work_order_id=%s",
                           (work_order_id,)).fetchone()
        if not row or row[0] not in ("draft", "blocked"):
            raise HTTPException(409, "only draft or blocked work orders can be rejected")
        conn.execute("UPDATE work_orders SET status='rejected', status_reason=%s WHERE work_order_id=%s",
                     (f"rejected by manager: {body.reason}", work_order_id))
        dbmod.audit(conn, c.sub, c.role, "reject", work_order_id, True, {"reason": body.reason})
    if row[1]:
        client("stepfunctions").send_task_failure(taskToken=row[1], error="Rejected", cause=body.reason[:200])
    return {"work_order_id": work_order_id, "status": "rejected"}


@app.get("/dispatch")
def dispatch_board(c: Caller = Depends(caller)):
    with db() as conn:
        rows = conn.execute("""SELECT DISTINCT ON (d.work_order_id) d.work_order_id, d.technician_id, d.runner_up_id,
                               d.start_at, d.travel_minutes, d.lateness_minutes, d.reason, w.status, w.sla_due_at,
                               w.priority, w.fault_type, w.asset_id, d.scenario_id
                               FROM dispatch_decisions d JOIN work_orders w USING (work_order_id)
                               ORDER BY d.work_order_id, d.decided_at DESC""").fetchall()
    keys = ("work_order_id", "technician_id", "runner_up_id", "start_at", "travel_minutes", "lateness_minutes", "reason",
            "status", "sla_due_at", "priority", "fault_type", "asset_id", "scenario_id")
    items = [dict(zip(keys, r)) for r in rows]
    if c.role != "manager":
        items = [i for i in items if i["technician_id"] == c.technician_id]
    for i in items:
        for k in ("start_at", "sla_due_at"):
            i[k] = str(i[k]) if i[k] else None
    return {"assigned": [i for i in items if i["status"] == "assigned"],
            "escalated": [i for i in items if i["status"] in ("escalated", "escalated_unassigned", "reschedule_requested")],
            "note": "scenario model results where scenario_id is set; live assignments otherwise"}


class Question(BaseModel):
    question: str


@app.post("/assistant")
def assistant(body: Question, c: Caller = Depends(caller)):
    from assistant.inprocess import ask_inprocess
    with db() as conn:
        return ask_inprocess(body.question[:1000], c, conn)
