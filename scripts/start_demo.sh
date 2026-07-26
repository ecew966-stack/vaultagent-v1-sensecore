#!/usr/bin/env bash
set -euo pipefail
exec streamlit run demo/app.py --server.address=0.0.0.0 \
  --server.port="${STREAMLIT_PORT:-8501}"
