# Mverify 0.16.0 — deployment, update and rollback

## Host model

Windows hosts source editing and synthetic regression only. RHEL hosts Mverify, Mcore, Ollama and proprietary RTL. Keep proprietary source, logs containing source excerpts, databases, generated designs and model requests on the approved engineering host. Do not expose Mcore or Ollama publicly. Mcore enforces loopback binding; use approved host-local access or an organization-managed authenticated tunnel if remote viewing is needed. This release provides no remote shell or job-submission API.

## Configuration

```bash
cp .env.example /path/to/approved/mverify.env
chmod 600 /path/to/approved/mverify.env
# Edit the protected file for host-local paths/models, then:
source /path/to/approved/mverify.env
```

Do not put license keys or secrets in the repository. `OLLAMA_HOST` should normally be `http://127.0.0.1:11434`; set `MCORE_MODEL` and `MCORE_EMBEDDING_MODEL` to installed tags. Use `MCORE_HOME` for a persistent private data directory.

## Independent installation

From the approved release checkout, use separate virtual environments:

```bash
python3.11 -m venv .venv-mcore
. .venv-mcore/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m mcore.api.server
```

In a second shell:

```bash
python3.11 -m venv .venv-mverify
. .venv-mverify/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python desktop_app.py
```

Mcore API defaults to `http://127.0.0.1:8765/api/v1`; Mverify does not start the API automatically. `MCORE_HOST` accepts loopback only. Keep `MCORE_HOME` writable by the service account and restricted to engineering users.

## Update

1. Review and approve the source revision on Windows; commit/push source only.
2. On RHEL, back up `MCORE_HOME`, save the current Git revision, and pull the approved commit.
3. Activate each existing virtual environment and install the approved revision (`python -m pip install -e .`).
4. Start Mcore. Startup runs backup-first migrations.
5. Check `curl --fail http://127.0.0.1:8765/api/v1/health` and `/models`.
6. Run `bash deploy/remote_validate.sh`; approve RTL/VCS actions only after reviewing their explicit paths and scope.

Example backup/revision capture:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
cp -a "$MCORE_HOME" "${MCORE_HOME}.backup-${stamp}"
git rev-parse HEAD > "${MCORE_HOME}.deployment-revision-${stamp}"
```

## Rollback

Stop Mcore and Mverify processes. Check out the saved approved Git revision. Restore the matching MCORE_HOME backup as a complete directory (never combine a newer schema with older code). Reactivate the existing environments, reinstall the restored revision, and restart the services. Verify `/health`, `/models`, and a project-isolated synthetic query before resuming engineering work. Preserve failed-release logs for diagnosis.

## Remote validation

```bash
source /path/to/approved/mverify.env
bash deploy/remote_validate.sh
```

This fixed workflow runs Python regression, project-isolated retrieval, reasoning and UVM generation tests, then checks Mcore health, configured model status and a synthetic embedding. It writes per-action logs and a structured report. To permit actual RTL inspection, set `MVERIFY_ALLOWED_PROJECT_ROOTS` and `MVERIFY_RTL_PROJECT` to host-local paths, review them, and pass `--approve-rtl`. Add `--approve-vcs` only for explicit approval of the fixed VCS compile/simulation action. The script enforces a project-root allowlist and fixed command set; it has no arbitrary shell input. A report is evidence for only the actions and project it records.

## Diagnostics

```bash
# Runtime services
curl -sS http://127.0.0.1:8765/api/v1/health
curl -sS http://127.0.0.1:8765/api/v1/models
curl -sS http://127.0.0.1:8765/api/v1/knowledge/project/status \
  -H 'Content-Type: application/json' -d '{"project_id":"<project-id>"}'

# Ollama locally on RHEL
curl -sS http://127.0.0.1:11434/api/tags
ollama list

# Python, tools and recorded validation
python --version
command -v vcs || true
command -v verdi || true
cat .mverify-validation/remote_validation.json
```

A model/embedding failure is reported as blocked; no model fallback is selected silently. A failed or skipped simulator action is not a passing RTL integration result.
