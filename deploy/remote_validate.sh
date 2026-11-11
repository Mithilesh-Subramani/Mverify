#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export MCORE_API_URL="${MCORE_API_URL:-http://127.0.0.1:8765/api/v1}"
export MCORE_MODEL="${MCORE_MODEL:-qwen2.5-coder:14b}"
export MCORE_EMBEDDING_MODEL="${MCORE_EMBEDDING_MODEL:-nomic-embed-text:latest}"
PYTHON_BIN="${MVERIFY_PYTHON:-${PYTHON:-python3}}"
exec "$PYTHON_BIN" -m tools.remote_validate "$@"
