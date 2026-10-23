"""One test per decision policy branch in the spec (policies 1 to 10)."""

from datetime import timedelta

import pytest

from api import workorders as wo_mod
from citation_verifier.verify import Verifier
from diagnosis import policy
from dispatch import model as dm
from dispatch import optimizer as opt
from mcp.authz import Caller, authorize


class StubJudge:
    """Stands in for the entailment LLM so the deterministic logic is tested on its own."""

    def __init__(self, answer: bool):
        self.answer = answer

    def complete(self, system, user):
        return '{"supported": %s, "reason": "stub"}' % ("true" if self.answer else "false")


def _site(cfg, site_id):
    sites, _, _ = dm.load_config(_root())
    return sites[site_id]


def _root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]


def _asset(cfg, asset_id):
    return next(a for a in cfg["sites"]["assets"] if a["id"] == asset_id)


def _technician_final(recorded_cases):
    return next(r for r in recorded_cases if not r["probe"] and r["ai"]["final"].get("route") == "technician"
                and r["ai"]["final"]["lockout_sourced"])


# Policy 1: confidence below threshold -> manual review, not diagnosed.
def test_policy1_low_confidence_goes_to_manual_review(input_cases, cfg):
    case = dict(next(iter(input_cases.values())))
    case["detection"] = dict(case["detection"], rules_alarm_windows=0, model_alarm_windows=3,
                             model_probability_mean=0.55)
    gate = wo_mod.detection_gate(case, cfg["policy"]["detection"]["min_confidence"], 2)
    assert gate == {"diagnose": False, "route": "manual_review", "reason": "detection confidence 0.55 below 0.70"}


# Policy 2: model and rules disagree -> both shown, manager review required.
def test_policy2_disagreement_requires_manager_review(input_cases, cfg):
    case = dict(next(iter(input_cases.values())))
    case["detection"] = dict(case["detection"], rules_alarm_windows=5, model_alarm_windows=0,
                             model_probability_mean=0.2)
    gate = wo_mod.detection_gate(case, cfg["policy"]["detection"]["min_confidence"], 2)
    assert gate["diagnose"] and gate["disagreement"] and gate["route"] == "manager_review_required"


# Policy 3: no supported passage -> insufficient evidence, no citation.
def test_policy3_no_supported_passage_abstains(recorded_cases):
    r = next(r for r in recorded_cases if r["ai"]["raw_citations"])
    diag = {"probable_cause": r["ai"]["proposed"]["probable_cause"], "citations": r["ai"]["raw_citations"],
            "recommended_checks": [], "safety_steps": []}
    failed = {"citations": [{"pass": False}] * len(diag["citations"]), "recommended_checks": [], "safety_steps": []}
    final = policy.apply(diag, failed)
    assert final["probable_cause"] == "insufficient_evidence" and final["citations"] == [] and final["abstained"]


# Policy 4: a citation passes only when the cited page supports the claim.
def test_policy4_citation_needs_page_text_and_entailment(manual_pages):
    (manual_id, page), text = next((k, v) for k, v in manual_pages.items() if len(v.split()) > 60)
    quote = " ".join(text.split()[10:30])
    supported = Verifier(manual_pages, StubJudge(True), 0.6).check(manual_id, page, quote, "claim")
    unsupported = Verifier(manual_pages, StubJudge(False), 0.6).check(manual_id, page, quote, "claim")
    invented = Verifier(manual_pages, StubJudge(True), 0.6).check(manual_id, page,
                                                                  "replace the compressor with a larger model today", "claim")
    assert supported["pass"] and not unsupported["pass"] and not invented["pass"]
    assert not invented["deterministic_pass"] and invented["reason"].startswith("skipped")


# Policy 5: manual does not match the equipment exactly -> compatibility uncertain.
def test_policy5_class_match_flags_compatibility(recorded_cases):
    r = _technician_final(recorded_cases)
    assert r["ai"]["final"]["compatibility_uncertain"] is True
    assert all(c["match"] == "class" for c in r["ai"]["final"]["citations"])


