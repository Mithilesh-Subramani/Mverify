# Mverify v0.8.0 — DUT-specific verification intelligence

## Changes
- Added `design_intelligence.py` to build a DUT-specific model from the current scan: selected top, parsed ports, candidate interface families, hierarchy children, state-machine evidence, detected features, and requirement mapping status.
- Added three architecture proposals: layered interface agents, a virtual-sequencer environment, and passive observation-first. Each option includes use conditions, agents, advantages, and risks.
- Added optional local Ollama reasoning through `http://localhost:11434/api/generate`. The prompt receives the local scan evidence and approved requirements. Ollama output is advisory; deterministic evidence remains visible, and unavailable Ollama falls back to deterministic analysis.
- Verification Intelligence now runs from the current DUT scan even when no requirement has been approved or mapped. It no longer relies only on a revision text field.
- Added architecture review/approval in the UI. The selected architecture is written to `APPROVED_ARCHITECTURE.json` and the generation manifest.
- Added a warning that a TLP/backend interface is not a serial PHY. PIPE/PHY stimulus is only applicable if that interface is actually present.
- Added tests for DUT model construction, architecture options, and DUT-specific analysis.

## Validation
- Python compileall: passed.
- Pytest: 32 passed, 3 existing deprecation warnings.
- VCS compile: not run. This environment does not have the user's Synopsys VCS installation.

## Important limitations
- Port grouping is candidate inference from names. It is not a SystemVerilog elaboration or protocol proof.
- Architecture approval records the topology decision. It does not yet activate pin-level drivers.
- Active PCIe stimulus requires a reviewed interface contract: signal role, direction, width, clock, reset polarity, handshake, packet encoding, and legal protocol behavior. A physical/PIPE agent cannot be inferred from a TLP-only DUT boundary.
- PCIe normative behavior must come from an imported, revision-matched specification and reviewed clause mapping. The local model must not invent missing timing or protocol values.
- This release is an intelligence and architecture-design upgrade, not a completed autonomous PCIe verification engine.
