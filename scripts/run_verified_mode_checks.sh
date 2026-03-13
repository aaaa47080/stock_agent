#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN=/path/to/python or create .venv first." >&2
  exit 1
fi

cd "$ROOT_DIR"

echo "[1/4] Python syntax checks"
"$PYTHON_BIN" -m py_compile \
  api/response_metadata.py \
  core/agents/analysis_policy.py \
  core/agents/base_react_agent.py \
  core/agents/manager.py \
  api/routers/analysis.py \
  pw_test/test_verified_mode_market_flow.py \
  tests/e2e/test_verified_mode_market_flow.py

echo "[2/4] Frontend syntax checks"
node --check web/js/auth.js
node --check web/js/chat-analysis.js

echo "[3/4] Critical backend tests"
"$PYTHON_BIN" -m pytest -o addopts='' \
  tests/test_analysis_mode_access.py \
  tests/test_analysis_policy.py \
  tests/test_analysis_response_metadata.py \
  tests/test_api_models.py \
  tests/test_tool_access_resolver.py \
  -q

echo "[4/4] E2E verified mode tests"
"$PYTHON_BIN" -m pytest -o addopts='' \
  tests/e2e/test_verified_mode_market_flow.py \
  -q

echo "Verified mode checks completed."
