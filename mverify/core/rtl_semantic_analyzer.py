"""Conservative RTL semantic evidence analysis.

This is not a complete SystemVerilog elaborator. It extracts explicit procedural
assignments, continuous assignments, state-like case statements, and signal
read/write relationships from parsed module bodies. Every result is evidence,
not a functional correctness claim.
"""
from __future__ import annotations
import re

def _unique(items):
    return list(dict.fromkeys(items))

def analyze_module_semantics(module):
    body = module.get("body", "")
    ports = module.get("ports", [])
    port_names = [p.get("name", "") for p in ports]
    # Continuous and procedural LHS candidates. Deliberately conservative.
    writes = []
    for pat in (
        r"\bassign\s+([A-Za-z_$][\w$]*)\s*=",
        r"\b([A-Za-z_$][\w$]*)\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))",
        r"\bfor\s*\([^;]*;\s*([A-Za-z_$][\w$]*)\s*(?:<=|=)",
    ):
        writes.extend(re.findall(pat, body))
    writes = _unique(writes)
    identifiers = set(re.findall(r"\b[A-Za-z_$][\w$]*\b", body))
    reads = sorted(identifiers - set(writes))
    state_blocks = []
    for match in re.finditer(r"\bcase\s*\(\s*([A-Za-z_$][\w$]*)\s*\)(.*?)\bendcase\b", body, re.S):
        state_name, block = match.group(1), match.group(2)
        labels = _unique(re.findall(r"(?m)^\s*([A-Za-z_$][\w$]*|[0-9]+'[bBdDhHoO][0-9a-fA-F_xXzZ]+)\s*:", block))
        state_blocks.append({
            "selector": state_name,
            "case_labels": labels,
            "transition_targets": _unique(re.findall(r"\b"+re.escape(state_name)+r"\s*<=\s*([A-Za-z_$][\w$]*)", block)),
            "evidence": "case (" + state_name + ") ... endcase",
        })
    always_blocks = len(re.findall(r"\balways(?:_ff|_comb|_latch)?\b", body))
    continuous_assignments = re.findall(r"\bassign\s+([A-Za-z_$][\w$]*)\s*=\s*([^;]+);", body)
    return {
        "module": module.get("name"),
        "source_file": module.get("source_file"),
        "ports": [{"name": p.get("name"), "direction": p.get("direction"),
                   "width": p.get("width")} for p in ports],
        "procedural_block_count": always_blocks,
        "write_candidates": writes,
        "read_identifier_candidates": reads[:250],
        "continuous_assignments": [
            {"lhs": lhs, "rhs": " ".join(rhs.split())[:240]}
            for lhs, rhs in continuous_assignments
        ],
        "state_machine_candidates": state_blocks,
        "analysis_limitations": [
            "Identifier read/write sets are lexical candidates, not elaborated driver/consumer proof.",
            "Macros, generate branches, interfaces, structs, aliases, functions and tasks may affect interpretation.",
            "No simulation behavior or protocol correctness is proven."
        ],
    }

def analyze_semantics(module_details, hierarchy):
    modules = [analyze_module_semantics(m) for m in module_details]
    # Build a candidate signal graph only for names explicitly present in parent
    # and child port lists. It is not a resolved netlist.
    by_name = {m["module"]: m for m in modules}
    links = []
    for edge in hierarchy:
        parent = by_name.get(edge.get("parent"), {})
        child = by_name.get(edge.get("child"), {})
        parent_ports = {p["name"] for p in parent.get("ports", [])}
        child_ports = {p["name"] for p in child.get("ports", [])}
        shared = sorted(parent_ports & child_ports)
        links.append({**edge, "same_named_port_candidates": shared,
                      "connection_resolution": "candidate_only",
                      "note": "Actual instance connection expressions require full elaboration."})
    return {
        "analysis_method": "lexical semantic evidence extraction",
        "modules": modules,
        "hierarchy_connections": links,
        "limitations": [
            "This is deeper than keyword extraction but is not a full SystemVerilog AST or elaborated design.",
            "No claim of complete signal tracing, driver uniqueness, CDC correctness, or functional behavior.",
            "Use a standards-compliant frontend such as Surelog/slang for production-grade elaboration."
        ]
    }
