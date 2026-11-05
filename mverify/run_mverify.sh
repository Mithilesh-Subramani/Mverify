#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [[ -x "../.venv/bin/python" ]]; then PY="../.venv/bin/python"; elif [[ -x ".venv/bin/python" ]]; then PY=".venv/bin/python"; else PY="python3"; fi
exec "$PY" desktop_app.py
