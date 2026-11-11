"""Universal Design Model (UDM) builder for technology-neutral RTL evidence.

The UDM is a normalized, evidence-labelled intermediate representation. It is
built from Mverify's lightweight Verilog/SystemVerilog parser and therefore
never claims full elaboration or functional proof. VHDL inventory is retained
by the project scanner, but VHDL semantic extraction is not implemented here.
"""
from __future__ import annotations
import re
from collections import Counter
from typing import Any

IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"


def _signals(body: str, ports: list[dict[str, Any]]) -> dict[str, Any]:
    names = [str(p.get("name", "")) for p in ports]
    low = {n: n.lower() for n in names}
    clocks = [n for n in names if re.search(r"(^|_)(clk|clock)(_|$)|clk$|clock$", low[n])]
    resets = [n for n in names if re.search(r"(^|_)(rst|reset)(_|$)|rst_n$|reset_n$", low[n])]
    valid = [n for n in names if re.search(r"(^|_)(valid|vld)(_|$)|valid$", low[n])]
    ready = [n for n in names if re.search(r"(^|_)(ready|rdy)(_|$)|ready$", low[n])]
    req = [n for n in names if re.search(r"(^|_)(req|request)(_|$)|req$", low[n])]
    rsp = [n for n in names if re.search(r"(^|_)(rsp|response|ack)(_|$)|rsp$", low[n])]
    memory = [n for n in names if re.search(r"mem|ram|rom|fifo|queue|buffer|addr|wdata|rdata", low[n])]
    interrupts = [n for n in names if re.search(r"irq|interrupt", low[n])]
    return {
        "clock_candidates": [{"name": n, "evidence": "port-name pattern", "confidence": "candidate"} for n in clocks],
        "reset_candidates": [{"name": n, "evidence": "port-name pattern", "confidence": "candidate"} for n in resets],
        "handshake_candidates": [{"kind": "valid_ready", "valid_candidates": valid, "ready_candidates": ready,
                                  "paired": bool(valid and ready), "evidence": "co-occurring port names; pairing not proven"}],
        "request_response_candidates": [{"request_candidates": req, "response_candidates": rsp,
                                          "evidence": "port-name pattern; protocol semantics not proven"}],
        "memory_related_ports": memory,
        "interrupt_candidates": interrupts,
    }


def _module_record(module: dict[str, Any], semantic_by: dict[str, dict[str, Any]], feature_by_module: dict[str, list[str]]) -> dict[str, Any]:
    name = module.get("name", "unknown")
    body = module.get("body", "")
    ports = module.get("ports", [])
    sem = semantic_by.get(name, {})
    identifiers = set(re.findall(rf"\b{IDENT}\b", body))
    memory_decl = bool(re.search(r"\b(reg|logic|bit)\s*(?:\[[^]]+\]\s*)?\w+\s*\[[^]]+\]", body))
    arithmetic = bool(re.search(r"(?<![=!<>])(?:\+|\-|\*|/|%)(?![=>])", body))
    comparisons = bool(re.search(r"(?:==|!=|<=|>=|<|>)", body))
    mux_case = bool(re.search(r"\bcase[xz]?\s*\(", body))
    always_ff = len(re.findall(r"\balways_ff\b", body))
    always_comb = len(re.findall(r"\balways_comb\b", body))
    always_latch = len(re.findall(r"\balways_latch\b", body))
    always_legacy = len(re.findall(r"\balways\s*@", body))
    procedural = always_ff + always_comb + always_latch + always_legacy
    state = sem.get("state_machine_candidates", [])
    features = list(feature_by_module.get(name, []))
    # Remove common lexical false positives: a packed bit-select is not, by
    # itself, evidence of a memory; request/grant arbitration is not a
    # ready/valid stream handshake.
    if not memory_decl:
        features = [x for x in features if x != "memory_registers"]
    port_lows = [str(p.get("name", "")).lower() for p in ports]
    has_valid = any(re.search(r"(^|_)(valid|vld)(_|$)|valid$", n) for n in port_lows)
    has_ready = any(re.search(r"(^|_)(ready|rdy)(_|$)|ready$", n) for n in port_lows)
    if not (has_valid and has_ready):
        features = [x for x in features if x != "handshake"]
    roles = []
    if arithmetic: roles.append("arithmetic_or_datapath_candidate")
    if comparisons: roles.append("comparison_or_control_candidate")
    if mux_case: roles.append("selection_or_fsm_candidate")
    if memory_decl or any(x in features for x in ("buffering", "memory_registers")):
        roles.append("storage_or_buffer_candidate")
    if state: roles.append("state_machine_candidate")
    if any(p.get("direction") == "input" for p in ports) and any(p.get("direction") == "output" for p in ports):
        roles.append("input_output_transform_candidate")
    return {
        "name": name, "source_file": module.get("source_file", ""), "port_style": module.get("port_style", "unknown"),
        "ports": [{k: p.get(k) for k in ("name", "direction", "width", "declaration")} for p in ports],
        "port_count": len(ports), "procedural_constructs": {
            "always_ff": always_ff, "always_comb": always_comb, "always_latch": always_latch,
            "legacy_always_at": always_legacy, "total_candidate_blocks": procedural},
        "state_machine_candidates": state,
        "feature_candidates": features,
        "behavioral_role_candidates": roles,
        "operator_evidence": {"arithmetic_operator_present": arithmetic, "comparison_operator_present": comparisons,
                              "case_statement_present": mux_case},
        "identifier_count": len(identifiers),
        "evidence_status": "static_source_evidence_not_elaborated_behavior",
    }


