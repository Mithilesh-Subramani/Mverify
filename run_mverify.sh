#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/Mverify"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3.11}"
fi
export PYTHONPATH="$ROOT/Mverify:$ROOT/Mcore${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" desktop_app.py
