#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON:-python3}"
VENV="${MVERIFY_VENV:-$ROOT/.venv-mverify}"
"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -e '.[dev]'
echo "Mverify environment ready: $VENV"
echo "Start with: $VENV/bin/python $ROOT/desktop_app.py"
