"""Evidence-first engineering reasoning orchestration for local LLMs.

This module does not expose hidden chain-of-thought. It requests concise,
auditable conclusions, evidence, assumptions, risks and validation steps.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List
from mcore.core.ollama import OllamaClient

SYSTEM_POLICY = """
You are Mcore, a VLSI engineering reasoning assistant.
Work only from supplied RTL/specification/tool evidence and retrieved knowledge.
Do not assume the DUT is PCIe or any other standard protocol.
Separate: confirmed_facts, inferences, assumptions, unknowns and recommendations.
Every RTL claim must identify a source file and line/symbol when supplied.
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
  "confidence": {"overall": 0.0, "basis": ""}
}
Confidence must be between 0 and 1. Empty arrays are valid. Do not fabricate detail.
"""

def _as_text(value: Any, max_chars: int = 50000) -> str:
    if isinstance(value, str):
        return value[:max_chars]
    return json.dumps(value, ensure_ascii=False, indent=2)[:max_chars]

def build_engineering_prompt(task: str, rtl_evidence=None, spec_evidence=None,
                             tool_evidence=None, retrieved_knowledge=None) -> str:
    payload = {
        "task": task,
        "rtl_evidence": rtl_evidence or {},
        "specification_evidence": spec_evidence or {},
        "tool_evidence": tool_evidence or {},
        "retrieved_knowledge": retrieved_knowledge or [],
    }
    return SYSTEM_POLICY + "\\n\\nENGINEERING INPUT:\\n" + _as_text(payload)

def validate_reasoning_result(result: Dict[str, Any]) -> List[str]:
    errors = []
    required = ["design_understanding", "confirmed_facts", "inferences",
                "assumptions", "unknowns", "requirement_analysis",
                "verification_strategy", "risks", "validation_plan",
                "questions_for_engineer", "confidence"]
    for key in required:
        if key not in result:
            errors.append("Missing required field: " + key)
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
               tool_evidence=None, retrieved_knowledge=None):
        prompt = build_engineering_prompt(task, rtl_evidence, spec_evidence,
                                          tool_evidence, retrieved_knowledge)
        result = self.client.generate_json(prompt)
        errors = validate_reasoning_result(result)
        return {
            "result": result,
            "schema_valid": not errors,
            "schema_errors": errors,
            "model": getattr(self.client, "model", "unknown"),
            "execution_status": "model_response_received",
            "validation_status": "schema_only_not_engineering_validation",
        }
