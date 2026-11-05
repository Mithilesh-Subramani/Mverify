"""Feature-centric RTL analysis.

This is a conservative static-analysis pass. It discovers candidate design
features from structure, procedural logic, state, and signal relationships.
It does not prove that a feature is functionally correct.
"""
from __future__ import annotations
import re
from pathlib import Path

PATTERNS = [
    ("clock_reset", "Clock and reset control", [
        r"\bposedge\s+\w+", r"\bnegedge\s+\w+", r"\b(?:rst|reset)[A-Za-z0-9_$]*\b"]),
    ("handshake", "Ready/valid or request/response handshake", [
        r"\b\w*valid\w*\b", r"\b\w*ready\w*\b",
        r"\b\w*(?:req|request|rsp|response|ack)\w*\b"]),
    ("state_machine", "State machine / control sequencing", [
        r"\btypedef\s+enum\b", r"\blocalparam\b[^;]*(?:IDLE|WAIT|SEND|CALC|STATE)",
        r"\bcase\s*\(\s*\w*(?:state|fsm)\w*\s*\)", r"\b\w*(?:state|fsm)\w*\s*<="]),
    ("buffering", "FIFO, queue, or buffering", [
        r"\b(?:fifo|queue|buffer|skid|elastic)\w*\b",
        r"\b(?:wr|rd|write|read)_(?:ptr|pointer|count)\b",
        r"\bfull\b", r"\balmost_full\b", r"\bempty\b"]),
    ("arbitration", "Arbitration or scheduling", [
        r"\b(?:arb|arbit|grant|priority|round_robin|rr|wrr|weighted)\w*\b",
        r"\brequest_vector\b", r"\bgrant_vector\b"]),
    ("integrity_check", "CRC, parity, or integrity checking", [
        r"\bcrc[A-Za-z0-9_$]*\b", r"\blcrc\b", r"\becrc\b", r"\bparity\b",
        r"\bsyndrome\b", r"\bchecksum\b"]),
    ("retry_recovery", "Retry, replay, timeout, or recovery", [
        r"\b(?:retry|replay|nak|timeout|watchdog|recovery)\w*\b",
        r"\b(?:timer|retry|replay)_?(?:count|counter|limit)\b"]),
    ("credit_flow", "Credit-based flow control or resource accounting", [
        r"\b(?:credit|credits|fc_)\w*\b", r"\bavailable_credits\b",
        r"\bcredit_count\b"]),
    ("packet_formatting", "Packet/header/payload formatting or parsing", [
        r"\b(?:packet|header|payload|descriptor|tlp|dllp)\w*\b",
        r"\b(?:opcode|length|tag|byte_enable|first_be|last_be)\b"]),
    ("data_path", "Data movement, transformation, or width adaptation", [
        r"\b(?:data|payload|word|dw|byte)_?(?:in|out|i|o|next|reg)\b",
        r"\[[0-9]+\s*:\s*0\]", r"\b(?:shift|rotate|align|extract|merge)\w*\b"]),
    ("counters_status", "Counters, status, and diagnostics", [
        r"\b\w*(?:count|counter|status|error|overflow|underflow|debug)\w*\b",
        r"\b(?:sat|saturat)\w*\b"]),
    ("memory_registers", "Memory, register, or lookup-table access", [
        r"\b(?:mem|memory|ram|rom|regfile|register_file|lut|table)\w*\b",
        r"\[[^]\n]*\]\s*(?:<=|=)"]),
    ("parameterization", "Parameterized or configurable behavior", [
        r"\bparameter\b", r"\blocalparam\b", r"\bifdef\b", r"\bifndef\b"]),
    ("backend_interface", "Backend or external service interface", [
        r"\b(?:backend|dma|memory|host|completion|completer)_?\w*\b"]),
    ("clock_domain", "Clock-domain crossing or synchronization", [
        r"\b(?:sync|synchronizer|cdc|async_fifo|gray_code)\w*\b",
        r"\b(?:sync[12]|meta| metastability)\b"]),
]

def _evidence(module, source, patterns):
    body = module.get("body", "")
    ports = module.get("ports", [])
    port_text = " ".join(p.get("name", "") for p in ports)
    hits = []
    for pattern in patterns:
        match = re.search(pattern, body, re.I)
        where = "module body"
        sample = ""
        if match:
            sample = body[max(0, match.start()-65):min(len(body), match.end()+85)].strip()
        else:
            match = re.search(pattern, port_text, re.I)
            if match:
                where = "module ports"
                sample = match.group(0)
        if match:
            hits.append({"pattern": pattern, "location": where,
                         "evidence": " ".join(sample.split())[:180]})
    return hits

def analyze_features(report: dict) -> dict:
    modules = report.get("module_details", [])
    features = []
    for key, label, patterns in PATTERNS:
        module_hits = []
        for module in modules:
            hits = _evidence(module, report.get("_source_text", ""), patterns)
            if hits:
                module_hits.append({
                    "module": module.get("name", "unknown"),
                    "source_file": module.get("source_file", ""),
                    "evidence": hits[:5],
                })
        if module_hits:
            evidence_count = sum(len(x["evidence"]) for x in module_hits)
            confidence = "high" if len(module_hits) >= 2 or evidence_count >= 3 else "medium"
            features.append({
                "feature_id": key, "feature": label,
                "status": "candidate_feature_detected",
                "confidence": confidence,
                "modules_involved": [x["module"] for x in module_hits],
                "evidence_count": evidence_count,
                "evidence": module_hits,
                "interpretation": "Static RTL evidence found. Functional behavior and correctness require simulation or deeper analysis.",
            })
    # Capture module-level inventory even if no feature pattern matched.
    return {
        "analysis_method": "feature-centric static RTL evidence analysis",
        "features": features,
        "module_inventory": [{
            "module": m.get("name"),
            "source_file": m.get("source_file"),
            "ports": len(m.get("ports", [])),
            "port_names": [p.get("name") for p in m.get("ports", [])],
        } for m in modules],
        "coverage_note": "Feature candidates are discovered from signal names and RTL constructs. This is broader than protocol-layer classification, but it is not a complete SystemVerilog semantic analysis. Unusual coding styles, macros, interfaces, generate branches, and indirect logic can hide features.",
        "next_analysis": [
            "Resolve each candidate through its driver, consumer, and hierarchy connections.",
            "Trace state transitions and data/control dependencies.",
            "Compare feature behavior with specification requirements.",
            "Confirm behavior with directed simulation, assertions, and coverage.",
        ],
    }
