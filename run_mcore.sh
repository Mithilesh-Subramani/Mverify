#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/Mcore${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT/Mcore"
exec python -m mcore.api.server
