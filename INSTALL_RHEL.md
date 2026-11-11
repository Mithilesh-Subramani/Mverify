# Install Mverify 0.13.0 on RHEL without sudo

Use a separate directory for this release. Keep the previous version as a rollback copy.

```bash
mkdir -p ~/Mverify_0.13.0
cd ~/Mverify_0.13.0
unzip ~/Downloads/Mverify_0.13.0_Universal_RTL_Intelligence.zip
cd Mverify_0.13.0

source ~/miniforge3/etc/profile.d/conda.sh
conda activate mverify-gui
python -m pip install -e '.[dev]'
python -m pytest -q
python -m compileall -q mverify mcore desktop_app.py
python desktop_app.py
```

If Tkinter is missing, use a Python environment that includes Tk support. Do not change system packages without administrator approval.

## Start Mcore (optional)

In a second terminal:

```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate mverify-gui
cd ~/Mverify_0.13.0/Mverify_0.13.0
python -m mcore.api.server
```

Ollama must already be running locally. Check it with:

```bash
curl http://127.0.0.1:11434/api/tags
```

Mverify's static scan and deterministic adaptive planner do not require Mcore or internet access. Model reasoning requires the local Mcore API and an installed Ollama model.

## First validation

1. Select `examples/rtl/alu/` as the project directory. Select `alu` as top and scan.
2. Confirm the adaptive plan selects `combinational_unit`.
3. Open `examples/rtl/sync_fifo.sv`; confirm storage and handshake test intents appear.
4. Open `examples/rtl/arbiter.sv`; confirm contention/fairness test intent appears without a memory-boundary test.
5. Open `examples/rtl/subsystem.sv`; confirm hierarchy is detected and the plan is not treated as a standalone combinational ALU.

These are planner regression examples. They do not demonstrate that functional UVM stimulus or scoreboards have been generated.
