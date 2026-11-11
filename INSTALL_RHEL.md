# Install Mverify 0.15.0 on RHEL without sudo

Use a separate directory for this release. Keep the previous version as a rollback copy.

```bash
mkdir -p ~/Mverify_0.15.0
cd ~/Mverify_0.15.0
unzip ~/Downloads/Mverify_0.15.0_Active_UVM_VCS_Verdi.zip
cd Mverify_0.15.0

source ~/miniforge3/etc/profile.d/conda.sh
conda activate mverify-gui
python -m pip install -e '.[dev]'
python -m pytest -q
python -m compileall -q mverify mcore desktop_app.py
mverify
```

If Tkinter is missing, use a Python environment that includes Tk support. Do not change system packages without administrator approval.

## Start Mcore (optional)

In a second terminal:

```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate mverify-gui
cd ~/Mverify_0.15.0/Mverify_0.15.0
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
## Standard Python installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
mverify
```

The desktop requires a graphical session. For a source-tree launch without installation, use:

```bash
python -c 'from mverify.desktop import main; main()'
```

Load the Synopsys environment in the same shell before launching Mverify if you want the Run Verification action to discover VCS and Verdi. See [VCS_VERDI_SETUP.md](VCS_VERDI_SETUP.md). Tool discovery does not modify license settings.

## WRR acceptance flow

1. Select the packaged `examples/rtl/pcie` directory as the project and set DUT top to `pcie_wrr_arbiter`.
2. Select **Scan design**, then choose and review an architecture proposal.
3. Select **Generate UVM scaffold**. The confirmed WRR interface produces an active UVM agent; unknown designs stay in assisted mode.
4. Select **RUN VERIFICATION**. The action compiles and simulates with the local VCS process. A Python test pass or successful compile is not a simulation pass.
5. Review the generated `mverify_uvm_generated/build` logs and JSON result. For scenario selection, set `MVERIFY_SCENARIO` before starting Mverify. For a non-default requester count, set `MVERIFY_NUM_TC` before generation (for example, `MVERIFY_NUM_TC=5 mverify`) and regenerate/recompile. `MVERIFY_WEIGHT_W` similarly selects the weight width.

On the reported host, first resolve the missing `libelf.so.1` dependency and Verdi license availability documented in `VCS_VERDI_SETUP.md`.

## Existing features

The previous 0.13.0 installation and Mcore/RAG setup remains documented below.

