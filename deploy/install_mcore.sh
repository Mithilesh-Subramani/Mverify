#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON:-python3}"
VENV="${MCORE_VENV:-$ROOT/.venv-mcore}"
"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -e .
echo "Mcore environment ready: $VENV"
echo "Start with: $VENV/bin/python -m mcore.api.server"
