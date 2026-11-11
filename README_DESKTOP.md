# Mverify desktop setup

Mverify uses a native Tkinter desktop application. It does not start a browser or web server.

1. Use Python 3.11 or newer.
2. Confirm Tkinter is installed: `python -m tkinter`.
3. Create and activate a virtual environment.
4. Install with `python -m pip install -e '.[dev]'`.
5. Run `python desktop_app.py` or `bash run_mverify.sh`.

The desktop has a project explorer, source preview, analysis summary, topology evidence, specification review, verification planning, UVM scaffold generation and an optional Mcore connection.

All RTL and specification files are read locally. Scan history is stored under `~/.mverify` unless `MVERIFY_HOME` is set.


## UVM topology and Mcore RAG (v0.12.1)

The UVM Generator tab shows the expected generated component tree after generation.
The generated base test calls `uvm_top.print_topology()` during end-of-elaboration.
After simulation, use **Load simulator log** to display the runtime topology excerpt.

To enable Mcore:
1. Open a second terminal in the repository.
2. Run `./run_mcore.sh`.
3. Keep the service running at `http://127.0.0.1:8765`.
4. Open the Mcore tab and select **Check service**.
5. Select **Index RTL into RAG**, then use **Search RAG** or **Ask Mcore**.

The current RAG retriever uses lexical term-frequency matching over SQLite chunks.
It does not use vector embeddings or a reranker. `Ask Mcore` also requires Ollama
and an installed model. If the API is not running, the GUI reports the connection
error. Mcore is optional; RTL scanning and UVM generation work without it.
