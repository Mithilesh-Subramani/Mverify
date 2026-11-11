# Known limitations — Mverify 0.12.0

- The lightweight parser is not a complete SystemVerilog/VHDL compiler.
- The generated interface maps parsed top-level declarations. It does not resolve every internal instance-to-port expression.
- The generated UVM environment is passive. It does not drive DUT inputs.
- Generated scenario test classes are selectable observation stubs. They are not complete functional tests.
- The sequence template is not compiled. A legal transaction model, driver, clocking, reset and handshake rules must be approved first.
- The scoreboard counts observations. It does not compare against an independent functional reference model.
- `uvm_top.print_topology()` is emitted by the generated base test. The actual topology is available only after a successful simulator run. The GUI can load the simulator log.
- The Mcore knowledge store currently uses lexical term-frequency retrieval. It is a basic retrieval-augmented workflow, not embedding/vector or reranking RAG.
- Mcore model reasoning requires a running Ollama service and an installed model.
- Mcore does not fine-tune model weights when an experience is stored.
- No simulator compile or simulation was run during packaging. Run the generated scripts with your licensed simulator and UVM installation.
