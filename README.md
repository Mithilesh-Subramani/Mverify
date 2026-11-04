# Mverify

Local-first RTL design verification assistant.

## Foundation v0.2 — structural discovery update

This release improves the first-pass Verilog/SystemVerilog structural scan:
- Handles parameterized module declarations: `module name #(parameters) (ports);`
- Uses balanced delimiters for parameter and port lists.
- Handles common ANSI port declarations and inherited directions.
- Records likely child-module instances, including parameterized instances.
- Reports likely top-level candidates and parser warnings.
- Keeps project scans in local SQLite storage.

This is **not** a complete IEEE Verilog/SystemVerilog parser. It does not elaborate macros, packages, interfaces, generate blocks, typedef-based widths, bind statements, or conditional compilation. It does not prove that a module implements a protocol requirement. Hierarchy results are heuristic and must be reviewed.

## Requirements

- Python 3.10+
- Linux development host (RHEL recommended)
- Optional later integration: Ollama, Synopsys VCS, Verdi

## Setup on RHEL

```bash
unzip Mverify_foundation_v0.2.zip -d ~/Mverify
cd ~/Mverify/Mverify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501.

## Scan a design

1. Start Mverify.
2. Enter the absolute path to the RTL project directory.
3. Enter the exact DUT top-module name if known.
4. Run the scan.
5. Review the module list, ports, hierarchy, top candidates, and warnings.
6. Download the JSON report.

## Privacy

The scanner reads local files only. It does not upload RTL or specifications. This milestone does not call Ollama.

## Important

A top candidate is a structural guess. Testbench modules and helper modules can also appear as candidates when source files are incomplete or hierarchy cannot be resolved. Select the actual DUT top manually. A successful parse is not proof of compile success or functional correctness.
