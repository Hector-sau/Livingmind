#!/usr/bin/env bash
# Regenerate packages/api-client from the backend Pydantic contracts.
# Requires: backend venv (backend/.venv) and `npm install` in packages/api-client.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/backend/.venv/bin/python}"
if [ ! -x "$PY" ]; then PY="$(command -v python3)"; fi
if "$PY" -c 'import fastapi, pydantic, sqlalchemy' >/dev/null 2>&1; then
  "$PY" "$ROOT/backend/scripts/export_openapi.py"
elif command -v docker >/dev/null 2>&1 && docker image inspect livingmind-api:dev >/dev/null 2>&1; then
  echo "backend Python dependencies are unavailable; exporting with livingmind-api:dev"
  docker run --rm -v "$ROOT:/workspace" -w /workspace livingmind-api:dev \
    python backend/scripts/export_openapi.py
else
  echo "Backend Python dependencies are missing. Install backend/requirements.txt or build livingmind-api:dev." >&2
  exit 1
fi
if [ ! -d "$ROOT/packages/api-client/node_modules" ]; then
  (cd "$ROOT/packages/api-client" && npm install --no-audit --no-fund)
fi
(cd "$ROOT/packages/api-client" && npm run -s generate)
