# Mverify 0.13.0

## Universal RTL foundation

- Added `mverify.core.universal_design_model` with UDM schema `mverify.udm.v1`.
- Added `mverify.core.adaptive_verification` with adaptive plan schema `mverify.adaptive_plan.v1`.
- Integrated both outputs into every RTL scan report and the desktop Analysis view.
- Included the UDM and adaptive plan in DUT intelligence evidence passed to optional local Ollama reasoning.
- Added regression tests for combinational ALU, FIFO, arbiter, and hierarchical subsystem examples.
- Kept protocol-specific discovery as an optional extension.

## Boundaries

- The UDM uses the existing lightweight Verilog/SystemVerilog parser.
- Signal naming and lexical constructs are candidate evidence, not semantic proof.
- Active UVM generation remains gated and the existing generator remains passive.
- This release does not claim complete VHDL parsing, SoC verification, formal verification, CDC signoff, or simulation success.
