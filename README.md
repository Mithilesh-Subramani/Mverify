# Mverify

Mverify is a local-first RTL design verification workbench. It scans Verilog/SystemVerilog projects, extracts specification requirements, maps requirements to RTL evidence, proposes verification architectures, and generates editable UVM scaffolds.

## Run

See [mverify/README.md](mverify/README.md) for setup, supported workflows, and current limitations.

For the native desktop application, see [mverify/README_DESKTOP.md](mverify/README_DESKTOP.md).

## Local AI direction

The planned AI stack is local Ollama inference with Qwen3-Coder, project-scoped hybrid RAG, and a local embedding model. Fine-tuning is a later phase based on reviewed and validated engineering examples. See the local AI architecture documentation when that implementation branch is ready.

## Verification boundary

Static analysis and generated UVM scaffolds are not proof of functional correctness or protocol compliance. Use the target HDL compiler, simulator, assertions, coverage, and reviewed specification-derived checks.
