# Mverify

Local-first, AI-assisted RTL design verification platform.

## Current milestone: Foundation v0.1

This starter establishes:
- Streamlit application shell
- Local project configuration
- SQLite database
- Logging
- RTL file discovery
- Basic Verilog/SystemVerilog module and port extraction
- A project scan report

It does **not** yet claim protocol compliance or simulation verification. Those engines are later milestones.

## Requirements

- Python 3.10+
- Red Hat Enterprise Linux (or another Linux development host)
- Optional: Ollama, Synopsys VCS, Verdi (integrated in later milestones)

## Setup on RHEL

```bash
python3 --version
mkdir -p ~/Mverify
unzip Mverify_foundation_v0.1.zip -d ~/Mverify
cd ~/Mverify/Mverify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest
streamlit run app.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501.

## Scan a design

1. Start Mverify.
2. Enter the absolute path to your RTL project directory.
3. Select the top-level module if it is known.
4. Run the scan.
5. Review the discovered modules, ports and warnings.

## Privacy

The foundation performs local file scanning. It does not upload RTL or specifications.
No Ollama call is made in this milestone.

## Current limitations

The parser is intentionally conservative. It handles common module declarations and ANSI-style ports. Complex SystemVerilog constructs, interfaces, packages, macros, generate elaboration and full semantic analysis require a proper HDL frontend in a later milestone. Always review the scan output.
