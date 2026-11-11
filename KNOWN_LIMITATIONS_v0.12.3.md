# Known limitations — Mverify 0.12.3

## Mcore and retrieval
- Project isolation uses a stable hash of the resolved project directory. Different project directories cannot retrieve each other's indexed chunks through project-scoped GUI requests.
- Ask Mcore automatically indexes a project only when that project has no indexed chunks. If RTL changes, use **Index RTL into RAG** to clear and rebuild that project's index.
- Hybrid retrieval uses lexical term-frequency scoring plus cosine similarity when the configured Ollama embedding model is installed. Install it with `ollama pull nomic-embed-text`. If it is absent or unavailable, retrieval falls back to lexical matching.
- This release does not yet include a dedicated cross-encoder reranker, AST/dataflow-aware chunk graph, or formal semantic proof.
- Legacy knowledge records without a project ID are isolated under `__legacy__` and are not returned to project-scoped GUI queries.
- Qwen answers are advisory. Review claims against the actual RTL and specification.

## Specification and verification
- Automatic requirement approval is a structural evidence triage result, not proof of compliance.
- The frontend is not a complete SystemVerilog/VHDL elaborator.
- UVM output remains a scaffold. No VCS/Questa compile or simulation success is claimed.
