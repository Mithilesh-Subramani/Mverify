# Mverify 0.12.1

## DUT-specific architecture selection
- Architecture candidates now depend on parsed interface groups, state-machine evidence, procedural logic, hierarchy size and protocol feature candidates.
- Small combinational datapaths such as ALUs receive one compact directed-test architecture proposal.
- Sequential single-interface blocks receive a single-interface proposal.
- Multi-interface protocol controllers receive layered proposals; virtual-sequence coordination is offered only when structural complexity supports it.
- Every proposal includes its evidence and is labelled as a proposal. The current generated UVM output remains a passive observation scaffold until interface contracts and reference models are approved.

## Topology visibility
- The Topology tab now displays the generated UVM topology preview directly after generation.
- The Topology tab includes direct actions to show the generated preview and load a VCS/Questa runtime log.
- Runtime topology loading searches for UVM topology markers and component names.

## RAG status
- Mcore RAG is implemented as local SQLite-backed lexical chunk retrieval with source provenance.
- Vector embeddings and semantic vector search are not implemented in this release.
- Mcore must be started separately before the GUI can connect to its API.
