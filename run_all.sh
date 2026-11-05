#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/Mcore:$ROOT/Mverify${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT/Mcore"
python -m mcore.api.server &
MCORE_PID=$!
cleanup() {
  kill "$MCORE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
echo "Waiting for Mcore API..."
for i in $(seq 1 30); do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=1).read()" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8765/health').read().decode())"
cd "$ROOT/Mverify"
PY="${PYTHON:-python3.11}"
exec "$PY" desktop_app.py
