"""Deterministic evaluation helpers for Mcore outputs."""
from typing import Dict, Any, List

def evaluate_claim_ledger(result: Dict[str, Any], evidence_ids: List[str]):
    """Flag unsupported evidence references; does not prove claims true."""
    known = set(evidence_ids or [])
    findings = []
    for section in ("confirmed_facts", "requirement_analysis", "design_understanding"):
        for index, item in enumerate(result.get(section, []) or []):
            if not isinstance(item, dict):
                findings.append({"severity": "warning", "location": f"{section}[{index}]",
                                 "message": "Claim is not structured; provenance cannot be checked."})
                continue
            refs = item.get("evidence_ids", [])
            if not refs:
                findings.append({"severity": "warning", "location": f"{section}[{index}]",
                                 "message": "No evidence_ids supplied for this claim."})
            for ref in refs:
                if ref not in known:
                    findings.append({"severity": "error", "location": f"{section}[{index}]",
                                     "message": f"Unknown evidence reference: {ref}"})
    return {"findings": findings, "claim_count": sum(
        len(result.get(k, []) or []) for k in
        ("confirmed_facts", "requirement_analysis", "design_understanding")),
        "evidence_checked": True,
        "interpretation": "This checks provenance references only. It does not establish semantic correctness."}
