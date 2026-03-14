#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8080}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-10}"
SMOKE_AUTH_TOKEN="${SMOKE_AUTH_TOKEN:-}"
SMOKE_EXPECT_MODE="${SMOKE_EXPECT_MODE:-verified}"

tmp_body="$(mktemp)"
trap 'rm -f "$tmp_body"' EXIT

request() {
  local method="$1"
  local path="$2"
  local auth_header=()
  if [[ -n "${SMOKE_AUTH_TOKEN}" ]]; then
    auth_header=(-H "Authorization: Bearer ${SMOKE_AUTH_TOKEN}")
  fi

  curl -sS \
    -o "$tmp_body" \
    -w "%{http_code}" \
    --max-time "${TIMEOUT_SECONDS}" \
    -X "$method" \
    "${auth_header[@]}" \
    "${API_URL}${path}" || echo "000"
}

echo "Smoke target: ${API_URL}"

health_code="$(request GET /health)"
if [[ "$health_code" != "200" ]]; then
  echo "FAIL: /health expected 200, got ${health_code}"
  exit 1
fi
echo "PASS: /health"

ready_code="$(request GET /ready)"
if [[ "$ready_code" != "200" ]]; then
  echo "FAIL: /ready expected 200, got ${ready_code}"
  exit 1
fi
echo "PASS: /ready"

pi_code="$(request GET /validation-key.txt)"
if [[ "$pi_code" != "200" ]]; then
  echo "FAIL: /validation-key.txt expected 200, got ${pi_code}"
  exit 1
fi
echo "PASS: /validation-key.txt"

if [[ -n "${SMOKE_AUTH_TOKEN}" ]]; then
  modes_code="$(request GET /api/analyze/modes)"
  if [[ "$modes_code" != "200" ]]; then
    echo "FAIL: /api/analyze/modes expected 200, got ${modes_code}"
    exit 1
  fi

  if ! grep -q "\"${SMOKE_EXPECT_MODE}\"" "$tmp_body"; then
    echo "FAIL: /api/analyze/modes does not include expected mode '${SMOKE_EXPECT_MODE}'"
    echo "Body:"
    cat "$tmp_body"
    exit 1
  fi
  echo "PASS: /api/analyze/modes includes '${SMOKE_EXPECT_MODE}'"
else
  modes_code="$(request GET /api/analyze/modes)"
  if [[ "$modes_code" != "401" && "$modes_code" != "403" ]]; then
    echo "FAIL: /api/analyze/modes without auth expected 401/403, got ${modes_code}"
    exit 1
  fi
  echo "PASS: /api/analyze/modes access control (unauth blocked)"
fi

echo "Post-deploy smoke checks passed."
