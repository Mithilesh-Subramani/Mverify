# Known limitations — v0.10.0

1. The built-in RTL parser is a lightweight structural parser. Surelog is invoked when installed and when a usable `.f` filelist exists. This release does not parse UHDM into a complete semantic graph.
2. The design graph contains module, port, instance and lexical FSM-candidate relationships. It does not prove all signal drivers, full dataflow, CDC, protocol semantics or reachability.
3. Runtime event-trace analysis compares explicit named events and only checks timing when a numeric maximum is supplied. It does not automatically decode VCD/FSDB waveforms or infer specification timing.
4. Generated UVM remains a structural smoke scaffold. Its scoreboard records observations and unknown-value samples. It is not an independent functional reference model for arbitrary DUTs.
5. No protocol-specific legal PCIe transaction model is generated automatically. The engineer must provide or approve interface semantics and expected results.
6. VCS and Verdi were not available in the build environment. Generated SystemVerilog was not compiled or simulated here.