def build_universal_design_model(module_details: list[dict[str, Any]], hierarchy: list[dict[str, Any]] | None = None,
                                 semantic_analysis: dict[str, Any] | None = None,
                                 feature_analysis: dict[str, Any] | None = None,
                                 selected_top: str | None = None,
                                 project_dir: str = "") -> dict[str, Any]:
    """Build UDM from parsed modules. Input module dicts may include parser-only body."""
    hierarchy = hierarchy or []
    semantic_analysis = semantic_analysis or {}
    feature_analysis = feature_analysis or {}
    semantic_by = {x.get("module"): x for x in semantic_analysis.get("modules", [])}
    feature_by_module: dict[str, list[str]] = {}
    for feat in feature_analysis.get("features", []):
        key = feat.get("feature_id", feat.get("feature", "unknown"))
        for item in feat.get("evidence", []):
            feature_by_module.setdefault(item.get("module", ""), []).append(key)
    records = [_module_record(m, semantic_by, feature_by_module) for m in module_details]
    names = {m.get("name") for m in module_details}
    instantiated = {e.get("child") for e in hierarchy}
    tops = sorted(x for x in names if x and x not in instantiated)
    if selected_top not in names:
        selected_top = tops[0] if len(tops) == 1 else None
    top_src = next((m for m in module_details if m.get("name") == selected_top), {})
    top_ports = top_src.get("ports", [])
    top_body = top_src.get("body", "")
    top_sem = semantic_by.get(selected_top, {})
    feature_ids = sorted({x for record in records for x in record.get("feature_candidates", [])})
    counts = Counter(p.get("direction", "unknown") for p in top_ports)
    return {
        "schema": "mverify.udm.v1",
        "project": {"root": project_dir, "selected_top": selected_top, "module_count": len(records)},
        "design_scope": "single_ip_or_subsystem_candidate" if len(records) < 12 else "multi_module_subsystem_or_soc_candidate",
        "modules": records,
        "hierarchy": {"instances": hierarchy, "instance_count": len(hierarchy), "top_candidates": tops,
                      "connectivity_status": "candidate_hierarchy_only_unless_elaborator_resolves_connections"},
        "top_interface": {"ports": [{k: p.get(k) for k in ("name", "direction", "width", "declaration")} for p in top_ports],
                           "port_count": len(top_ports), "direction_counts": dict(counts),
                           "signal_relationship_candidates": _signals(top_body, top_ports)},
        "design_characteristics": {"feature_candidates": feature_ids,
                                   "state_machine_candidates": top_sem.get("state_machine_candidates", []),
                                   "procedural_block_count": top_sem.get("procedural_block_count", 0),
                                   "top_level_role_candidates": next((r["behavioral_role_candidates"] for r in records if r["name"] == selected_top), []),
                                   "sequential_logic_candidate": bool(
                                       re.search(r"\balways_ff\b|\balways\s*@\s*\([^)]*(?:posedge|negedge)", top_body)
                                       or any(x.get("transition_targets") for x in top_sem.get("state_machine_candidates", []))
                                   ),
                                   "combinational_logic_candidate": bool(re.search(r"\bassign\b|\balways_comb\b", top_body))},
        "evidence_policy": {"confirmed": "Only parser-observed declarations and source constructs are confirmed as source evidence.",
                            "inferred": "Signal roles, clocks, resets, interfaces and block functions are candidates, not proven semantics.",
                            "unknown": "Resolved connectivity, elaborated parameter values, complete dataflow, CDC safety and functional behavior require stronger tools or review."},
        "analysis_limits": [
            "The current frontend is a lightweight Verilog/SystemVerilog parser, not a complete IEEE SystemVerilog elaborator.",
            "Port-name patterns are candidate evidence and do not prove protocol or clock/reset semantics.",
            "Instance hierarchy does not prove resolved port-to-expression connectivity.",
            "VHDL files may be inventoried, but VHDL semantic parsing is not implemented in this release.",
            "No functional correctness, timing closure, CDC safety or specification compliance is proven.",
        ],
    }
