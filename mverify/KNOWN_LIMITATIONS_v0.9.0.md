# Known limitations — Mverify 0.9.0

1. The RTL frontend is still the existing lightweight structural parser. It is not a complete SystemVerilog elaborator. Surelog/UHDM integration remains a planned engineering task.
2. The project scanner now records common `.f` filelist sources, include directories and defines. It still scans discovered RTL files recursively and does not yet reproduce every VCS option or library-resolution rule.
3. Generated UVM now contains bounded structural stimulus, monitor sampling, a connected scoreboard, observation counters, unknown-sample checks and a running base test. It does not contain a universal functional reference model. No generic tool can infer correct expected outputs from arbitrary port names alone.
4. Structural smoke stimulus drives the same 32-bit random value to non-reset inputs within each interface group. This is useful for basic activity checks only. It may be illegal for a protocol. Review and replace it with interface-specific sequences before functional verification.
5. The monitor samples one representative output per interface group. Full signal-level transaction decoding and protocol-specific scoreboarding are not yet implemented.
8. Qwen through Ollama is an advisory teacher/reasoning model. It does not automatically update model weights. Fine-tuning requires a separate compatible training toolchain, approved data and evaluation.
9. No VCS compile or simulation was run for this package in the build environment. The generated UVM was inspected through Python tests and a synthetic valid RTL fixture only.
10. The four PCIe source files supplied with this conversation currently begin with `module #(` (no module identifier before the parameter list). The lightweight parser therefore extracts zero modules from those files. Confirm the original source declarations and compile them with VCS before using them as a benchmark. Mverify does not silently repair source RTL.
