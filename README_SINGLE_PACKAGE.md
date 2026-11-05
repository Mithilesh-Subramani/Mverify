# Mverify + Mcore — Unified Local Engineering Verification Package

This package combines Mverify v0.10.0 with Mcore v0.3.0.

## Package layout
- `Mverify/`: desktop RTL/specification analysis and verification workflow.
- `Mcore/`: local reasoning API, knowledge retrieval, training review and reasoning foundation.
- `run_mcore.sh`: starts the Mcore API.
- `run_mverify.sh`: starts the Mverify desktop application.
- `run_all.sh`: starts Mcore, checks its health endpoint, then starts Mverify.

## Requirements
- Linux (RHEL-compatible environment recommended).
- Python 3.11 recommended.
- Tkinter for the desktop UI.
- Ollama is optional. Install it and pull a compatible model for local LLM inference.
- VCS/Verdi are optional external EDA tools. They are not bundled.

## Setup
```bash
cd Mverify_Mcore_Unified
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Start both
```bash
./run_all.sh
```

Or start services separately:
```bash
./run_mcore.sh
./run_mverify.sh
```

Mcore API default: `http://127.0.0.1:8765`.

## Ollama (optional)
```bash
ollama serve
ollama pull qwen2.5-coder:7b
```
Mcore uses Ollama for inference only. This package does not train model weights.
Fine-tuning is an optional experiment documented in `Mcore/training/`.

## Tests
```bash
source .venv/bin/activate
PYTHONPATH="$PWD/Mcore:$PWD/Mverify" python -m pytest -q Mcore/tests Mverify/tests
python -m compileall -q Mcore Mverify
```

## Important limitations
- Mverify's existing UVM generator remains primarily structural/template-based.
- Mcore v0.3 adds evidence-first reasoning orchestration and initial rules; it is not yet a trained VLSI foundation model.
- Reasoning schema and evidence-ID checks do not prove semantic correctness.
- Full IEEE SystemVerilog/UVM rule coverage is not included.
- Surelog integration, VCS, Verdi, Ollama inference and fine-tuning must be validated in the target environment.
- No functional PCIe compliance claim is made by this package.