# Policy 6: required safety step has no source -> approval blocked.
def test_policy6_unsourced_lockout_blocks_approval(recorded_cases, input_cases, cfg, t0):
    r = _technician_final(recorded_cases)
    final = dict(r["ai"]["final"], safety_steps=[], lockout_sourced=False)
    case = input_cases[r["case_id"]]
    site = _site(cfg, "SITE-HTF-DC1")
    wo = wo_mod.draft(final, case, _asset(cfg, "AST-RTU-01"), site, cfg["dispatch"], cfg["policy"], t0, False)
    assert wo.status == "blocked" and "lockout" in wo.status_reason
    with pytest.raises(wo_mod.ApprovalError):
        wo_mod.approve(wo, "manager-1", t0 + timedelta(minutes=5))


# Policy 7: no technician qualifies -> escalated unassigned with the reason.
def test_policy7_no_qualified_technician_escalates(t0, cfg):
    sites, techs, dispatch = dm.load_config(_root())
    job = dm.Job("WO-T7", "SITE-STM-LAB", t0, t0 + timedelta(hours=4), ("BOILER_LICENSE",), 120)
    res = opt.plan_cpsat([job], techs, sites, t0.replace(hour=0), dispatch)
    a = res["assignments"][0]
    assert a.status == "escalated_unassigned" and "missing certifications" in a.reason


# Policy 8: qualified technicians exist but no feasible slot -> reason returned, reschedule requested.
def test_policy8_no_feasible_plan_requests_reschedule(t0, cfg):
    sites, techs, dispatch = dm.load_config(_root())
    start = t0.replace(hour=0)
    late_release = start + timedelta(hours=23, minutes=50)       # nothing fits before the horizon ends
    job = dm.Job("WO-T8", "SITE-STM-LAB", late_release, late_release + timedelta(hours=4), ("CONTROLS",), 90)
    res = opt.plan_cpsat([job], techs, sites, start, dispatch)
    a = res["assignments"][0]
    assert a.status == "reschedule_requested" and "capacity" in a.reason


# Policy 9: manager approval expires -> escalated, not dispatched.
def test_policy9_expired_approval_escalates(recorded_cases, input_cases, cfg, t0):
    r = _technician_final(recorded_cases)
    wo = wo_mod.draft(r["ai"]["final"], input_cases[r["case_id"]], _asset(cfg, "AST-RTU-01"),
                      _site(cfg, "SITE-HTF-DC1"), cfg["dispatch"], cfg["policy"], t0, False)
    assert wo.status == "draft"
    late = wo.approval_deadline_at + timedelta(minutes=1)
    with pytest.raises(wo_mod.ApprovalError, match="expired"):
        wo_mod.approve(wo, "manager-1", late)
    assert wo.status == "escalated"


# Policy 10: an MCP caller asks for another technician's job -> denied and recorded.
def test_policy10_other_technicians_job_denied_and_audited(db):
    from api import db as dbmod
    caller = Caller(sub="sub-T03", role="technician", technician_id="T03")
    ok, why = authorize(caller, "get_work_order", owner_technician_id="T01")
    dbmod.audit(db, caller.sub, caller.role, "get_work_order", "WO-OTHER", ok, {"reason": why})
    assert not ok
    row = db.execute("SELECT allowed, detail->>'reason' FROM audit_log WHERE resource = 'WO-OTHER'").fetchone()
    assert row == (False, "work order is assigned to another technician")
    assert authorize(Caller("sub-m", "manager"), "get_work_order", "T01")[0]


def test_db_rejects_unverified_instruction(db, recorded_cases, input_cases, cfg, t0):
    """The schema itself refuses an instruction that did not pass verification."""
    import psycopg
    from api import db as dbmod
    r = _technician_final(recorded_cases)
    wo = wo_mod.draft(r["ai"]["final"], input_cases[r["case_id"]], _asset(cfg, "AST-RTU-01"),
                      _site(cfg, "SITE-HTF-DC1"), cfg["dispatch"], cfg["policy"], t0, False)
    dbmod.save_work_order(db, wo)
    assert db.execute("SELECT count(*) FROM work_order_steps WHERE work_order_id=%s",
                      (wo.work_order_id,)).fetchone()[0] == len(wo.steps)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("""INSERT INTO work_order_steps (work_order_id, kind, seq, quote, manual_id, page, verified)
                      VALUES (%s, 'check', 99, 'free text', 'none', 1, false)""", (wo.work_order_id,))
