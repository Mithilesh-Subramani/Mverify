# Mverify 0.16.2 — Mcore-Centric RTL Verification Intelligence

Mverify is the RTL project workbench; Mcore is its separately runnable local reasoning and retrieval service. Together they provide project inventory, a source-grounded Universal Design Model (UDM), requirement triage, scoped retrieval, evidence-checked engineering answers, verification planning and UVM scaffold generation.

This release is designed for a split workflow: edit and review source on Windows, then deploy approved changes to the RHEL engineering host. It contains synthetic fixtures only. Proprietary RTL must remain on the engineering host.

## Start on RHEL

```bash
# Set the local service/model configuration (see .env.example).
source /path/to/approved/mverify.env
python3.11 -m venv .venv-mcore
. .venv-mcore/bin/activate
python -m pip install -e .
python -m mcore.api.server
```

In a second terminal, install/run the Mverify desktop in its own environment:

```bash
python3.11 -m venv .venv-mverify
. .venv-mverify/bin/activate
python -m pip install -e '.[dev]'
python desktop_app.py
```

The services are independently started and stopped. Mcore binds to loopback by default and rejects non-loopback bind configuration. Ollama is addressed locally by Mcore; neither service should be published to the public internet.

## Windows development and RHEL validation

Windows is for source changes, synthetic tests, Git review and delivery. Do not configure Windows to reach RHEL localhost, and do not copy proprietary RTL to Windows, Git, Codex, or external services. Commit and push source changes without design data. On RHEL, pull the approved revision and run `bash deploy/remote_validate.sh`. This runs fixed test commands, checks Mcore and Ollama/model/embedding availability, and writes logs plus `remote_validation.json` under `MVERIFY_VALIDATION_DIR` (default `.mverify-validation`).

Private-project analysis requires explicit local configuration and approval:

```bash
export MVERIFY_ALLOWED_PROJECT_ROOTS=/server/designs/approved
export MVERIFY_RTL_PROJECT=/server/designs/approved/project_a
export MVERIFY_DUT_TOP=top_module  # optional; selection may require engineer review
bash deploy/remote_validate.sh --approve-rtl
# Include --approve-vcs only after separately approving the fixed VCS action:
bash deploy/remote_validate.sh --approve-rtl --approve-vcs
```

The validator accepts no arbitrary command strings. It runs a fixed list of Python tests and, when explicitly approved, scans only an allowlisted directory and may run a fixed compile/simulation flow. Each action has a timeout, writes a log, and is recorded in JSON. RTL stays on the RHEL host. Without actual RHEL report evidence, integration status is unknown; this source package does not claim remote validation success.

## Configuration

Copy `.env.example` to a protected, host-local environment file and source it. Defaults target `127.0.0.1`: Mcore API `8765`; Ollama `11434`; reasoning model `qwen2.5-coder:14b`; embedding model `nomic-embed-text:latest`. Change values using environment variables. Mcore reports missing configured models and does not silently choose a substitute.

## Data, migration and lifecycle

Mcore stores its SQLite databases under `MCORE_HOME` (default `~/.mcore`). Startup migrations create timestamped backups before schema changes. See `DEPLOYMENT_v0.16.0.md` for install, update, rollback, diagnostics and validation commands. Back up the MCORE_HOME directory and deployment revision together before updating.

## Engineering boundaries

UDM and the lightweight parser are evidence-bearing structural summaries, not a full SystemVerilog elaborator. Mcore validates claim schema, evidence IDs, project scope and certain metadata conflicts; it cannot prove semantic correctness. Retrieval is project-isolated and uses embeddings when the configured Ollama embed model is available, with visible lexical fallback. Generated UVM is a scaffold; actual DUT simulation is performed only when an operator explicitly approves an allowlisted project and VCS action. Passing Python tests do not establish RTL functionality, coverage closure, timing, or Verdi usability.

## v0.16.2 verification intelligence additions

- **Interface candidate discovery:** identifies exact valid/ready naming pairs and records their directions. These are review candidates, not proven protocol contracts.
- **Handshake trace analysis:** imports wide or long CSV signal samples and measures accepted cycles, stalled cycles, longest observed stall and unknown samples. No protocol latency limit is assumed.
- **RTL change snapshots:** hashes RTL and build inputs under the project-local `.mverify/snapshots/` directory and reports added, removed and modified files.
- **Verification readiness report:** summarizes interface candidates, FSM candidates, requirement review state and explicit evidence limitations.
- **Hybrid model routing:** Ollama remains the default. Cloud inference is disabled by default and requires configured credentials plus an explicit per-request `cloud_approved=true` and `data_classification="approved_for_cloud"`. Sensitive project data stays on the local route by default.

The Streamlit workbench is optional. Install it with `python -m pip install '.[ui]'`, then run `streamlit run app.py`. The desktop application remains available through `python desktop_app.py`.

See `KNOWN_LIMITATIONS_v0.16.0.md`, `MCORE_API_v0.16.0.md` and `UNIVERSAL_RTL_ARCHITECTURE.md`.
