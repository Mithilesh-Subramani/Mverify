# Mverify 0.12.3 — Project-isolated hybrid RAG and context-aware Mcore

## Fixed
- Scope knowledge chunks and retrieval by a stable identifier derived from the active project path. A question about an ALU cannot retrieve stale PCIe chunks from another project.
- Add project-scoped clear/status operations. Re-indexing replaces the active project's previous chunks instead of accumulating stale source versions.
- Ask Mcore automatically creates the active project's index when no project index exists. The explicit Index RTL into RAG button refreshes that project's index.
- Send the selected DUT, ports, module inventory, hierarchy, feature evidence, semantic evidence, toolchain data and project identity with each reasoning request.
- Expand short questions with active-DUT identifiers before retrieval, so questions such as “what are the risks?” retrieve current design evidence.
- Add hybrid retrieval: lexical term matching plus optional Ollama embeddings (`/api/embed`). If the embedding model is unavailable, Mcore falls back to lexical retrieval without repeatedly waiting on a failed embedding request.
- Keep retrieval scoped to the current project. Legacy unscoped chunks are not included in project-scoped Ask Mcore requests.
- Fix prompt newline construction so evidence sections are separated correctly.

## Validation
- Python compile check passed.
- 64 Python tests passed, including new project-isolation, re-index cleanup and embedding-score tests.
- No VCS/Questa compile or RTL simulation claim is made.
