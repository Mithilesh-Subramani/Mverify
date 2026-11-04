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

def _requirement_test_dimensions(statement: str) -> list[dict[str, str]]:
    """Derive test dimensions from the actual requirement wording.

    These are prompts for an engineer, not invented PCIe normative values.
    """
    text = statement.lower()
    dimensions = []
    rules = [
        (r"shall not|must not|invalid|error|malformed|unsupported|reserved",
         "negative_case", "Exercise the prohibited, invalid, malformed, or unsupported condition stated by the requirement."),
        (r"when|if|while|after|before|until|upon",
         "condition_and_sequence", "Exercise the stated condition and sequence. Extract exact ordering and preconditions from the specification context."),
        (r"timeout|within|minimum|maximum|at least|no more than|shall be",
         "timing_or_limit", "Check the stated timing or numeric limit. Obtain exact values and tolerances from the cited specification clause."),
        (r"valid|ready|accept|transfer|transmit|receive|handshake",
         "interface_handshake", "Check the specified interface event, acceptance condition, and stability during any wait state."),
        (r"credit|flow control|buffer|full|empty",
         "resource_boundary", "Check resource availability, exhaustion, update, and recovery as required by the cited clause."),
        (r"crc|lcrc|ecrc|parity|integrity|sequence number|replay|nak|ack",
         "protocol_integrity_or_recovery", "Check the required integrity, sequence, acknowledgement, and recovery behavior. Do not assume unspecified retry limits."),
        (r"reset|initializ|training|configuration|negotia",
         "initialization_and_configuration", "Check the specified initialization/configuration sequence and resulting observable state."),
    ]
    for pattern, kind, prompt in rules:
        if re.search(pattern, text):
            dimensions.append({"dimension": kind, "test_intent": prompt})
    if not dimensions:
        dimensions.append({
            "dimension": "requirement_specific_behavior",
            "test_intent": "Derive stimulus and checks from the complete specification clause and its referenced definitions. No generic test is assumed.",
        })
    return dimensions


def generate_verification_plan(mapped_requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build spec-led verification proposals; never infer PCIe behavior from feature names alone."""
    plan = []
    for req in mapped_requirements:
        statement = (req.get("statement") or "").strip()
        decomp = decompose_requirement(req)
        dimensions = _requirement_test_dimensions(statement)
        source = req.get("source") or "unspecified specification source"
        clause = req.get("clause") or req.get("section") or "not supplied"
        approved = (req.get("review_status") or "needs_review").lower() == "approved"
        mapped = req.get("mapping_status") == "structural_evidence_found"
        scenarios = []
        if approved:
            for i, dimension in enumerate(dimensions, start=1):
                scenarios.append({
                    "scenario_id": f'{req.get("requirement_id", "REQ")}-{i:02d}',
                    "scenario_type": dimension["dimension"],
                    "stimulus": dimension["test_intent"],
                    "expected_result": "Extract the exact expected result, preconditions, timing, and exceptions from the cited PCIe specification clause before implementation.",
                    "specification_source": source,
                    "specification_clause": clause,
                    "status": "proposal_requires_clause_review",
                })
        plan.append({
            "requirement_id": req.get("requirement_id"),
            "statement": statement,
            "specification_basis": {
                "source": source,
                "clause_or_section": clause,
                "revision": req.get("spec_revision") or "not supplied",
                "review_status": req.get("review_status", "needs_review"),
                "basis_note": "The plan is anchored to this extracted requirement. Clause context and revision must be confirmed; no missing PCIe rule or numeric limit is invented.",
            },
            "protocol_context": "PCIe (only when established by project/specification evidence)" if req.get("protocol_context") == "PCIe" else req.get("protocol_context", "not established"),
            "feature_evidence": req.get("feature_evidence", []),
            "rtl_evidence": req.get("rtl_evidence", []),
            "source_mapping_status": req.get("mapping_status", "not_mapped"),
            "implementation_assessment": "structural_evidence_found_not_functionally_proven" if mapped else "no_structural_match_or_not_mapped",
            "derived_test_dimensions": dimensions if approved else [],
            "proposed_scenarios": scenarios,
            "missing_inputs": [
                item for item, missing in [
                    ("Applicable PCIe specification revision", not req.get("spec_revision")),
                    ("Exact clause/section reference", not (req.get("clause") or req.get("section"))),
                    ("Reviewed and approved requirement wording", not approved),
                    ("Observable RTL signals and driver/consumer path", not bool(req.get("rtl_evidence") or req.get("feature_evidence"))),
                    ("Exact preconditions, limits, and timing from clause", True),
                ] if missing
            ],
            "plan_status": "draft_needs_engineer_review" if approved else "blocked_pending_requirement_approval",
            "execution_status": "not_generated_or_run",
            "verification_status": "not_verified",
        })
    return plan
