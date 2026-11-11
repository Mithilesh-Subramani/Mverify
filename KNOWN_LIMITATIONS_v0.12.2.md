# Known limitations — Mverify 0.12.2

## Specification-to-RTL triage
- Automatic approval means that a requirement candidate is sufficiently clear and has a structural RTL evidence match for verification planning. It does not prove that the RTL satisfies the requirement.
- The current mapping uses static names, feature candidates, semantic signal/state candidates and architecture-layer evidence. It does not perform complete symbolic dataflow or formal equivalence.
- Ambiguous, incomplete or unsupported requirements remain in `needs_review`; engineers can override the review status.
- Normative extraction from complex PDFs can still produce false positives. Review the extracted statement and source context.

## Mcore and RAG
- Ask Mcore retrieves indexed evidence automatically and sends the question plus evidence to the selected Ollama model.
- Search RAG only displays retrieval results; it does not call the LLM.
- Retrieval remains SQLite lexical term-frequency search. Vector embeddings, semantic vector search and reranking are not implemented.
- The GUI formats model output for readability. Model claims still require source review.

## RTL and UVM
- The built-in frontend is a conservative source parser, not a complete SystemVerilog/VHDL elaborator.
- UVM generation remains a passive observation scaffold with scenario stubs. It is not a complete protocol-functional testbench.
- No VCS or Questa compile/simulation success is claimed by this package.
