# Mverify local AI and RAG architecture

## Locked direction

Mverify uses a local, replaceable AI service. The initial chat model is `qwen3-coder:30b` through Ollama. The initial embedding model is `nomic-embed-text`. Project knowledge is stored in a local Qdrant database. Fine-tuning is a later, separately evaluated improvement. Mcore is out of scope for this implementation.

## Responsibilities

- Fine-tuned chat model: learns reusable SystemVerilog, UVM, protocol and verification reasoning patterns.
- RAG: retrieves the current project's RTL, specification, build files and approved engineering knowledge.
- RTL frontend: supplies structural facts such as modules, ports, hierarchy and source locations. Vector search is not a replacement for parsing or elaboration.
- Verification tools: VCS/Questa, assertions, coverage and simulation provide execution evidence. The model cannot declare compliance by itself.

## Retrieval design

Use project-scoped Qdrant collections. Never retrieve across project or tenant boundaries by default. Every chunk carries its source path, line range, source kind and content hash. Retrieval is hybrid: dense embedding similarity plus lexical overlap, which helps exact RTL identifiers. Future iterations should add parser-backed symbol and hierarchy lookup as a first-class retrieval channel.

Initial ingestion supports Verilog/SystemVerilog source and text/Markdown/CSV documents. PDF and DOCX extraction can be connected to the existing specification extraction engine in the next integration step. Chunking is line-based to preserve useful source locations. It is an initial baseline, not a language-aware SV chunker.

## Runtime settings

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=qwen3-coder:30b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_NUM_CTX=16384
OLLAMA_TIMEOUT=300
MVERIFY_QDRANT_PATH=~/.mverify/qdrant
```

Install the optional retrieval dependency with `pip install 'qdrant-client>=1.12,<2'`. Ollama remains a separate local service.

## Training policy

Collect model inputs, model outputs, retrieved evidence, source hashes, engineer corrections, review status, and compile/simulation outcomes. Only engineer-approved and appropriately licensed examples may enter a fine-tuning dataset. Never train on raw customer RTL without explicit permission. RAG and fine-tuning are complementary, not interchangeable.

## Validation boundaries

- An indexed chunk is searchable evidence, not proof of behavior.
- A semantic match must be displayed with its source file and line range.
- Requirement approval is not a functional pass.
- UVM generation is not compile success.
- Compile success is not simulation success.
- Simulation success is not protocol compliance unless the checks trace to reviewed requirements.
