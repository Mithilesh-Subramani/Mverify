# Mverify Desktop (v0.8.1)

Mverify now has a native Tkinter desktop window. It does not start Streamlit, a local web server, or a browser.

## Requirements
- Python 3.11+
- Tkinter/Tk development package installed by the operating system
- Optional: local Ollama server and a model such as `qwen2.5-coder:7b`
- Optional: `pypdf` and `python-docx` for PDF/DOCX specification extraction

## RHEL setup
From the Mverify project directory:
```bash
python3.11 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -r requirements.txt
python -m tkinter
```
The last command should open a small Tk test window. If it reports that tkinter is missing, ask the system administrator to install the matching Python 3.11 Tk package (package name varies by RHEL image).

Start Mverify:
```bash
python desktop_app.py
```
Or:
```bash
bash run_mverify.sh
```

## Desktop workflow
1. Browse to the RTL project and scan it.
2. Load a local specification.
3. Review candidate requirements. This first desktop release displays the extracted JSON; it does not yet provide a full editable grid.
4. Run DUT-specific verification intelligence. Ollama is optional and stays local.
5. Review and approve an architecture option.
6. Generate the current UVM scaffold.

## Performance
The desktop window starts without a browser runtime or Streamlit server. RTL scans and AI analysis run in a worker thread so the window remains responsive. Analysis time still depends on RTL size and local Ollama model speed.

## Current limitations
- Tkinter is a lightweight native desktop UI, not a polished installer/package.
- Requirement editing is currently limited; use an input CSV with a `review_status` column set to `approved` for approved rows.
- This change does not add functional PCIe pin-level drivers. That remains a separate protocol-model/driver implementation milestone.
- The existing analysis engines and their evidence limitations are unchanged.
