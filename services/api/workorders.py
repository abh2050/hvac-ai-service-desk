"""Work order drafting and approval. Deterministic code only: the LLM never writes a field here.

Every instruction on a work order is a verified manual quote carried over from the diagnosis
policy. Priority, SLA, required certifications, and status come from configuration and rules.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta

ABSTAIN = "insufficient_evidence"
PRIORITY_BY_CRITICALITY = {"critical": "P1", "high": "P2", "standard": "P3"}
REQUIRED_FIELDS = ("work_order_id", "asset_id", "case_id", "created_at", "status", "priority", "sla_due_at",
                   "fault_type", "route", "required_certs", "est_minutes", "approval_deadline_at")


@dataclass
class WorkOrder:
    work_order_id: str
    asset_id: str
    site_id: str
    case_id: str
    created_at: datetime
    status: str
    status_reason: str | None
    priority: str
    sla_due_at: datetime
    fault_type: str
    route: str
    required_certs: list
    est_minutes: int
    compatibility_uncertain: bool
    detection_disagreement: bool
    approval_deadline_at: datetime | None
    steps: list = field(default_factory=list)       # dicts: kind, seq, quote, manual_id, page, verified
    approved_by: str | None = None
    approved_at: datetime | None = None
    edited: bool = False


def detection_gate(case: dict, min_confidence: float, min_windows: int) -> dict:
    """Policies 1 and 2, before any diagnosis.

    Confidence is the second-opinion model's mean probability on the flagged windows. Rules are the
    primary detector (owner decision after Gate 1).
    """
    det = case["detection"]
    rules_alarm = det["rules_alarm_windows"] >= min_windows
    model_alarm = det["model_alarm_windows"] >= min_windows
    if not rules_alarm and det["model_probability_mean"] < min_confidence:
        return {"diagnose": False, "route": "manual_review",
                "reason": f"detection confidence {det['model_probability_mean']:.2f} below {min_confidence:.2f}"}
    disagreement = rules_alarm != model_alarm
    return {"diagnose": True, "disagreement": disagreement,
            "route": "manager_review_required" if disagreement else "normal",
            "reason": "rules and model disagree; console shows both" if disagreement else ""}


def required_certs_for(fault_type: str, dispatch_cfg: dict) -> list:
    table = dispatch_cfg["required_certs_by_fault"]
    return list(table.get(fault_type, table["default"]))


def est_minutes_for(required: list, dispatch_cfg: dict) -> int:
    d = dispatch_cfg["job_duration_minutes"]
    if any(c.startswith("EPA608") for c in required):
        return d["refrigerant"]
    if required == ["CONTROLS"]:
        return d["controls"]
    return d["default"]


def draft(final: dict, case: dict, asset: dict, site, dispatch_cfg: dict, policy_cfg: dict,
          created_at: datetime, disagreement: bool) -> WorkOrder:
    """Build a draft work order from a policy-checked diagnosis (policies 3, 5, 6)."""
    route = final.get("route", "technician")
    fault = final["probable_cause"] if not final["abstained"] else final.get("llm_proposed_cause") or ABSTAIN
    required = required_certs_for(fault, dispatch_cfg) if route == "technician" else []
    steps = []
    for kind, key in (("safety", "safety_steps"), ("check", "recommended_checks"), ("citation", "citations")):
        for seq, item in enumerate(final.get(key, []), start=1):
            steps.append({"kind": kind, "seq": seq, "quote": item["quote"], "manual_id": item["manual_id"],
                          "page": item["page"], "verified": True})
    if final["abstained"]:
        status, reason = "blocked", "insufficient evidence: no manual passage supports the cause; manual review"
    elif route == "operations_review":
        status, reason = "draft", "building operations issue; operations review, no technician dispatch"
    elif not final.get("lockout_sourced"):
        status, reason = "blocked", "no sourced lockout or disconnect step in the manuals; approval blocked"
    else:
        status, reason = "draft", "awaiting manager approval"
    if disagreement and status == "draft":
        reason += "; rules and model disagree, manager review required"
    return WorkOrder(
        # The case hash keeps ids unique when two cases on one asset start in the same minute.
        work_order_id=f"WO-{asset['id']}-{created_at:%Y%m%d%H%M}-{hashlib.sha1(case['case_id'].encode()).hexdigest()[:6]}",
        asset_id=asset["id"], site_id=site.site_id,
        case_id=case["case_id"], created_at=created_at, status=status, status_reason=reason,
        priority="P3" if route == "operations_review" else PRIORITY_BY_CRITICALITY[site.criticality],
        sla_due_at=created_at + timedelta(hours=site.sla_response_hours), fault_type=fault, route=route,
        required_certs=required, est_minutes=est_minutes_for(required, dispatch_cfg) if required else 0,
        compatibility_uncertain=bool(final.get("compatibility_uncertain")), detection_disagreement=disagreement,
        approval_deadline_at=created_at + timedelta(hours=policy_cfg["work_order"]["approval_timeout_hours"]),
        steps=steps)


def missing_fields(wo: WorkOrder) -> list:
    bad = [f for f in REQUIRED_FIELDS if getattr(wo, f) in (None, "")]
    if wo.route == "technician" and wo.status != "blocked" and not wo.required_certs:
        bad.append("required_certs")
    if wo.sla_due_at <= wo.created_at:
        bad.append("sla_due_at")
    return bad


def unsourced_steps(wo: WorkOrder) -> int:
    return sum(1 for s in wo.steps if not (s.get("manual_id") and s.get("page") and s.get("quote") and s.get("verified")))


class ApprovalError(Exception):
    pass


def approve(wo: WorkOrder, manager: str, now: datetime, keep_step_ids: set | None = None) -> WorkOrder:
    """Approve, optionally removing steps. Managers cannot add free-text instructions."""
    if wo.status != "draft":
        raise ApprovalError(f"cannot approve a work order in status {wo.status}: {wo.status_reason}")
    if wo.route != "technician":
        raise ApprovalError("only technician work orders are approved for dispatch")
    if now > wo.approval_deadline_at:
        expire(wo, now)
        raise ApprovalError("approval window expired; work order escalated")
    if keep_step_ids is not None:
        kept = [s for i, s in enumerate(wo.steps) if i in keep_step_ids]
        if not any(s["kind"] == "safety" for s in kept):
            raise ApprovalError("edit would remove every sourced safety step")
        wo.edited = len(kept) != len(wo.steps)
        wo.steps = kept
    wo.status, wo.status_reason = "approved", "approved by manager"
    wo.approved_by, wo.approved_at = manager, now
    return wo


def reject(wo: WorkOrder, manager: str, now: datetime, reason: str) -> WorkOrder:
    if wo.status not in ("draft", "blocked"):
        raise ApprovalError(f"cannot reject a work order in status {wo.status}")
    wo.status, wo.status_reason = "rejected", f"rejected by {manager}: {reason}"
    return wo


def expire(wo: WorkOrder, now: datetime) -> WorkOrder:
    """Policy 9: an unapproved draft past its deadline escalates and is not dispatched."""
    if wo.status == "draft" and wo.approval_deadline_at and now > wo.approval_deadline_at:
        wo.status, wo.status_reason = "escalated", "approval window expired; escalated, not dispatched"
    return wo
