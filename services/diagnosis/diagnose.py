"""Diagnosis step: the LLM proposes a cause with verbatim manual quotes. It decides nothing.

The citation verifier and the policy module (deterministic code) decide what survives.
"""

from __future__ import annotations

import json

from .llm import LLM, parse_json

FAULT_TYPES = {
    "AHU": ["heating_valve_stuck", "heating_valve_leak", "cooling_valve_stuck", "cooling_valve_leak",
            "oa_damper_stuck", "oa_damper_leak"],
    "RTU": ["oa_damper_stuck", "economizer_setpoint_incorrect", "sa_temp_sensor_bias", "condenser_fouling",
            "refrigerant_undercharge", "compressor_stage2_not_engaging", "hvac_setback_delayed_onset",
            "hvac_setback_early_termination", "no_overnight_hvac_setback", "excessive_infiltration",
            "lighting_setback_delayed_onset", "lighting_setback_early_termination",
            "no_overnight_lighting_setback", "thermostat_bias"],
}
ABSTAIN = "insufficient_evidence"

SYSTEM = """You assist HVAC service managers. You propose a diagnosis. Separate software verifies every quote and decides what a technician sees.

Rules:
1. Choose probable_cause from ALLOWED_CAUSES, or "insufficient_evidence".
2. Support the cause with citations. Each citation names a passage_id from PASSAGES and an exact quote copied word for word from that passage (8 to 40 words). Do not paraphrase inside a quote.
3. recommended_checks and safety_steps may contain only quotes copied word for word from PASSAGES, each with its passage_id. Never write a procedure, part, or safety step in your own words.
4. If no passage supports any cause, return probable_cause "insufficient_evidence" with empty citations, recommended_checks, and safety_steps.
5. Use the sensor evidence and rule results to choose the cause. The rule hint can be wrong.
6. Reply with one JSON object and nothing else."""

SCHEMA = {
    "probable_cause": "one of ALLOWED_CAUSES or insufficient_evidence",
    "confidence": "number 0 to 1",
    "explanation": "two sentences on why the sensor evidence points to this cause",
    "citations": [{"passage_id": "P1", "quote": "exact words", "claim": "what this quote supports"}],
    "recommended_checks": [{"passage_id": "P2", "quote": "exact words"}],
    "safety_steps": [{"passage_id": "P3", "quote": "exact words"}],
}


def equipment_group(equipment_class: str) -> str:
    return "AHU" if equipment_class.startswith("AHU") else "RTU"


def build_prompt(case: dict, passages: list[dict]) -> str:
    plist = [{"passage_id": f"P{i + 1}", "manual": p["title"], "page": p["page"], "text": p["text"]}
             for i, p in enumerate(passages)]
    return json.dumps({
        "ALLOWED_CAUSES": FAULT_TYPES[equipment_group(case["equipment_class"])],
        "CASE": {k: case[k] for k in ("equipment_class", "unit", "source_type", "detection", "sensor_evidence")},
        "PASSAGES": plist,
        "OUTPUT_SCHEMA": SCHEMA,
    }, indent=1)


def diagnose(case: dict, passages: list[dict], llm: LLM) -> dict:
    raw = llm.complete(SYSTEM, build_prompt(case, passages))
    out = parse_json(raw) or {}
    allowed = set(FAULT_TYPES[equipment_group(case["equipment_class"])]) | {ABSTAIN}
    cause = out.get("probable_cause")
    out["probable_cause"] = cause if cause in allowed else ABSTAIN
    out["parse_ok"] = bool(out) and cause in allowed
    # Resolve passage ids to manual pages so the verifier can check the page text.
    ids = {f"P{i + 1}": p for i, p in enumerate(passages)}
    for key in ("citations", "recommended_checks", "safety_steps"):
        items = out.get(key) if isinstance(out.get(key), list) else []
        resolved = []
        for item in items:
            if not isinstance(item, dict):
                continue
            p = ids.get(item.get("passage_id"))
            resolved.append({**item, "manual_id": p["manual_id"] if p else None, "page": p["page"] if p else None,
                             "match": p["match"] if p else None})
        out[key] = resolved
    out["raw"] = raw
    return out
