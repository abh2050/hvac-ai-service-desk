"""Deterministic decision policy applied after verification. The LLM output never bypasses it."""

from __future__ import annotations

from .diagnose import ABSTAIN, OPERATIONS

LOCKOUT_WORDS = ("lockout", "lock out", "tagout", "tag out", "disconnect", "de-energize", "deenergize")


def apply(diag: dict, verified: dict, equipment_rules_fired: bool = False) -> dict:
    """`verified` maps section name -> list of verifier results aligned with diag[section].

    `equipment_rules_fired` is True when an equipment rule (the primary detector) fired that day.
    """
    cites = [c for c, v in zip(diag["citations"], verified["citations"]) if v["pass"]]
    checks = [c for c, v in zip(diag["recommended_checks"], verified["recommended_checks"]) if v["pass"]]
    safety = [c for c, v in zip(diag["safety_steps"], verified["safety_steps"]) if v["pass"]]
    cause = diag["probable_cause"]
    if cause in OPERATIONS and equipment_rules_fired:
        # The primary detector points at equipment; an operations proposal disagrees with it.
        return {"probable_cause": ABSTAIN, "llm_proposed_cause": cause, "confidence": diag.get("confidence"),
                "citations": [], "recommended_checks": [], "safety_steps": [], "abstained": True,
                "route": "manual_review", "compatibility_uncertain": False, "lockout_sourced": False,
                "dropped_unsupported": {k: 0 for k in verified},
                "reason": "operations proposal conflicts with equipment rules"}
    if cause in OPERATIONS:
        # Owner decision: operations faults go to operations review with no technician instructions.
        return {"probable_cause": cause, "llm_proposed_cause": cause, "confidence": diag.get("confidence"),
                "citations": [], "recommended_checks": [], "safety_steps": [], "abstained": False,
                "route": "operations_review", "compatibility_uncertain": False, "lockout_sourced": False,
                "dropped_unsupported": {k: 0 for k in verified}}
    abstained = cause == ABSTAIN or not cites   # policy 3: no supported passage -> insufficient evidence
    final = {
        "probable_cause": ABSTAIN if abstained else cause,
        "llm_proposed_cause": cause,
        "confidence": diag.get("confidence"),
        "citations": [] if abstained else cites,
        "recommended_checks": [] if abstained else checks,
        "safety_steps": [] if abstained else safety,
        "abstained": abstained,
        "route": "manual_review" if abstained else "technician",
        # policy 5: every cited manual must match the equipment exactly, or the diagnosis is flagged.
        "compatibility_uncertain": (not abstained) and any(c.get("match") != "exact" for c in cites),
        # policy 6 input for Gate 3: approval needs a sourced lockout step.
        "lockout_sourced": any(any(w in s["quote"].lower() for w in LOCKOUT_WORDS) for s in safety),
        "dropped_unsupported": {k: sum(1 for v in verified[k] if not v["pass"]) for k in verified},
    }
    return final
