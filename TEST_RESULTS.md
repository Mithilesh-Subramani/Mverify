# Test results — Mverify 0.15.0

## Python

- Baseline on untouched 0.13.0 checkout: **69 passed** (`python -m pytest -q`). The first attempt could not start because pytest was missing; after installing the declared `pytest>=7,<9` development dependency, the baseline passed.
- Release tree: **81 passed** (`python -m pytest -q`), including tests for the WRR model, contract gating, generated active source structure and parameter overrides, duplicate-definition handling, command construction, timeout handling, tool discovery, log classification, and VCD validation.
- Python source compilation: passed (`py_compile` on core modules and desktop application).

## Simulator and GUI evidence

- Local Windows tool discovery: VCS unavailable; Verdi unavailable; `UVM_HOME` and license environment variables unavailable.
- WSL has no configured Linux distribution. SSH to `c2sgpr075.cambridge.edu.in` could not resolve from this host.
- User-provided Linux evidence: VCS startup fails because `libelf.so.1` is missing; Verdi reports its Verdi-Elite license is unavailable.
- VCS compile: **not run**. VCS simulation/functional scoreboard: **not run**. Functional coverage: **not run**. Verdi waveform opening: **not run**. GUI interaction test: **not run**.

No simulator, functional, coverage, or Verdi success is claimed.
