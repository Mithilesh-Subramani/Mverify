"""Technology-neutral verification planning from the Universal Design Model.

Plans are evidence-based recommendations. They do not claim executable stimulus
or correctness. Active stimulus is blocked until interface contracts are reviewed.
"""
from __future__ import annotations
from typing import Any


def _candidate_tests(features: set[str], sequential: bool, ports: list[dict[str, Any]]) -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    def add(key: str, purpose: str, oracle: str, evidence: str):
        tests.append({"id": key, "purpose": purpose, "oracle_needed": oracle, "basis": evidence,
                      "status": "plan_only_not_executable"})
    if not sequential:
        add("input_space", "Exercise representative input combinations and boundary values.",
            "Independent function/truth table or approved expected-value model.", "Combinational logic candidate")
        add("control_combinations", "Exercise each control/opcode/select combination.",
            "Approved operation semantics and expected output mapping.", "Control/comparison evidence")
    else:
        add("reset_initialization", "Check reset assertion, release and initial observable state.",
            "Confirmed reset polarity, synchrony and reset values.", "Sequential logic candidate")
        add("state_transition", "Exercise legal and boundary state transitions.",
            "Approved state-transition model or requirement-derived expectations.", "State/procedural evidence")
    if "buffering" in features or "memory_registers" in features:
        add("storage_boundaries", "Exercise empty/full, simultaneous access and boundary occupancy.",
            "Defined storage depth, latency, ordering and simultaneous read/write semantics.", "Storage feature candidate")
    if "arbitration" in features:
        add("contention_fairness", "Exercise simultaneous requesters, priority and starvation boundaries.",
            "Approved arbitration policy and fairness definition.", "Arbitration feature candidate")
    if "handshake" in features:
        add("handshake_backpressure", "Exercise acceptance, stalls and stable payload while waiting.",
            "Confirmed handshake event and payload stability contract.", "Handshake feature candidate")
    if "clock_domain" in features:
        add("clock_domain_interaction", "Review asynchronous crossings and reset interactions.",
            "Clock-domain map, synchronizer intent and CDC constraints.", "Clock-domain feature candidate")
    if "integrity_check" in features:
        add("integrity_fault_injection", "Exercise valid and corrupted integrity fields.",
            "Independent CRC/parity/checksum reference and error policy.", "Integrity feature candidate")
    if "counters_status" in features:
        add("counter_status_boundaries", "Exercise rollover, saturation and sticky status behavior.",
            "Specified counter width, update conditions and clear semantics.", "Counter/status feature candidate")
    if "retry_recovery" in features:
        add("recovery_paths", "Exercise retry, timeout and recovery paths.",
            "Approved retry policy, timer bounds and recovery state model.", "Retry/recovery feature candidate")
    if not tests:
        add("review_design_behavior", "Identify externally observable behavior and define directed tests.",
            "Engineer-approved interface contract and independent oracle.", "Insufficient semantic evidence")
    return tests


