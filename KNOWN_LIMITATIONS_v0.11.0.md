# Known limitations — Mverify 0.11.0

- The Verilog/SystemVerilog parser is lightweight. It is not a complete IEEE SystemVerilog frontend.
- VHDL is inventoried but not semantically parsed.
- Filelist support covers common `.f` syntax. Complex simulator syntax, environment-variable expansion and all vendor options are not implemented.
- Instance detection is heuristic. Actual port-connection expressions are not fully resolved by the lightweight parser.
- Surelog integration is optional and process-level. UHDM extraction is not integrated into a normalized signal-connectivity model.
- Tool presence does not imply that the project is configured to use that tool.
- Feature names and interface groups are candidates. Engineer review is required.
- The UI is a more complete native workbench, but it is not yet a signed commercial installer or a Qt-based product shell.
- Specification extraction does not guarantee correct requirement interpretation. Review clauses, revision and extracted text.
- UVM output is a structural scaffold. It is not a verified protocol-functional testbench. Do not interpret generated smoke stimulus as legal protocol traffic.
- Functional scoreboard generation, assertion generation and coverage closure require approved protocol semantics and expected-behavior models.
- No VCS, Questa or Verdi simulation was run as part of this release build.
- Mcore is an optional local service. Its absence must not block Mverify analysis.
- Subscription licensing, online accounts, installer signing, telemetry and update delivery are not implemented.
