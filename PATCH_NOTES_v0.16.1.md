# Mverify 0.16.1 hotfix

## Fixed
- Mcore API response writer now tolerates a client disconnect without emitting an unhandled BrokenPipe traceback.
- Knowledge ingestion now returns a structured HTTP 503 error if embedding or database ingestion fails, rather than closing the request without a useful response.
- Desktop Mcore HTTP client now converts HTTP/network failures into readable messages.
- UVM generation dialog now distinguishes active WRR generation from passive observation-only generation.
- The UI now explains that selecting `pcie_controller_top` produces a passive environment because its active interface contracts are not approved. For the existing WRR-specific active generator, select `pcie_wrr_arbiter` as the DUT top and rescan.

## Not claimed
- This hotfix does not make the generic PCIe controller UVM environment active.
- It does not establish a functional PCIe controller reference model or sequence.
- No VCS compile or RTL simulation was run in this packaging environment.
- The WRR active generator still requires validation against the actual RTL on the user's RHEL/VCS environment.
