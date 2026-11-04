# Mverify

Local-first RTL design verification assistant.

## v0.5 — Verification Intelligence Engine

### Added
- Requirement classification into PCIe Transaction, Data Link, and Physical Layer candidates.
- Engineer-provided category takes precedence over heuristic classification.
- Requirement decomposition into actor, action, preconditions, expected result, negative behavior, and missing information.
- Layer-oriented verification scenario proposals.
- Requirement-to-RTL evidence carried into the plan.
- Explicit draft, review, and not-executed statuses.
- JSON export of verification plans.

### Run on Linux / RHEL
```bash
unzip Mverify_foundation_v0.5.zip -d ~/Mverify
cd ~/Mverify/Mverify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

### Workflow
1. Scan RTL.
2. Upload specification or requirements CSV.
3. Review extracted requirements and set `review_status=approved`.
4. Map approved requirements to RTL.
5. Generate verification plan.
6. Review classifications, decompositions, missing information, and proposed scenarios.
7. Export the plan JSON.

### Status semantics
- `draft_needs_engineer_review`: proposal requires review.
- `proposed_not_executed`: scenario exists only as a plan.
- `not_generated_or_run`: no executable test or simulation exists.
- `not_verified`: no passing simulation evidence exists.

### Limitations
- Classification and decomposition are deterministic heuristics, not semantic interpretation of the full specification.
- No numeric limits, timing values, or protocol rules are invented.
- Scenarios are generic proposals and require mapping to actual DUT interfaces.
- This milestone does not generate UVM source, compile RTL, run VCS, or inspect waveforms.
- Local-only processing; no remote AI service is used.
