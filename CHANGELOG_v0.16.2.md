# Mverify 0.16.2 — Verification Intelligence Update

## Added
- Deterministic valid/ready interface candidate discovery with explicit inference labels and review gates.
- CSV waveform-sample ingestion in wide and long formats.
- Handshake acceptance and backpressure stall measurements without invented latency thresholds.
- Immutable RTL/build-input hash snapshots and file-level change comparison.
- Verification readiness report for interface candidates, FSM candidates and requirement review state.
- Streamlit UI for interface review, handshake trace analysis, and project snapshots.
- Hybrid model router with local Ollama default and explicit cloud approval/data-classification gates.

## Preserved
- Existing Mcore API, project-scoped knowledge retrieval, claim evaluation, UDM, RTL scanning, requirement triage, architecture approval, UVM generation and simulator backend.

## Validation
- Python unit tests are run with `python -m pytest`.
- This package does not claim VCS/Questa/Xcelium compilation or RTL simulation. Those require the user's licensed EDA environment and approved DUT.
