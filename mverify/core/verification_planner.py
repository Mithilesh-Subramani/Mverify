"""Deterministic requirement decomposition and verification-plan generation.

Generated scenarios are proposals. They are not executable UVM tests and are not
proof of compliance until reviewed, implemented, and run.
"""
from __future__ import annotations
import re
from typing import Any

LAYER_RULES = {
    "transaction_layer": {
        "terms": ("tlp", "transaction", "completion", "memory read", "memory write",
                  "byte enable", "tag", "requester", "configuration"),
        "scenarios": [
            ("legal_transaction", "Submit a legal transaction and check acceptance and packet fields.",
             "A legal request is accepted and its encoded TLP fields match the approved requirement."),
            ("invalid_transaction", "Submit an invalid transaction or field combination.",
             "The DUT rejects or reports the condition as required; no illegal packet is emitted."),
            ("backpressure", "Hold downstream ready low while presenting a valid transaction.",
             "Valid/data remain stable until handshake; no loss or duplication occurs."),
            ("receive_path", "Inject a valid inbound TLP and observe decoded receive outputs.",
             "Metadata and payload are correct and remain aligned through backpressure."),
        ],
    },
    "data_link_layer": {
        "terms": ("dllp", "data link", "replay", "lcrc", "ack", "nak",
                  "flow control", "credit", "sequence number", "sequence"),
        "scenarios": [
            ("lcrc_integrity", "Transmit or receive a packet with valid and corrupted LCRC.",
             "Valid packets pass; corrupted packets are detected and handled per the approved rule."),
            ("ack_nak_replay", "Exercise ACK, NAK, timeout, and replay conditions.",
             "Sequence tracking and replay behavior match the approved requirement."),
            ("flow_control", "Exercise credit initialization, credit consumption, and credit return.",
             "Traffic is blocked or permitted according to available credits."),
            ("link_backpressure", "Apply link-side backpressure during packet transfer.",
             "Packet and valid remain stable until accepted; no transaction is lost."),
        ],
    },
    "physical_layer": {
        "terms": ("ltssm", "pipe", "physical layer", "ordered set", "link training",
                  "speed negotiation", "lane", "electrical idle"),
        "scenarios": [
            ("reset_and_detect", "Apply reset and observe Detect/link initialization behavior.",
             "State transitions follow the approved PHY/PIPE-level requirements."),
            ("link_training", "Exercise training sequence exchange and negotiation.",
             "The DUT reaches the expected link state and negotiated parameters."),
            ("recovery", "Inject link degradation or retraining conditions.",
             "The DUT enters and exits Recovery as specified."),
        ],
    },
}

def classify_requirement(requirement: dict[str, Any]) -> dict[str, Any]:
    text = (requirement.get("statement") or "").lower()
    declared = (requirement.get("category") or "").lower().replace(" ", "_")
    scores = {}
    for layer, rule in LAYER_RULES.items():
        scores[layer] = sum(1 for term in rule["terms"] if term in text)
    best = max(scores, key=scores.get) if scores else "unclassified"
    if declared in LAYER_RULES:
        best = declared
        reason = "Engineer-provided category"
    elif scores[best] == 0:
        best = "unclassified"
        reason = "No layer-specific keyword evidence"
    else:
        reason = "Keyword-based candidate classification; review required"
    return {"suggested_category": best, "classification_scores": scores,
            "classification_reason": reason}

def decompose_requirement(requirement: dict[str, Any]) -> dict[str, Any]:
    """Create transparent fields without inventing numeric limits or timing."""
    statement = (requirement.get("statement") or "").strip()
    lower = statement.lower()
    negated = bool(re.search(r"\b(shall not|must not|should not|not permitted|prohibited)\b", lower))
    actor = "DUT" if re.search(r"\b(receiver|transmitter|device|controller|dut)\b", lower) else "unspecified actor"
    action = statement
    expected = "Requirement-specific expected behavior must be confirmed by an engineer."
    if negated:
        expected = "The prohibited behavior must not occur; define an observable assertion/checker."
    elif re.search(r"\b(shall|must|required)\b", lower):
        expected = "The stated behavior must occur under the requirement's defined preconditions."
    preconditions = "Not extracted. Review the surrounding specification context."
    if re.search(r"\bwhen\b|\bif\b|\bwhile\b", lower):
        preconditions = "A condition is stated in the requirement. Extract the exact condition during review."
    return {
        "actor": actor,
        "action": action,
        "preconditions": preconditions,
        "expected_result": expected,
        "negative_requirement": negated,
        "observable_signal_candidates": [],
        "missing_information": [
            "Exact preconditions and parameter values",
            "Observable DUT signals or interface events",
            "Timing bounds and tolerances, if specified",
            "Reset and configuration assumptions",
            "Error response and recovery behavior, if applicable",
        ],
        "decomposition_status": "draft_needs_engineer_review",
    }

def generate_verification_plan(mapped_requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for req in mapped_requirements:
        classified = classify_requirement(req)
        layer = classified["suggested_category"]
        decomp = decompose_requirement(req)
        scenarios = []
        if layer in LAYER_RULES:
            rule = LAYER_RULES[layer]
            # Keep scenarios relevant to requirement keywords; include broad baseline only
            # when no scenario term overlaps.
            text = (req.get("statement") or "").lower()
            relevant = []
            for scenario in rule["scenarios"]:
                key = scenario[0].replace("_", " ")
                if any(term in text for term in rule["terms"]) or not relevant:
                    relevant.append(scenario)
            scenarios = [{
                "scenario_id": f'{req.get("requirement_id","REQ")}-{i+1:02d}',
                "scenario_type": s[0],
                "stimulus": s[1],
                "expected_result": s[2],
                "status": "proposed_not_executed",
            } for i, s in enumerate(relevant[:3])]
        plan.append({
            "requirement_id": req.get("requirement_id"),
            "statement": req.get("statement"),
            "review_status": req.get("review_status", "needs_review"),
            **classified,
            "decomposition": decomp,
            "proposed_scenarios": scenarios,
            "plan_status": "draft_needs_engineer_review",
            "execution_status": "not_generated_or_run",
            "source_mapping_status": req.get("mapping_status", "not_mapped"),
            "rtl_evidence": req.get("rtl_evidence", []),
            "verification_status": "not_verified",
        })
    return plan
