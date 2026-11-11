from mcore.reasoning.engineering_reasoner import (
    build_engineering_prompt, validate_reasoning_result
)
from mcore.reasoning.engineering_rules import list_rules, get_rule
from mcore.reasoning.evaluation import evaluate_claim_ledger

def test_prompt_requires_evidence_and_no_protocol_assumption():
    p = build_engineering_prompt("Analyse custom RTL", rtl_evidence={"top":"custom_top"})
    assert "Do not assume the DUT is PCIe" in p
    assert "tool_evidence" in p

def test_reasoning_schema_rejects_missing_fields():
    assert validate_reasoning_result({})

def test_reasoning_schema_accepts_complete_shape():
    result = {
        "design_understanding": [], "confirmed_facts": [], "inferences": [],
        "assumptions": [], "unknowns": [], "requirement_analysis": [],
        "verification_strategy": {
            "verification_level": [], "agents": [], "monitors": [],
            "reference_models": [], "scoreboards": [], "assertions": [],
            "coverage": [], "alternatives": [], "selection_rationale": ""
        },
        "risks": [], "validation_plan": [], "questions_for_engineer": [],
        "confidence": {"overall": 0.5, "basis": "limited evidence"}
    }
    assert validate_reasoning_result(result) == []

def test_rules_are_traceable_and_domain_filterable():
    assert get_rule("UVM-TLM-001")["domain"] == "uvm"
    assert all(r["domain"] == "uvm" for r in list_rules("uvm"))

def test_claim_ledger_flags_unknown_evidence():
    result = {"confirmed_facts": [{"evidence_ids": ["bad-id"]}]}
    report = evaluate_claim_ledger(result, ["rtl:top.sv:1-20"])
    assert report["findings"][0]["severity"] == "error"
