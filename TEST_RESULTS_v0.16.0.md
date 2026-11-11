# Local results — Mverify 0.16.0

Development host: Windows. No connection to the RHEL Ollama service or private RTL was assumed or attempted.

- Python regression: **90 passed** (`python -m pytest -q`), including project isolation, Mcore configuration/API, claim/evidence handling, migrations/retrieval, synthetic UVM generation and active-verification structure.
- Package contents: synthetic RTL fixtures only; no proprietary project files included.
- RHEL Mcore health/model/embedding checks: **not run here**.
- RHEL project-isolated reasoning and UVM generation: **not run here**.
- Actual project scan, VCS compile/simulation, functional checking, coverage and Verdi: **not run here**.

Use `bash deploy/remote_validate.sh` on the RHEL engineering host to create `remote_validation.json` and per-check logs. Actual RTL access and VCS actions require explicit local approvals and allowlisted RHEL paths. No remote integration success is claimed by this report.
