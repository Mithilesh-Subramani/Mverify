# Known limitations — Mverify 0.15.0

- The active strategy is implemented for the included `pcie_wrr_arbiter` contract. Other designs remain assisted/passive until a supported behavioral contract and safe stimulus mapping are established.
- The generated WRR testbench parses parameter defaults from the RTL. To exercise a non-default or non-power-of-two requester count, set `MVERIFY_NUM_TC` before generating and recompile; the GUI does not expose these parameters.
- Scenario names select parameterized stimulus profiles through plusargs; they are not separate UVM test classes. Fairness is checked for `continuous_contention`.
- Functional coverage currently reports requester count, requester grant index, acceptance, and one weight lane. It does not claim every requested cross, pointer/reload bins, or complete coverage.
- The generated UVM source was not compiled or simulated in this Windows session. The supplied Linux log reports VCS cannot load `libelf.so.1`; the supplied Verdi log reports its requested license is unavailable. Resolve those environment blockers before claiming WRR verification evidence.
- The desktop UI retains the existing Tkinter layout with an added run action and tool status view; the full redesign/sidebar/workspace described in the attached requirements was not completed.
- The backend runs tools available to the desktop process. The described Linux VCS host was not reachable from this session; no remote execution/transfer adapter is included.
- FSDB/PLI setup and automatic Verdi waveform loading are only attempted when local tool discovery succeeds. VCD is the generated fallback.
- Mcore remains the existing local service. No arbitrary shell execution path or external RTL upload was added.
