# Mverify 0.15.0

- Added contract-gated active UVM generation for the included `pcie_wrr_arbiter` RTL: sequencer, driver, monitor, reset sequence, independent quota reference model, functional scoreboard, assertions, coverage, scenario profiles, and VCD capture.
- Added strategy selection that requires parsed port directions and matching RTL contract evidence before enabling active stimulus. Other DUTs keep the existing assisted observation flow.
- Added controlled VCS/Verdi discovery, argument-vector compile and simulation execution, timeout handling, log classification, file-list writing, waveform validation, and structured per-test JSON evidence.
- Added precompile duplicate module/package detection and unresolved package import reporting.
- Added a desktop Run Verification action and tool status view. GUI work runs in the existing background worker.
- Packaged the supplied PCIe RTL copy under `examples/rtl/pcie`.
- Added tests for the active WRR model, strategy gate, generated environment, and simulator backend.
