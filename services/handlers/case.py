"""In-VPC handlers for the case state machine: aggregate, diagnose, verify and draft, approval, escalation.

Every decision here reuses the code measured in Gates 1 to 3. The LLM proposes; the verifier,
the policy module, and the work order module decide.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from api import db as dbmod
from api import workorders as wo_mod
from citation_verifier.verify import Verifier
from diagnosis import policy
from diagnosis.diagnose import ABSTAIN, COMPONENT, diagnose, propose
from diagnosis.evidence import build_case
from diagnosis.llm import LLM
from diagnosis.retrieval import KbIndex
from dispatch import model as dm

from .common import APP_ROOT, config, db, guardrail, param
from .metrics import emit

LOCAL = ZoneInfo("America/New_York")      # technician shifts and site hours are local time
CHECK_CLAIM = "This passage gives a step to inspect, check, adjust, clean, or service the {}."
SAFETY_CLAIM = "This passage states a safety, lockout, or disconnect step to follow before servicing the equipment."


def _now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone(LOCAL).replace(tzinfo=None, second=0, microsecond=0)


def window(event, _ctx):
    """One EventBridge Window event -> one detection_windows row."""
    d = event["detail"]
    if not d.get("operating"):
        return {"stored": False}
    with db() as conn:
        # The API normally creates the run row; a replay started another way still records cleanly.
        conn.execute("""INSERT INTO pipeline_runs (run_id, episode_id, source_type, started_by)
                        VALUES (%s, %s, %s, 'pipeline') ON CONFLICT (run_id) DO NOTHING""",
                     (d["run_id"], d["scenario_id"], d["source_type"]))
        conn.execute("""INSERT INTO detection_windows (run_id, window_start, rule_alarm, rules_fired, rule_hint,
                        model_prob, model_alarm, features) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (run_id, window_start) DO NOTHING""",
                     (d["run_id"], d["window_start"], d["rule_alarm"], d.get("rules_fired") or "", d.get("rule_hint"),
                      d.get("model_prob"), d["model_alarm"], Jsonb(d.get("features") or {})))
    return {"stored": True}


def end_of_day(event, _ctx):
    """EndOfDay event -> day decision (Gate 1 rule, policies 1 and 2) -> case or no case."""
    d = event["detail"]
    rules_cfg, pol = config("rules"), config("policy")
    with db() as conn:
        conn.execute("""INSERT INTO pipeline_runs (run_id, episode_id, source_type, started_by)
                        VALUES (%s, %s, %s, 'pipeline') ON CONFLICT (run_id) DO NOTHING""",
                     (d["run_id"], d["scenario_id"], d["source_type"]))
        rows = conn.execute("""SELECT window_start, rule_alarm, rules_fired, rule_hint, model_prob, model_alarm, features
                               FROM detection_windows WHERE run_id = %s ORDER BY window_start""", (d["run_id"],)).fetchall()
        windows = [dict(zip(("window_start", "rule_alarm", "rules_fired", "rule_hint", "model_prob", "model_alarm",
                             "features"), r)) for r in rows]
        case = build_case(f"{d['unit']}|{d['day']}|{d['run_id']}", windows, d["family"], d["equipment_class"], d["unit"],
                          d["source_type"], d["day"], rules_cfg["day_alarm_min_windows"])
        if not case["flagged"]:
            gate = {"diagnose": False, "route": "no_fault_detected", "reason": "fewer than 2 alarm windows"}
        else:
            gate = wo_mod.detection_gate(case, pol["detection"]["min_confidence"], rules_cfg["day_alarm_min_windows"])
        case["gate"] = gate
        conn.execute("""INSERT INTO cases (case_id, run_id, asset_id, detection, route, execution_arn)
                        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id) DO NOTHING""",
                     (case["case_id"], d["run_id"], d["asset_id"], Jsonb(case), gate["route"],
                      event.get("execution_arn")))
        dbmod_history(conn, d["asset_id"], "detection",
                      f"Day {d['day']} (replay of recorded data): {case['detection']['rules_alarm_windows']} rule alarm "
                      f"windows, {case['detection']['model_alarm_windows']} model alarm windows; route {gate['route']}.",
                      f"run:{d['run_id']}")
    return {"case": case, "asset_id": d["asset_id"], "run_id": d["run_id"], "diagnose": gate["diagnose"]}


def dbmod_history(conn, asset_id, kind, summary, ref):
    conn.execute("INSERT INTO asset_history (asset_id, occurred_at, kind, summary, source_ref) VALUES (%s, now(), %s, %s, %s)",
                 (asset_id, kind, summary, ref))


def _llm(model_id: str, max_tokens: int) -> LLM:
    return LLM(model_id, max_tokens=max_tokens, guardrail=guardrail())


def diagnose_case(event, _ctx):
    """Propose -> retrieve from the Knowledge Base -> cite. Returns the raw (unverified) diagnosis."""
    import time as _t
    started = _t.time()
    case = event["case"]
    models = config("models")
    llm = _llm("openai.gpt-oss-120b-1:0", models["diagnosis"]["max_tokens"])
    proposed = propose(case, llm)
    kb_id = os.environ.get("KB_ID") or param("/uptime-desk/kb/id")    # in-VPC functions get it from env (no SSM endpoint)
    passages = KbIndex(kb_id).search(proposed["manual_query"], case["equipment_class"], k=6)
    diag = diagnose(case, passages, llm, proposed)
    diag.pop("raw", None)
    emit("StageSeconds", round(_t.time() - started, 2), "Seconds", Stage="diagnose")
    return {**event, "proposed": {k: proposed.get(k) for k in ("probable_cause", "confidence", "component",
                                                                 "manual_query", "explanation")},
            "diagnosis": diag, "retrieved": [(p["manual_id"], p["page"]) for p in passages],
            "llm_usage": {"calls": llm.usage.calls, "cost_usd": round(llm.usage.cost_usd, 5),
                          "input_tokens": llm.usage.input_tokens, "output_tokens": llm.usage.output_tokens}}


def verify_and_draft(event, _ctx):
    """Verifier + policy (deterministic) -> work order draft saved to Aurora."""
    import time as _t
    started = _t.time()
    case, diag = event["case"], event["diagnosis"]
    models, pol = config("models"), config("policy")
    ent = _llm("openai.gpt-oss-20b-1:0", models["entailment"]["max_tokens"])
    verifier = Verifier.from_jsonl(APP_ROOT / "data/processed/manual_pages.jsonl", ent,
                                   pol["diagnosis"]["deterministic_match_min_token_overlap"])
    comp = COMPONENT.get(diag["probable_cause"], "equipment")
    verified = {
        "citations": [verifier.check(c["manual_id"], c["page"], c.get("quote", ""), c.get("claim", "")) for c in diag["citations"]],
        "recommended_checks": [verifier.check(c["manual_id"], c["page"], c.get("quote", ""), CHECK_CLAIM.format(comp))
                               for c in diag["recommended_checks"]],
        "safety_steps": [verifier.check(c["manual_id"], c["page"], c.get("quote", ""), SAFETY_CLAIM)
                         for c in diag["safety_steps"]],
    }
    final = policy.apply(diag, verified, equipment_rules_fired=bool(case["detection"]["rules_fired"]))
    sites, _, dispatch = dm.load_config(APP_ROOT)
    asset = next(a for a in config("sites")["assets"] if a["id"] == event["asset_id"])
    wo = wo_mod.draft(final, case, asset, sites[asset["site"]], dispatch, pol, _now_local(),
                      case["gate"].get("disagreement", False))
    with db() as conn:
        dbmod.save_work_order(conn, wo)
        conn.execute("UPDATE work_orders SET run_id = %s WHERE work_order_id = %s", (event["run_id"], wo.work_order_id))
        conn.execute("UPDATE cases SET diagnosis = %s WHERE run_id = %s",
                     (Jsonb({"proposed": event["proposed"], "final": final, "verified": verified,
                             "retrieved": event["retrieved"]}), event["run_id"]))
        dbmod_history(conn, wo.asset_id, "diagnosis",
                      f"Diagnosis: {final['probable_cause'].replace('_', ' ')}"
                      + (" (compatibility uncertain)" if final.get("compatibility_uncertain") else ""), f"run:{event['run_id']}")
        dbmod_history(conn, wo.asset_id, "work_order", f"Work order {wo.work_order_id} created, status {wo.status}.",
                      f"work_order:{wo.work_order_id}")
    emit("StageSeconds", round(_t.time() - started, 2), "Seconds", Stage="verify_and_draft")
    emit("IncidentModelCostUSD", round(event.get("llm_usage", {}).get("cost_usd", 0) + ent.usage.cost_usd, 6), "None")
    emit("WorkOrders", 1, "Count", Status=wo.status)
    return {"run_id": event["run_id"], "work_order_id": wo.work_order_id, "status": wo.status, "route": wo.route,
            "needs_approval": wo.status == "draft" and wo.route == "technician",
            "verification": {k: [v["pass"] for v in vs] for k, vs in verified.items()},
            "entailment_cost_usd": round(ent.usage.cost_usd, 5)}


def store_token(event, _ctx):
    """Called with a Step Functions task token; the API's approve call resumes the execution."""
    with db() as conn:
        conn.execute("UPDATE work_orders SET approval_task_token = %s WHERE work_order_id = %s",
                     (event["token"], event["work_order_id"]))
    return {"stored": True}


def escalate(event, _ctx):
    """Policy 9: the approval window expired; escalate and do not dispatch."""
    with db() as conn:
        conn.execute("""UPDATE work_orders SET status = 'escalated', approval_task_token = NULL,
                        status_reason = 'approval window expired; escalated, not dispatched'
                        WHERE work_order_id = %s AND status = 'draft'""", (event["work_order_id"],))
    return {"work_order_id": event["work_order_id"], "status": "escalated"}
