# Mverify 0.16.2 — Start Here (Windows)

## 1. Extract the ZIP

Extract the complete `Mverify_0.16.2` folder. Do not copy only selected Python files.

## 2. Create the Python environment

Open PowerShell in the extracted project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ui]"
```

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Run the Streamlit workbench

```powershell
streamlit run app.py
```

Open the local URL printed by Streamlit. Select the directory that contains your RTL files, select the DUT top if needed, and click **Scan RTL project**.

## 4. Run the desktop application

The existing Tkinter desktop application is preserved:

```powershell
python desktop_app.py
```

## 5. Run the Mcore reasoning service

In a second PowerShell terminal, activate the same environment and run:

```powershell
.\.venv\Scripts\Activate.ps1
python -m mcore.api.server
```

Mcore uses loopback by default. Keep it on the local machine or a protected engineering host. Do not expose the API to the public internet.

## 6. Run the tests

```powershell
python -m pytest -q
```

Expected package validation at build time: 77 tests passed. Re-run tests on your machine before using the update with a live design.

## 7. New v0.16.2 functions

After scanning an RTL project, the Streamlit workbench includes:

- Candidate valid/ready interface pairs. Review all candidates; names alone do not prove protocol semantics.
- Handshake trace analysis. Upload a CSV in wide format (`cycle,tx_valid,tx_ready`) or long format (`cycle,signal,value`). The analysis measures accepts and observed stalls. It does not assume a legal maximum latency.
- RTL change snapshots. The first snapshot creates a baseline. Capture another after edits to see added, removed and modified RTL/build files.
- Verification readiness gates. These distinguish static evidence from simulation and compliance evidence.

Snapshots are stored under the selected project in `.mverify/snapshots/`.

## 8. Hybrid AI policy

Local Ollama remains the default. Cloud routing is disabled unless explicitly configured. To enable an OpenAI-compatible provider, set these variables in a protected environment:

```text
MCORE_CLOUD_ENABLED=true
MCORE_CLOUD_BASE_URL=https://your-approved-provider/v1
MCORE_CLOUD_API_KEY=<secret>
MCORE_CLOUD_MODEL=<approved-model>
```

A request must also explicitly set `cloud_approved=true` and `data_classification="approved_for_cloud"` to use the cloud route. The request context can include RTL/specification evidence. Do not approve cloud use for confidential designs unless your organization has authorized that provider and data transfer.

## 9. EDA validation boundary

This package does not include Synopsys VCS, Verdi, Questa or Xcelium. Those tools require your licensed installation and environment setup. Python tests do not prove that generated UVM compiles or that a DUT passes protocol verification. Run simulator validation on your approved engineering machine.
