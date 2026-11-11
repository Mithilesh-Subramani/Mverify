# Mcore v0.2.0

Independent local VLSI AI service. Mverify is its first client.

Run `./run_mcore.sh` (default `127.0.0.1:8765`). Ollama/Qwen runs separately at `http://localhost:11434`.

Capabilities: provenance-aware knowledge ingestion, chunking, lexical retrieval, retrieval-augmented Qwen reasoning, training candidate review/list/reject/consent approval, JSONL export, and optional QLoRA/SFT starter.

Fine-tuning dependencies are separate: `pip install -r training/requirements-finetune.txt`. Fine-tuning requires a compatible base model, supported hardware, reviewed dataset and separate evaluation. The API does not automatically train models.
