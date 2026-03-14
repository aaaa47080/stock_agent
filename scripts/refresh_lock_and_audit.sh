#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
PIP_TOOLS_CACHE_DIR="${PIP_TOOLS_CACHE_DIR:-/tmp/pip-tools-cache}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN=/path/to/python or create .venv first." >&2
  exit 1
fi

cd "$ROOT_DIR"

if ! "$PYTHON_BIN" -c "import piptools" >/dev/null 2>&1; then
  echo "pip-tools is required. Install with: $PYTHON_BIN -m pip install pip-tools" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "import pip_audit" >/dev/null 2>&1; then
  echo "pip-audit is required. Install with: $PYTHON_BIN -m pip install pip-audit" >&2
  exit 1
fi

echo "[1/3] Regenerate requirements.lock.txt"
PIP_TOOLS_CACHE_DIR="$PIP_TOOLS_CACHE_DIR" \
  "$PYTHON_BIN" -m piptools compile \
  --resolver=backtracking \
  --output-file=requirements.lock.txt \
  requirements.txt

echo "[2/3] Audit direct dependencies"
"$PYTHON_BIN" -m pip_audit -r requirements.txt --no-deps --disable-pip

echo "[3/3] Audit lockfile dependencies"
"$PYTHON_BIN" -m pip_audit -r requirements.lock.txt --no-deps --disable-pip

echo "Lock refresh and security audits completed."
