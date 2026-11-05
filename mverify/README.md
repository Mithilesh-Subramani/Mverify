# Mverify v0.6.2 — Feature-centric RTL analysis

## New in v0.6.2
- Adds a protocol-agnostic DUT feature inventory. It searches for candidate functions such as clock/reset control, handshakes, state machines, buffering, arbitration, integrity checks, retry/recovery, credit flow, packet formatting, data paths, counters, memories, parameterization, backend interfaces, and clock-domain crossing.
- Displays the modules and source evidence associated with each detected feature.
- Adds feature evidence to requirement-to-RTL mapping. A requirement can map to a design feature even when it does not map cleanly to a named PCIe layer.
- Keeps protocol/layer discovery as optional context. It is no longer the primary way to understand the DUT.
- Adds tests for non-PCIe designs and feature-based requirement mapping.

## New in v0.6
- Evidence-based requirement triage runs after specification extraction.
- Clear normative, observable requirements with matching RTL structural/layer evidence are auto-approved for planning.
- Headings and verification-process descriptions are rejected as DUT requirements.
- Ambiguous or unsupported candidates remain `needs_review`.
- Every decision includes a confidence value and human-readable reason.
- Generate UVM 1.2 skeleton source under `<RTL project>/mverify_uvm_generated`.
- Generated output includes signal-family interfaces, transaction item, sequencer/driver/monitor/agent classes, environment, scoreboard, base test, smoke sequence, top-level DUT instantiation with named port mapping, virtual-interface config_db setup, file list, and manifest.
- RTL source files are not modified. Generated files are isolated in a separate directory.

## Run
Use Python 3.11 or newer in a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

## Workflow
1. Scan the directory that contains the DUT RTL.
2. Select the correct DUT top if discovery finds more than one candidate.
3. Upload the DUT specification.
4. Mverify classifies candidates and auto-approves only those with clear normative/observable language and supporting structural evidence.
5. Review ambiguous candidates. You can override statuses in the table.
6. Map approved requirements and inspect evidence.
7. Select the DUT top and click **Generate UVM files in RTL project**.
8. Review `<RTL project>/mverify_uvm_generated`.

## Approval semantics
`approved` means a requirement is eligible for verification planning. It does not mean that RTL implements it or passes simulation. Structural names and hierarchy are evidence for planning only.

## UVM generator limitations — important
The generator creates an actual editable UVM component tree and top-level named DUT port connections. It is still a skeleton, not a complete protocol-aware verification environment:
- Generic transaction fields are placeholders.
- Driver pin-level behavior and monitor sampling must be implemented for each protocol.
- Scoreboard expected models and functional coverage must be completed.
- Package dependencies and simulator compile order must be checked against the target RTL.
- The generated code has not been compiled by VCS/Questa in this build environment. Do not treat generation as compile success.

The current auto-triage engine is deterministic and explainable. It is not an LLM and does not train itself. Ollama-based semantic assistance and persistent engineer-feedback learning are future integration work. Deterministic evidence gates remain authoritative for auto-approval.

## Validation
The included Python unit tests cover existing v0.5 behavior plus requirement triage and UVM tree generation. They do not replace HDL compilation or simulation.

## v0.6.3 — Specification-led PCIe verification planning

Mverify separates three kinds of evidence:

1. **Specification requirements:** extracted from the user-provided specification, with source file and line. The engineer must confirm the applicable PCIe revision and clause/section.
2. **RTL implementation evidence:** feature candidates, module/port matches, and hierarchy evidence. These show where to investigate; they do not prove protocol correctness.
3. **Verification evidence:** proposed requirement-derived test dimensions and, later, assertions/simulation results. A proposal is not an executed test or a compliance result.

The planner no longer selects generic test scenarios from a guessed PCIe layer. It derives review prompts from each approved requirement's wording (for example, negative conditions, sequencing, timing/limits, handshake, resource boundaries, integrity/recovery, and initialization/configuration). Exact PCIe rules, numeric limits, timing, exceptions, and expected results must be taken from the cited specification revision and clause. Mverify must not invent missing values or silently substitute general protocol knowledge.

Before relying on a plan, provide the exact specification revision and clause/section in the requirement table. Requirements without adequate clause context remain review items. Feature discovery remains useful for tracing implementation evidence, but the specification is the source of expected behavior.

This release is a conservative planning improvement. It does not yet implement a complete PCI-SIG specification semantic model, full SystemVerilog elaboration, or automatic proof of PCIe compliance.


## v0.8.1 Desktop application
Run `python desktop_app.py` for the native Tkinter desktop window. Streamlit is no longer required. See `README_DESKTOP.md` for RHEL setup and Tkinter checks.


## Local AI + project-scoped RAG (initial foundation)

A separate Streamlit page is available at **Local AI RAG** after starting Mverify. It uses Ollama for local chat and embeddings, and a local Qdrant database for project-scoped retrieval.

Install dependencies and models:

```bash
python -m pip install -r requirements.txt
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text
python -m streamlit run app.py
```

Open the **Local AI RAG** page, enter the RTL/specification directory, and select **Index / refresh this project**. Then ask a question about the DUT. The response displays retrieved source paths and line ranges. Initial retrieval supports Verilog/SystemVerilog, TXT, Markdown, RST, CSV, PDF and DOCX files. PDF and DOCX ingestion uses the existing optional extraction dependencies.

Set `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`, `OLLAMA_NUM_CTX`, and `OLLAMA_TIMEOUT` to configure the local model service. The RAG page also exposes model and Qdrant path settings. Each project path maps to a separate Qdrant collection.

This is the first integration milestone. It does not yet implement incremental file-level re-indexing, parser-backed symbol retrieval, tenant authentication, fine-tuning, or VCS/Questa execution orchestration. Review `docs/LOCAL_AI_RAG_ARCHITECTURE.md` and `docs/LOCAL_AI_TRAINING_DATA_POLICY.md`.
