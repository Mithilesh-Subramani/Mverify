# Mcore AI Core 0.1.0

Independent local AI service for VLSI engineering. Mverify is its first integration partner.

## Start

```bash
python -m mcore.api.server
```

API binds to `127.0.0.1:8765`. Set `MCORE_HOME` to choose its private data directory.

## Qwen integration

Mcore can call an Ollama-served Qwen model for advisory reasoning. Qwen is not a trainer by itself. Mcore stores candidate examples, requires explicit consent for training-ready status, and exports approved JSONL. A separate compatible fine-tuning toolchain must train and evaluate model weights.

## Endpoints

- `GET /health`
- `GET /models` (requires Ollama)
- `POST /reason` (requires Ollama)
- `POST /training/submit`
- `POST /knowledge/ingest`

This is an initial local service foundation, not a trained proprietary foundation model. Do not ingest confidential customer RTL unless data-use permission is explicit.
