"""Evidence-first engineering reasoning orchestration for local LLMs.

This module does not expose hidden chain-of-thought. It requests concise,
auditable conclusions, evidence, assumptions, risks and validation steps.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List
from mcore.core.ollama import OllamaClient
from mcore.reasoning.evaluation import validate_engineering_claims, downgrade_unsupported_claims

SYSTEM_POLICY = """
You are Mcore, a VLSI engineering reasoning assistant.
Work only from the CURRENT project's supplied RTL/specification/tool evidence and retrieved knowledge.
Never reuse facts, protocol assumptions, module names or conclusions from another project.
Do not assume the DUT is PCIe or any other standard protocol. The current project identity and top module are authoritative.
Answer the user's actual question. If asked for risks, give risks first; do not respond with a generic DUT-identification explanation.
Separate: confirmed_facts, inferences, assumptions, unknowns and recommendations.
Each item in claim arrays must be an object with claim, classification, evidence_ids, and reasoning fields.
classification must be CONFIRMED, INFERRED, UNKNOWN, or CONTRADICTED.
Use only exact evidence IDs present in the supplied evidence_context. CONFIRMED claims require evidence IDs.
Every RTL claim must cite evidence IDs, source file, module, symbol and line range when supplied.
Every standards claim must identify an exact source and revision when supplied.
Never invent clause numbers, signal semantics, timing limits or interface roles.
Do not claim code compiles unless compiler evidence is supplied.
Do not claim a requirement is verified unless executable passing evidence is supplied.
Give a concise decision rationale, not private chain-of-thought.
Return valid JSON only, with this schema:
{
  "design_understanding": [],
  "confirmed_facts": [],
  "inferences": [],
  "assumptions": [],
  "unknowns": [],
  "requirement_analysis": [],
  "verification_strategy": {
    "verification_level": [],
    "agents": [],
    "monitors": [],
    "reference_models": [],
    "scoreboards": [],
    "assertions": [],
    "coverage": [],
    "alternatives": [],
    "selection_rationale": ""
  },
  "risks": [],
  "validation_plan": [],
  "questions_for_engineer": [],
    "confidence": {"overall": 0.0, "basis": ""},
  "evidence_references": []
}
Confidence must be between 0 and 1. Empty arrays are valid. Do not fabricate detail.
"""

def _as_text(value: Any, max_chars: int = 50000) -> str:
    if isinstance(value, str):
        return value[:max_chars]
    return json.dumps(value, ensure_ascii=False, indent=2)[:max_chars]

def build_engineering_prompt(task: str, rtl_evidence=None, spec_evidence=None,
                             tool_evidence=None, retrieved_knowledge=None, project_context=None,
                             evidence_context=None) -> str:
    payload = {
        "task": task,
        "current_project_context": project_context or {},
        "rtl_evidence": rtl_evidence or {},
        "specification_evidence": spec_evidence or {},
        "tool_evidence": tool_evidence or {},
        "retrieved_knowledge": retrieved_knowledge or [],
        "evidence_context": evidence_context or {},
    }
    return SYSTEM_POLICY + "\n\nENGINEERING INPUT:\n" + _as_text(payload)

def validate_reasoning_result(result: Dict[str, Any]) -> List[str]:
    errors = []
    required = ["design_understanding", "confirmed_facts", "inferences",
                "assumptions", "unknowns", "requirement_analysis",
                "verification_strategy", "risks", "validation_plan",
                "questions_for_engineer", "confidence"]
    for key in required:
        if key not in result:
            errors.append("Missing required field: " + key)
    for section in ("design_understanding", "confirmed_facts", "inferences", "assumptions", "unknowns",
                    "requirement_analysis", "risks", "validation_plan", "questions_for_engineer"):
        values = result.get(section, [])
        if not isinstance(values, list):
            errors.append(section + " must be an array")
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                errors.append(f"{section}[{index}] must be a classified claim object")
                continue
            classification = str(item.get("classification", "")).upper()
            if classification not in {"CONFIRMED", "INFERRED", "UNKNOWN", "CONTRADICTED"}:
                errors.append(f"{section}[{index}].classification is invalid")
            if not isinstance(item.get("evidence_ids", []), list):
                errors.append(f"{section}[{index}].evidence_ids must be an array")
    if not isinstance(result.get("confidence"), dict):
        errors.append("confidence must be an object")
    else:
        score = result["confidence"].get("overall")
        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            errors.append("confidence.overall must be a number from 0 to 1")
    strategy = result.get("verification_strategy")
    if strategy is not None:
        for key in ["verification_level", "agents", "monitors",
                    "reference_models", "scoreboards", "assertions",
                    "coverage", "alternatives", "selection_rationale"]:
            if key not in strategy:
                errors.append("Missing verification_strategy." + key)
    return errors

class EngineeringReasoner:
    def __init__(self, client=None):
        self.client = client or OllamaClient()

    def reason(self, task, rtl_evidence=None, spec_evidence=None,
               tool_evidence=None, retrieved_knowledge=None, project_context=None,
               evidence_context=None):
        prompt = build_engineering_prompt(task, rtl_evidence, spec_evidence,
                                          tool_evidence, retrieved_knowledge, project_context,
                                          evidence_context=evidence_context)
        result = self.client.generate_json(prompt)
        errors = validate_reasoning_result(result)
        validation = validate_engineering_claims(result, (evidence_context or {}).get("evidence", []),
                                                  (evidence_context or {}).get("project_id", "")) if not errors else {
            "status": "ENGINEERING_REVIEW_REQUIRED", "claims": {"checked": 0, "supported": 0, "unsupported": 0,
            "contradicted": 0, "missing_evidence": 0}, "findings": [], "engineering_correctness": "NOT_PROVEN",
            "engineering_review_required": True, "validation_limitations": ["Response schema validation failed."]}
        safe_result = downgrade_unsupported_claims(result, validation)
        return {
            "result": safe_result,
            "schema_valid": not errors,
            "schema_errors": errors,
            "claim_validation": validation,
            "model": getattr(self.client, "model", "unknown"),
            "execution_status": "model_response_received",
            "validation_status": validation["status"] if not errors else "ENGINEERING_REVIEW_REQUIRED",
        }
