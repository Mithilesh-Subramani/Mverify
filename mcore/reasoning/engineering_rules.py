"""Versioned, evidence-oriented starter rule catalogue.

These are internal engineering checks, not a replacement for licensed IEEE/
Accellera standards or simulator diagnostics. Rules are deliberately scoped.
"""
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass(frozen=True)
class EngineeringRule:
    rule_id: str
    domain: str
    title: str
    description: str
    severity: str
    applicability: str
    validation_method: str
    source_status: str = "internal_guideline"
    standard_reference: Optional[str] = None

    def as_dict(self):
        return asdict(self)

RULES = [
    EngineeringRule("SV-PKG-001", "systemverilog", "Package dependency order",
        "A package must be compiled before source files that import it.",
        "error", "Compilation units with package imports",
        "Compile-filelist dependency analysis", "language_tooling_rule"),
    EngineeringRule("SV-IF-001", "systemverilog", "Interface/modport consistency",
        "Virtual-interface declarations and modport usage must match the interface definition.",
        "error", "Designs or testbenches that use interfaces",
        "Parser plus simulator compilation", "methodology_check"),
    EngineeringRule("UVM-COMP-001", "uvm", "Component construction",
        "UVM components should be constructed through the component hierarchy and use the parent/name constructor pattern.",
        "warning", "UVM component classes",
        "AST/lint plus simulator compilation", "uvm_methodology_guideline"),
    EngineeringRule("UVM-PHASE-001", "uvm", "Phase objection balance",
        "Run-phase objections must be raised and dropped on all intended completion paths.",
        "warning", "Tests or sequences that control phase completion",
        "Static control-flow review plus simulation timeout checks", "uvm_methodology_guideline"),
    EngineeringRule("UVM-TLM-001", "uvm", "TLM connection compatibility",
        "Connected TLM endpoints must have compatible transaction types and connection directions.",
        "error", "Analysis, put, get and transport TLM connections",
        "Type-aware topology validation plus simulator elaboration", "uvm_methodology_guideline"),
    EngineeringRule("UVM-VIF-001", "uvm", "Virtual interface configuration",
        "A virtual interface must be configured and retrieved using a matching type and configuration path.",
        "error", "Agents with virtual interfaces",
        "Configuration-path/type check plus simulation", "uvm_methodology_guideline"),
    EngineeringRule("VERIF-EVID-001", "verification", "Requirement evidence",
        "A requirement must not be marked verified without an executable check and passing evidence.",
        "error", "Requirement status tracking",
        "Evidence ledger validation", "mverify_evidence_policy"),
    EngineeringRule("VERIF-UNC-001", "verification", "Uncertainty disclosure",
        "Inferred protocol semantics must be marked as hypotheses until confirmed by specification or engineer review.",
        "warning", "Incomplete or custom DUT descriptions",
        "Provenance and confidence validation", "mverify_evidence_policy"),
]

def list_rules(domain=None):
    return [r.as_dict() for r in RULES if domain is None or r.domain == domain]

def get_rule(rule_id):
    for rule in RULES:
        if rule.rule_id == rule_id:
            return rule.as_dict()
    return None
