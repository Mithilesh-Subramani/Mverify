# Mverify v0.10.0

## Implemented in this release
- Compile-filelist-first RTL source selection, with recursive discovery retained as fallback.
- Optional Surelog parse/elaboration invocation with saved log and explicit availability/status reporting.
- Conservative DUT design graph for modules, ports, instance relationships and FSM candidates.
- Deterministic runtime event-trace comparison and signal-sample summaries.

## Still not claimed
- A complete SystemVerilog semantic frontend is available only when Surelog is installed; the graph still uses conservative extracted data.
- No full UHDM graph importer is included.
- No automatic, correct reference model can be inferred for arbitrary DUTs.
- Generated UVM is structural and must not be described as protocol-functional until an approved oracle and interface model are attached.
- No VCS/Verdi execution was possible in this build environment.
