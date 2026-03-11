#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"
LIBOMP_DIR="/opt/homebrew/opt/libomp/lib"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing virtualenv interpreter: $VENV_PY" >&2
  exit 1
fi

export DYLD_LIBRARY_PATH="$LIBOMP_DIR${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
exec "$VENV_PY" "$ROOT_DIR/run_streamlit.py" "$@"
