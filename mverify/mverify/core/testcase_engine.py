"""Evidence-aware test generation: deterministic cases and clearly labelled suggestions."""
from __future__ import annotations
import re
from typing import Any

RESET_NAMES = {"rst", "rst_n", "reset", "reset_n", "aresetn", "areset"}

def _is_reset(name: str) -> bool:
    n=name.lower()
    return n in RESET_NAMES or n.endswith("_reset") or n.endswith("_rst_n")

def _signal_names(report: dict[str, Any]) -> set[str]:
    return {p.get("name", "").lower() for m in report.get("module_details", []) for p in m.get("ports", [])}

def generate_testcases(report: dict[str, Any], requirements: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return executable-intent candidates and advisory suggestions separately.

    Generated cases are structural stimulus/observation plans. They are not called
    functional checks unless a requirement/reference model provides an oracle.
    """
    requirements=requirements or []
    top_name=report.get("selected_top") or ((report.get("top_candidates") or [None])[0])
    top=next((m for m in report.get("module_details",[]) if m.get("name")==top_name),{})
    ports=top.get("ports",[])
    inputs=[p for p in ports if p.get("direction")=="input" and p.get("name") not in ("clk", "clock") and not _is_reset(p.get("name",""))]
    outputs=[p for p in ports if p.get("direction")=="output"]
    generated=[]
    if inputs:
        generated.append({"id":"GEN-RESET-001","name":"Reset and initialization observation","kind":"generated","category":"reset","stimulus":["Assert the identified reset input(s)","Hold reset for the configured reset interval","Release reset and observe output ports"],"checks":["Record output values after reset release","Flag unknown output values when the configured observation window expires"],"oracle":"structural_sanity_only","limitations":["Reset polarity and timing must be confirmed from RTL/specification before enabling automatic reset drive."]})
        generated.append({"id":"GEN-INPUT-002","name":"Input activity smoke test","kind":"generated","category":"input_activity","stimulus":["Apply bounded deterministic values to DUT input ports","Repeat with alternating bit patterns","Observe output ports on clock edges"],"checks":["Record sampled inputs and outputs","Flag unknown output values after reset"],"oracle":"structural_sanity_only","limitations":["No functional expected-value model is inferred from port names."]})
        generated.append({"id":"GEN-INPUT-003","name":"Input boundary-value sweep","kind":"generated","category":"boundary","stimulus":["Apply all-zero values","Apply all-one values","Apply alternating 1010 and 0101 patterns where widths permit"],"checks":["Record output observations and unknown-value checks"],"oracle":"structural_sanity_only","limitations":["Protocol legality and expected outputs require approved interface semantics."]})
    if outputs:
        generated.append({"id":"GEN-OBS-004","name":"Output observability test","kind":"generated","category":"observability","stimulus":["Apply the input activity smoke pattern"],"checks":["Capture all DUT output ports","Report outputs that remain unknown during the observation window"],"oracle":"structural_sanity_only","limitations":["A constant output may be legal; no stuck-at conclusion is made without a requirement."]})
    suggested=[]
    all_names=_signal_names(report)
    patterns=[
      (r"valid|ready", "Handshake backpressure", "Exercise valid without ready, ready without valid, and simultaneous assertion.", "Confirm the interface contract and hold/stability rules before approving."),
      (r"ack|nak|replay", "Acknowledgement and recovery", "Exercise acknowledgement, negative acknowledgement and recovery paths where present.", "Requires protocol-specific sequencing and exact specification rules."),
      (r"crc|lcrc|ecrc|parity", "Integrity error handling", "Exercise valid integrity data and controlled corruption if the interface permits it.", "Requires a trusted CRC model and defined error response."),
      (r"credit|fc_", "Flow-control boundaries", "Exercise available, exhausted and replenished resource conditions.", "Requires exact credit semantics and limits."),
      (r"fifo|full|empty", "Buffer boundary behaviour", "Exercise empty, one-entry, near-full and full conditions.", "Requires FIFO depth and acceptance semantics."),
      (r"grant|arb|request", "Arbitration contention", "Exercise single requester, simultaneous requesters, withdrawal and grant backpressure.", "Requires arbitration policy and fairness/weight rules."),
      (r"state|fsm|busy", "State transition coverage", "Exercise each discovered state and each legal transition condition.", "Requires reliable state extraction and reachable-state confirmation."),
    ]
    text=" ".join(all_names)
    for pat,name,stim,lim in patterns:
        if re.search(pat,text):
            suggested.append({"id":f"SUG-{len(suggested)+1:03d}","name":name,"kind":"suggested","category":"inferred_from_signal_names","stimulus":[stim],"checks":["Compare against approved specification behaviour and an independent reference model."],"oracle":"not_available_until_requirement_mapping","limitations":[lim]})
    for req in requirements:
        if (req.get("review_status") or "").lower()=="approved":
            rid=req.get("requirement_id") or f"REQ-{len(suggested)+1:03d}"
            statement=req.get("statement","")
            suggested.append({"id":f"{rid}-TC01","name":f"Requirement scenario: {rid}","kind":"suggested","category":"specification_derived","requirement_id":rid,"stimulus":[f"Exercise the condition stated by the approved requirement: {statement}"],"checks":["Check the exact expected result, timing and exceptions in the approved clause."],"oracle":"requires_requirement_oracle","limitations":["This is a scenario proposal. It is not executable until signals, preconditions and expected results are approved."]})
    return {"generated":generated,"suggested":suggested,"summary":{"generated_count":len(generated),"suggested_count":len(suggested),"functional_oracle_available":False,"note":"Generated structural tests are not protocol compliance tests. Suggested tests require engineer review and an expected-result oracle."}}
