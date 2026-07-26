#!/usr/bin/env bash
set -euo pipefail
exec uvicorn src.api.main:app --host "${VAULTAGENT_API_HOST:-0.0.0.0}" \
  --port "${VAULTAGENT_API_PORT:-8080}"
