# Mcore v0.3.0 — Engineering Reasoning Foundation

## Purpose
This release adds an evidence-first engineering reasoning API. It is a foundation,
not a trained VLSI foundation model and not proof of correct hardware reasoning.

## New capabilities
- Structured engineering prompt for RTL, specification, tool and retrieved evidence.
- DUT-agnostic reasoning policy. The model must not assume PCIe or another protocol.
- Structured result contract: facts, inferences, assumptions, unknowns, requirement
  analysis, verification strategy, risks, validation plan and confidence.
- Output schema validation.
- Initial internal SV/UVM/verification rule catalogue with explicit provenance labels.
- Evidence-reference checker. It checks IDs, not semantic truth.
- New API routes: GET /rules, POST /reason/engineering, POST /reason/evaluate.

## API examples

`GET http://127.0.0.1:8765/rules?domain=uvm`

`POST /reason/engineering`
```json
{
  "task": "Propose a verification strategy for this DUT",
  "rtl_evidence": {"top_module": "my_controller", "evidence": []},
  "spec_evidence": {"requirements": []},
  "tool_evidence": {"parser_status": "not_run"},
  "model": "qwen2.5-coder:7b"
}
```

`POST /reason/evaluate`
```json
{
  "result": {"confirmed_facts": [{"evidence_ids": ["rtl:top:1-20"]}]},
  "evidence_ids": ["rtl:top:1-20"]
}
```

## Important limits
- No model weights were trained in this release.
- The rule catalogue is an initial internal checklist. It is not the full IEEE 1800
  or Accellera UVM standard and does not claim exact clause coverage.
- The reasoner schema validates output shape, not correctness.
- Evidence ID validation checks provenance references, not whether a claim follows
  logically from the evidence.
- No native SystemVerilog AST, full elaboration, formal proof or simulator compile
  is added by this release.
- Ollama must be installed and a compatible model must be pulled separately.
- Do not mark generated UVM as valid until a supported simulator compiles and runs it.

## Next milestones
1. Add real SV parser/elaborator-backed evidence objects.
2. Add standard-versioned rule packs with exact licensed references.
3. Add task-specific reasoning evaluations and a curated gold dataset.
4. Add architecture model validation before UVM generation.
5. Add compile/test feedback loops with bounded repair attempts.