def plan_adaptive_verification(udm: dict[str, Any]) -> dict[str, Any]:
    top = udm.get("project", {}).get("selected_top") or "unknown"
    chars = udm.get("design_characteristics", {})
    features = set(chars.get("feature_candidates", []))
    ports = udm.get("top_interface", {}).get("ports", [])
    sequential = bool(chars.get("sequential_logic_candidate"))
    role = set(chars.get("top_level_role_candidates", []))
    hierarchy_count = udm.get("hierarchy", {}).get("instance_count", 0)
    scope = udm.get("design_scope", "unknown")
    if not sequential and hierarchy_count <= 2 and (
        "arithmetic_or_datapath_candidate" in role
        or (chars.get("combinational_logic_candidate") and not chars.get("state_machine_candidates"))
    ):
        architecture = "combinational_unit"
        topology = ["transaction_item (only if input/output contract is defined)", "directed or constrained stimulus source (after input mapping)",
                    "passive output monitor", "independent reference model", "scoreboard", "functional coverage"]
        rationale = "The selected top has combinational datapath evidence and no detected sequential process. A compact environment is preferred."
    elif scope == "multi_module_subsystem_or_soc_candidate" or hierarchy_count >= 8 or (
        hierarchy_count >= 1 and len(udm.get("modules", [])) >= 2
    ):
        architecture = "subsystem_or_soc"
        topology = ["one agent per confirmed external interface", "per-IP monitors where observability exists",
                    "memory/peripheral models only when interface contracts are known", "virtual-sequence coordinator when cross-interface scenarios are required",
                    "subsystem scoreboards and assertions", "integration coverage"]
        rationale = "The design has multi-module or multi-feature evidence. Partition verification by confirmed subsystem boundaries; do not create one agent per internal module automatically."
    elif features.intersection({"handshake", "buffering", "arbitration", "memory_registers"}) or sequential:
        architecture = "sequential_or_interface_block"
        topology = ["passive interface monitor", "driver/sequencer only after contract review", "independent reference model",
                    "scoreboard", "reset/state assertions", "functional coverage"]
        rationale = "Sequential or resource/interface behavior is indicated. Use the smallest environment that covers the observed boundary."
    else:
        architecture = "minimal_observation_first"
        topology = ["passive monitor", "engineer-reviewed stimulus mapping", "independent oracle", "scoreboard after oracle approval"]
        rationale = "Evidence is insufficient to safely infer an active interface. Begin with passive observation and contract definition."
    tests = _candidate_tests(features, sequential, ports)
    if architecture == "subsystem_or_soc":
        tests = [{
            "id": "subsystem_boundary_interactions",
            "purpose": "Identify and exercise externally observable interactions across confirmed child-IP boundaries.",
            "oracle_needed": "Resolved connectivity, interface contracts, address/interrupt relationships where applicable, and independent subsystem expectations.",
            "basis": "Multi-module hierarchy candidate; child-instance connectivity is not yet proven.",
            "status": "plan_only_not_executable",
        }]
    unknowns = []
    sig = udm.get("top_interface", {}).get("signal_relationship_candidates", {})
    if not sig.get("clock_candidates"): unknowns.append("No clock port candidate was identified; confirm clocking or combinational timing model.")
    if not sig.get("reset_candidates"): unknowns.append("No reset port candidate was identified; confirm whether reset is absent or named differently.")
    if not ports: unknowns.append("Top-level port declarations are unavailable or unresolved.")
    if sig.get("handshake_candidates", [{}])[0].get("paired"):
        unknowns.append("Valid/ready names co-occur, but direction, pairing, acceptance and stability semantics are not proven.")
    return {
        "schema": "mverify.adaptive_plan.v1", "dut_top": top, "architecture": architecture,
        "architecture_rationale": rationale, "topology_recommendation": topology,
        "candidate_tests": tests,
        "generation_gates": {
            "passive_monitor": "may_generate_from_parsed_port_declarations",
            "active_driver": "blocked_until_clock_reset_and_interface_contract_are_reviewed",
            "sequence": "blocked_until_transaction_fields_constraints_and_legal_timing_are_defined",
            "reference_model": "blocked_until_expected_behavior_is independently_defined_or_requirement_approved",
            "scoreboard": "may_generate_shell_only_until_independent_oracle_is_available",
            "assertions": "generate only from confirmed temporal and reset semantics",
            "coverage": "candidate coverpoints may be proposed; bins require reviewed semantic meaning",
        },
        "evidence": {"feature_candidates": sorted(features), "sequential_logic_candidate": sequential,
                     "hierarchy_instance_count": hierarchy_count, "top_port_count": len(ports),
                     "design_scope_candidate": scope, "top_roles": sorted(role)},
        "unknowns_and_review_items": unknowns + [
            "Static source evidence does not establish functional behavior.",
            "No active stimulus is authorized by signal names alone.",
            "Compile and simulation results are not available from this planning step.",
        ],
        "status": "adaptive_plan_generated_not_functionally_verified",
    }
