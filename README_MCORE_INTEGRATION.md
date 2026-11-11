# Mverify + Mcore integration (0.12.3)

Mverify is the desktop engineering workbench. Mcore is a separate local API. Qwen runs through Ollama.

## Start Ollama

```bash
ollama serve
ollama pull qwen2.5-coder:14b
ollama pull nomic-embed-text
```

`qwen2.5-coder:14b` performs reasoning. `nomic-embed-text` provides embeddings for semantic retrieval. The embedding model is optional; Mcore falls back to lexical retrieval if it is not available.

## Start Mcore

From the Mverify release root, with the Python environment activated:

```bash
python -m mcore.api.server
```

Default API: `http://127.0.0.1:8765`. Keep this terminal open.

## Start Mverify

In another terminal:

```bash
python desktop_app.py
```

Open the Mcore tab, check the service, scan the active RTL project, then use **Ask Mcore**. If the project has no index, Ask Mcore creates a project-scoped index automatically. Use **Index RTL into RAG** after RTL changes to replace the active project's old index.

## Ask Mcore vs Search RAG

- **Ask Mcore** retrieves current-project evidence automatically and asks the selected Ollama model to produce an evidence-grounded engineering answer.
- **Search RAG** is a retrieval diagnostic. It shows matching source chunks and does not call Qwen.

## Project isolation

Each project directory receives a stable project ID. Retrieval from the GUI is restricted to that ID. Legacy unscoped chunks are not mixed into the active project's context.
