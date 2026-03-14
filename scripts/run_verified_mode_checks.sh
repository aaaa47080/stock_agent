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

echo "[1/8] Python syntax checks"
"$PYTHON_BIN" -m py_compile \
  api/response_metadata.py \
  core/agents/analysis_policy.py \
  core/agents/base_react_agent.py \
  core/agents/manager.py \
  api/routers/analysis.py \
  scripts/check_asset_versions.py \
  pw_test/test_non_pi_browser_gate.py \
  pw_test/test_verified_mode_market_flow.py \
  tests/e2e/test_non_pi_browser_gate.py \
  tests/e2e/test_static_asset_load_smoke.py \
  tests/e2e/test_verified_mode_market_flow.py

echo "[2/8] Frontend syntax checks"
node --check web/js/auth.js
node --check web/js/chat-analysis.js
node --check web/js/pi-auth.js
node --check web/js/messages_page.js
node --check web/scam-tracker/js/scam-tracker.js

echo "[3/8] Static reference checks"
"$PYTHON_BIN" scripts/check_static_refs.py

echo "[4/8] Asset version consistency checks"
"$PYTHON_BIN" scripts/check_asset_versions.py

echo "[5/8] Dependency vulnerability audit (direct deps)"
if ! "$PYTHON_BIN" -c "import pip_audit" >/dev/null 2>&1; then
  echo "pip-audit is required. Install it with: $PYTHON_BIN -m pip install pip-audit" >&2
  exit 1
fi
"$PYTHON_BIN" -m pip_audit -r requirements.txt --no-deps --disable-pip

echo "[6/8] Dependency vulnerability audit (lockfile)"
if [[ ! -f requirements.lock.txt ]]; then
  echo "requirements.lock.txt not found. Generate it with:" >&2
  echo "  ./.venv/bin/pip-compile --resolver=backtracking --output-file=requirements.lock.txt requirements.txt" >&2
  exit 1
fi
"$PYTHON_BIN" -m pip_audit -r requirements.lock.txt --no-deps --disable-pip

echo "[7/8] Critical backend tests"
"$PYTHON_BIN" -m pytest -o addopts='' \
  tests/test_analysis_mode_access.py \
  tests/test_analysis_policy.py \
  tests/test_analysis_response_metadata.py \
  tests/test_api_models.py \
  tests/test_tool_access_resolver.py \
  -q

echo "[8/8] E2E stability tests"
"$PYTHON_BIN" -m pytest -o addopts='' \
  tests/e2e/test_non_pi_browser_gate.py \
  tests/e2e/test_static_asset_load_smoke.py \
  tests/e2e/test_verified_mode_market_flow.py \
  -q

echo "Verified mode checks completed."
