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

# Owner decision after Gate 2 run 1: building operations faults go to operations review, not to a
# technician. No repair procedure is issued for them, so no manual citation is required.
OPERATIONS = {"hvac_setback_delayed_onset", "hvac_setback_early_termination", "no_overnight_hvac_setback",
              "excessive_infiltration", "lighting_setback_delayed_onset", "lighting_setback_early_termination",
              "no_overnight_lighting_setback", "thermostat_bias"}

# Deterministic fault -> component map. Verification claims use it for the AI path and the
# baseline alike, so both are judged against the same wording.
COMPONENT = {
    "heating_valve_stuck": "heating coil valve", "heating_valve_leak": "heating coil valve",
    "cooling_valve_stuck": "cooling coil valve", "cooling_valve_leak": "cooling coil valve",
    "oa_damper_stuck": "outdoor air damper", "oa_damper_leak": "outdoor air damper",
    "economizer_setpoint_incorrect": "economizer controller setpoint",
    "sa_temp_sensor_bias": "supply air temperature sensor", "condenser_fouling": "condenser coil",
    "refrigerant_undercharge": "refrigerant charge", "compressor_stage2_not_engaging": "second stage compressor",
    "thermostat_bias": "zone thermostat or temperature sensor",
    "hvac_setback_delayed_onset": "unit operating schedule", "hvac_setback_early_termination": "unit operating schedule",
    "no_overnight_hvac_setback": "unit operating schedule", "excessive_infiltration": "building envelope and outdoor air",
    "lighting_setback_delayed_onset": "lighting schedule", "lighting_setback_early_termination": "lighting schedule",
    "no_overnight_lighting_setback": "lighting schedule",
}

PROPOSE_SYSTEM = """You assist HVAC service managers. From sensor evidence and rule results, propose the most likely fault.
The rule hint can be wrong; weigh the sensor evidence yourself.
Some allowed causes are building operations problems (schedules, setbacks, lighting, infiltration, thermostat offsets),
not equipment faults. They show up in OPERATING_PATTERN (when the unit ran) and zone conditions more than in
refrigerant or coil readings. Consider them before choosing an equipment fault.
Choose probable_cause from ALLOWED_CAUSES. Then write manual_query: a short search query (under 15 words) for
equipment manual pages about inspecting, checking, servicing, or adjusting the component involved.
Reply with one JSON object and nothing else."""

PROPOSE_SCHEMA = {
    "probable_cause": "one of ALLOWED_CAUSES",
    "confidence": "number 0 to 1",
    "explanation": "two sentences on why the sensor evidence points to this cause",
    "component": "the physical component involved, for example 'heating coil valve'",
    "manual_query": "search query for manual pages about that component",
}

SYSTEM = """You assist HVAC service managers. A fault was proposed from sensor data. Your job is to find what the
equipment manual says about the component involved. Separate software verifies every quote and decides what a technician sees.

Rules:
1. probable_cause must be PROPOSED_CAUSE, or "insufficient_evidence" if no passage concerns the component involved.
2. citations: each names a passage_id from PASSAGES and an exact quote copied word for word from that passage (8 to 40 words),
   with a claim stating what the quote says about the component (for example how it works, how to inspect or adjust it,
   or what symptom it causes). Do not paraphrase inside a quote. Claims must be literally supported by the quote's page.
3. recommended_checks and safety_steps may contain only quotes copied word for word from PASSAGES, each with its
   passage_id. Never write a procedure, part, or safety step in your own words. Include a lockout, disconnect, or
   de-energize step if any passage has one.
4. If no passage concerns the component, return "insufficient_evidence" with empty citations, recommended_checks, and safety_steps.
5. Reply with one JSON object and nothing else."""

SCHEMA = {
    "probable_cause": "PROPOSED_CAUSE or insufficient_evidence",
    "citations": [{"passage_id": "P1", "quote": "exact words", "claim": "what this quote says about the component"}],
    "recommended_checks": [{"passage_id": "P2", "quote": "exact words"}],
    "safety_steps": [{"passage_id": "P3", "quote": "exact words"}],
}


def equipment_group(equipment_class: str) -> str:
    return "AHU" if equipment_class.startswith("AHU") else "RTU"


def case_view(case: dict) -> dict:
    view = {k: case[k] for k in ("equipment_class", "unit", "source_type", "detection", "sensor_evidence")}
    view["OPERATING_PATTERN"] = case.get("operating_pattern")
    return view


def propose(case: dict, llm: LLM) -> dict:
    """Step 1: name the likely fault from sensor evidence only, plus a manual search query."""
    allowed = FAULT_TYPES[equipment_group(case["equipment_class"])]
    raw = llm.complete(PROPOSE_SYSTEM, json.dumps({"ALLOWED_CAUSES": allowed, "CASE": case_view(case),
                                                   "OUTPUT_SCHEMA": PROPOSE_SCHEMA}, indent=1))
    out = parse_json(raw) or {}
    cause = out.get("probable_cause")
    out["parse_ok"] = cause in allowed
    out["probable_cause"] = cause if cause in allowed else ABSTAIN
    out["manual_query"] = out.get("manual_query") or f"{case['equipment_class']} {cause or ''}".replace("_", " ")
    out["raw"] = raw
    return out


def build_prompt(case: dict, passages: list[dict], proposed: dict) -> str:
    plist = [{"passage_id": f"P{i + 1}", "manual": p["title"], "page": p["page"], "text": p["text"]}
             for i, p in enumerate(passages)]
    return json.dumps({
        "PROPOSED_CAUSE": proposed["probable_cause"],
        "COMPONENT": proposed.get("component"),
        "CASE": case_view(case),
        "PASSAGES": plist,
        "OUTPUT_SCHEMA": SCHEMA,
    }, indent=1)


def diagnose(case: dict, passages: list[dict], llm: LLM, proposed: dict) -> dict:
    """Step 3: cite what the retrieved manual pages say about the proposed fault's component."""
    if proposed["probable_cause"] in OPERATIONS:
        out = {"probable_cause": proposed["probable_cause"], "route": "operations_review", "citations": [],
               "recommended_checks": [], "safety_steps": [], "raw": ""}
    elif proposed["probable_cause"] == ABSTAIN:
        out = {"probable_cause": ABSTAIN, "citations": [], "recommended_checks": [], "safety_steps": [], "raw": ""}
    else:
        raw = llm.complete(SYSTEM, build_prompt(case, passages, proposed))
        out = parse_json(raw) or {}
        out["raw"] = raw
    cause = out.get("probable_cause")
    out["probable_cause"] = proposed["probable_cause"] if cause == proposed["probable_cause"] else ABSTAIN
    out["parse_ok"] = proposed["parse_ok"] and cause in (proposed["probable_cause"], ABSTAIN)
    out["confidence"] = proposed.get("confidence")
    out["explanation"] = proposed.get("explanation")
    out["component"] = proposed.get("component")
    out["route"] = out.get("route", "technician")
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
    return out
