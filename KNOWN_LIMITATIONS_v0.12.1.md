# Known limitations — Mverify 0.12.1

## RTL analysis
- The built-in frontend is a conservative source parser. It is not a complete SystemVerilog/VHDL elaborator.
- Signal grouping and architecture classification use static evidence and heuristics. Treat them as reviewable candidates, not proof of connectivity or protocol semantics.
- Full instance connection resolution, driver uniqueness, CDC proof, timing analysis and functional equivalence are not provided.

## UVM generation
- The generated environment is currently a passive observation scaffold. It connects parsed top-level ports, samples them, connects a monitor analysis port to an observation scoreboard, and prints the UVM component topology during `end_of_elaboration_phase`.
- The generated scenario test classes are selectable observation stubs. They do not apply protocol stimulus or prove expected functional results.
- The protocol sequence file is a review template and is not included in the compile filelist. A driver/sequencer must be generated only after clock/reset, interface directions, handshake rules and transaction semantics are approved.
- The scoreboard counts and reports observations. It is not an independent functional reference model.
- The generated topology preview is a static expected component tree. The actual UVM factory-built topology is available only after a successful simulator compile and test run; load that simulator log in the GUI.
- No VCS or Questa compile/simulation success is claimed by this package.

## Mcore and RAG
- Mcore is an optional local HTTP service. Start it separately with `python -m mcore.api.server` from the repository root.
- RAG is implemented as SQLite-backed chunk storage and lexical term-frequency retrieval with source provenance.
- Vector embeddings, vector databases, semantic embedding search and automatic model fine-tuning are not implemented.
- Ollama is required for local-model engineering reasoning. RAG search can operate without Ollama once Mcore is running and files are indexed.
