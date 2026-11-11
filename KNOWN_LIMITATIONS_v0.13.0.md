# Known limitations — Mverify 0.13.0

## Universal Design Model
- The UDM is built from the lightweight Verilog/SystemVerilog parser. It is not a complete IEEE SystemVerilog AST or elaborator.
- Instance hierarchy is candidate evidence. Port-to-expression connections are not fully resolved.
- Clock, reset, valid/ready, request/response, memory and interrupt roles are candidates based on names and source patterns. They are not protocol contracts.
- State-machine candidates can include ordinary case-based combinational selection. Sequential classification uses edge-sensitive constructs and candidate state updates, but still requires review.
- VHDL files can be inventoried; VHDL semantic analysis is not implemented.

## Adaptive verification planning
- The planner selects a verification strategy and proposes test intents. It does not generate executable functional tests.
- Driver generation remains blocked until clock/reset and interface contracts are reviewed.
- A scoreboard shell is not a functional scoreboard. A functional scoreboard needs an independent oracle.
- Assertions and coverage require confirmed temporal semantics and meaningful coverage models.

## SoC scope
- Multi-module hierarchy is identified as a subsystem/SoC candidate. The current tool does not prove IP integration correctness, address-map correctness, bus connectivity, interrupt routing, CDC safety, coherency, or end-to-end SoC behavior.

## Tool execution
- Surelog and other external tools are optional. Their availability does not imply full language support or successful elaboration.
- Compile and simulation must be performed with the target simulator. Mverify does not claim simulation success unless a result is actually collected.
