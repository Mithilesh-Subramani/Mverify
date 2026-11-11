# Mverify 0.12.1 — RTL Engineering Workbench

Mverify is a local-first desktop application for RTL project discovery, evidence-based design analysis, specification review, verification planning and UVM scaffold generation. It supports general RTL projects. PCIe discovery is an optional protocol-specific extension, not the core architecture.

## Current capabilities

- Native desktop GUI with project explorer, source preview, scan metrics, analysis, topology, specification, verification planning and UVM generation views.
- Project inventory for Verilog/SystemVerilog, VHDL, filelists, timing constraints, EDA project metadata, Tcl scripts, documentation and support files.
- Verilog/SystemVerilog lightweight structural parsing, candidate module hierarchy, top candidates, port declarations and lexical semantic evidence.
- `.f` filelist handling for common include-directory, macro, nested-filelist and source entries.
- Optional Surelog invocation when installed. Tool availability is reported instead of being assumed.
- Feature detection and requirement-to-RTL mapping. Findings retain their evidence and limitations.
- Verification scenario catalog and passive UVM 1.2 scaffold generation.
- Generated top-level virtual interface, all-port passive monitor, scoreboard connection, selectable observation test stubs and runtime topology print.
- Desktop UVM topology preview and simulator-log import.
- Optional Mcore knowledge indexing, lexical RAG search and evidence-grounded Ollama reasoning.
- Optional local Ollama advisory analysis and separate Mcore learning service.
- SQLite scan history stored under `~/.mverify` by default.

## Important analysis boundaries

The lightweight parser is not a complete SystemVerilog or VHDL compiler. Project inventory can discover VHDL and other EDA inputs, but VHDL semantic parsing is not implemented in this release. The hierarchy and port topology are candidate evidence. They do not prove resolved instance-to-port connectivity, unique drivers, CDC safety, timing closure or functional correctness.

Surelog is optional. A successful Surelog parse/elaboration process is not simulation. The current UVM generator is a passive scaffold. It maps parsed top-level ports and samples them. It does not drive DUT inputs. Generated scenario tests are observation stubs, not protocol-functional tests. The sequence template is not compiled. Active stimulus requires reviewed signal semantics, reset behavior, timing and protocol mapping. Functional scoreboarding requires an independent requirement-derived reference model.

Mcore is optional and separate. The desktop can index RTL text, search the Mcore knowledge store and send evidence-grounded engineering questions to the Mcore API. Current retrieval is lexical term matching, not vector embedding retrieval. Model reasoning requires Ollama and an installed model. Training examples require explicit engineer consent and review. The application does not update model weights when it records an experience.

## Quick start (RHEL / Linux)

```bash
git clone https://github.com/Mithilesh-Subramani/Mverify.git
cd Mverify
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m pytest -q
python desktop_app.py
```

Tkinter must be available in the selected Python installation. Check it with `python -m tkinter`.

Or use `bash run_mverify.sh`.

## Optional tools

Mverify checks for `surelog`, `slang`, `yosys`, `iverilog`, `verilator`, `vcs`, `vsim`, `verdi`, `gtkwave` and `ollama` on `PATH`. Missing tools do not prevent basic inventory and lightweight parsing.

For local Ollama assistance, start Ollama separately and select an installed model in the Verification Plan view. The default model is `qwen2.5-coder:14b`; change it to a model that is installed on your machine.

## Repository layout

```text
Mverify/
├── desktop_app.py              # native desktop application
├── mverify/                    # canonical Mverify Python package
├── mcore/                      # canonical Mcore Python package
├── Mcore/                      # Mcore docs, training utilities and tests
├── tests/                      # Mverify test suite
├── .github/workflows/tests.yml # CI
├── pyproject.toml
└── run_mverify.sh
```

There is one canonical `mverify` package. The old nested `mverify/mverify` duplicate package has been removed from the release layout.

## Development

```bash
python -m pytest -q
python -m compileall -q mverify mcore desktop_app.py
```

Start Mcore in a second terminal when you need RAG/model assistance:

```bash
./run_mcore.sh
```

Then open the Mcore tab, check the service, index RTL into RAG, and search or ask an engineering question.

See `KNOWN_LIMITATIONS_v0.12.1.md` and `CHANGELOG_v0.12.1.md` for release boundaries.


## Version 0.12.3 updates

- Desktop specification import performs automatic evidence-based requirement triage. Ambiguous requirements remain available for manual override. Approval does not prove compliance.
- Ask Mcore and Search RAG now display readable engineering summaries and source evidence instead of raw JSON.
- Ask Mcore performs retrieval through Mcore and uses the selected local Ollama model; Search RAG is retrieval-only.
- See `KNOWN_LIMITATIONS_v0.12.3.md` for exact implementation boundaries.

## Mcore retrieval in 0.12.3

Mcore retrieval is scoped to the active project. Ask Mcore automatically retrieves current-project evidence. Hybrid lexical/vector retrieval is enabled when Ollama `nomic-embed-text` is installed; otherwise it uses lexical fallback. Re-index after RTL changes. See `README_MCORE_INTEGRATION.md`.
