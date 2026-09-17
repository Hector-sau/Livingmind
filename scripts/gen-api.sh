#!/usr/bin/env bash
# Regenerate packages/api-client from the backend Pydantic contracts.
# Requires: backend venv (backend/.venv) and `npm install` in packages/api-client.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/backend/.venv/bin/python}"
if [ ! -x "$PY" ]; then PY="$(command -v python3)"; fi
"$PY" "$ROOT/backend/scripts/export_openapi.py"
if [ ! -d "$ROOT/packages/api-client/node_modules" ]; then
  (cd "$ROOT/packages/api-client" && npm install --no-audit --no-fund)
fi
(cd "$ROOT/packages/api-client" && npm run -s generate)
