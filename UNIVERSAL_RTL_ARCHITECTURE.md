# Universal RTL architecture

Mverify is organized around a protocol-neutral design model. PCIe discovery is an optional extension; it is not the central architecture.

## Pipeline
1. Ingest project files, filelists, parameters and source files.
2. Parse supported Verilog/SystemVerilog declarations and structural evidence.
3. Build the Universal Design Model (UDM).
4. Classify design scope and candidate behaviors.
5. Build an adaptive verification plan.
6. Generate only artifacts supported by approved contracts and independent expected behavior.
7. Compile, simulate, inspect topology, and record measured results.

## UDM schema
`mverify.udm.v1` contains project identity, module inventory, candidate hierarchy, top-level interface, signal relationship candidates, design characteristics, evidence policy and analysis limits.

## Adaptive plan schema
`mverify.adaptive_plan.v1` contains selected architecture, rationale, topology recommendation, candidate tests, generation gates, evidence and unknowns.

## Architecture classes
- `combinational_unit`: compact stimulus, passive monitor, independent function model, scoreboard and coverage.
- `sequential_or_interface_block`: reset/state checks, monitor, and a driver only after contract review.
- `subsystem_or_soc`: agents at confirmed external boundaries, per-IP observation, models for confirmed interfaces, and coordinated scenarios only when cross-interface behavior requires them.
- `minimal_observation_first`: used when evidence is insufficient to infer a safe active interface.

These are planning classes, not claims that all corresponding UVM components are generated today.

## Evidence discipline
- Confirmed: parser-observed declarations and constructs.
- Inferred: likely roles based on patterns.
- Unknown: behavior that needs elaboration, design review, specification, or simulation.

## Future milestones
1. AST/elaboration-backed design graph and resolved instance connections.
2. Clock/reset and interface contract extraction.
3. Transaction models and independent reference-model generation.
4. Functional UVM drivers, sequencers, monitors and scoreboards.
5. Assertions, coverage and requirement traceability.
6. Simulator orchestration and failure diagnosis.
7. Multi-IP/SoC integration verification and CDC/formal integrations.
