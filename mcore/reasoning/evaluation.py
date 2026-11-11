"""Evidence provenance and claim-quality checks for Mcore outputs.

These deterministic checks validate references, project ownership, structural
fact conflicts and evidence relevance. They cannot prove RTL semantics.
"""
from __future__ import annotations
import re
from typing import Dict, Any, List

_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9_$.-]{1,}")
_STOP = {"this", "that", "with", "from", "when", "then", "into", "will", "does", "have", "has", "the", "and", "for", "are", "was", "were", "not", "only", "must", "should", "claim", "evidence"}


def _claim_text(item: Any) -> str:
    if isinstance(item, str): return item
    if not isinstance(item, dict): return ""
    return " ".join(str(item.get(k, "")) for k in ("claim", "text", "statement", "requirement", "reasoning", "rationale"))


def _relevance(text: str, evidence: dict) -> float:
    claim_terms = {x.lower() for x in _WORD.findall(text)} - _STOP
    evidence_text = " ".join(str(evidence.get(k, "")) for k in ("content", "module", "symbol", "source", "fact_value"))
    evidence_terms = {x.lower() for x in _WORD.findall(evidence_text)}
    if not claim_terms: return 0.0
    overlap = len(claim_terms & evidence_terms) / len(claim_terms)
    # Exact module/symbol provenance carries weight in addition to text overlap.
    named = {str(evidence.get(k, "")).lower() for k in ("module", "symbol") if evidence.get(k)}
    named_hit = any(name in text.lower() for name in named)
    return min(1.0, overlap + (0.25 if named_hit else 0.0))


def validate_engineering_claims(result: Dict[str, Any], evidence: List[dict], project_id: str) -> dict:
    evidence_by_id = {x.get("id"): x for x in evidence if x.get("id")}
    findings = []
    counts = {"checked": 0, "supported": 0, "unsupported": 0, "contradicted": 0, "missing_evidence": 0}
    sections = ("confirmed_facts", "inferences", "assumptions", "unknowns", "requirement_analysis", "design_understanding", "risks", "recommended_actions")
    for section in sections:
        for index, claim in enumerate(result.get(section, []) or []):
            counts["checked"] += 1
            location = f"{section}[{index}]"
            if not isinstance(claim, dict):
                counts["unsupported"] += 1
                findings.append({"location": location, "status": "unsupported", "effective_classification": "UNKNOWN",
                                 "message": "Claim is not structured with classification and evidence references."})
                continue
            classification = str(claim.get("classification", "UNKNOWN")).upper()
            if classification not in {"CONFIRMED", "INFERRED", "UNKNOWN", "CONTRADICTED"}:
                classification = "UNKNOWN"
            refs = claim.get("evidence_ids", [])
            refs = refs if isinstance(refs, list) else []
            text = _claim_text(claim)
            cited = [evidence_by_id.get(ref) for ref in refs]
            missing = [ref for ref in refs if ref not in evidence_by_id]
            wrong_project = [ref for ref in refs if ref in evidence_by_id and evidence_by_id[ref].get("project_id") != project_id]
            scores = [_relevance(text, item) for item in cited if item and item.get("project_id") == project_id]
            relevance = max(scores, default=0.0)
            fact_keys = {item.get("fact_key") for item in cited if item and item.get("fact_key")}
            conflicts = []
            for fact_key in fact_keys:
                values = {str(item.get("fact_value")) for item in evidence if item.get("project_id") == project_id and item.get("fact_key") == fact_key}
                if len(values) > 1:
                    conflicts.append({"fact_key": fact_key, "values": sorted(values)})
            if conflicts:
                state = "contradicted"; effective = "CONTRADICTED"; counts["contradicted"] += 1
            elif not refs:
                state = "missing_evidence"; effective = "UNKNOWN"; counts["missing_evidence"] += 1
            elif missing or wrong_project or relevance < 0.10:
                state = "unsupported"; effective = "INFERRED" if not missing and not wrong_project else "UNKNOWN"
                counts["unsupported"] += 1
            else:
                state = "supported_reference"; effective = classification if classification != "CONTRADICTED" else "UNKNOWN"
                counts["supported"] += 1
            findings.append({"location": location, "claim": text, "declared_classification": classification,
                "effective_classification": effective, "status": state, "evidence_ids": refs,
                "unknown_evidence_ids": missing, "cross_project_evidence_ids": wrong_project,
                "relevance_score": round(relevance, 3), "potential_conflicts": conflicts})
    total = counts["checked"]
    if counts["unsupported"] or counts["missing_evidence"] or counts["contradicted"]:
        status = "ENGINEERING_REVIEW_REQUIRED"
    elif total and counts["supported"] == total:
        status = "EVIDENCE_VALIDATED"
    else:
        status = "SCHEMA_VALID"
    return {"status": status, "claims": counts, "findings": findings,
            "missing_evidence": counts["missing_evidence"],
            "unsupported_claims": counts["unsupported"], "contradicted_claims": counts["contradicted"],
            "validation_limitations": ["Evidence IDs and project ownership are deterministic checks.",
                "Relevance uses source metadata and token overlap; it is not semantic entailment or proof.",
                "Hardware behavior still requires engineer review and executable verification evidence."],
            "engineering_correctness": "NOT_PROVEN", "engineering_review_required": True}


def downgrade_unsupported_claims(result: Dict[str, Any], validation: dict) -> Dict[str, Any]:
    """Return a copy whose unsupported confirmed claims are downgraded explicitly."""
    import copy
    clean = copy.deepcopy(result)
    by_location = {x["location"]: x for x in validation.get("findings", [])}
    for section in ("confirmed_facts", "inferences", "assumptions", "unknowns", "requirement_analysis", "design_understanding", "risks", "recommended_actions"):
        for index, claim in enumerate(clean.get(section, []) or []):
            finding = by_location.get(f"{section}[{index}]")
            if isinstance(claim, dict) and finding and finding["status"] != "supported_reference":
                claim["classification"] = finding["effective_classification"]
                claim["validation_note"] = finding["status"]
    return clean

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
