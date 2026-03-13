# Verified Mode 測試計畫

這份文件定義目前 `analysis_mode=verified` 的最低驗收範圍。

## 驗收範圍

1. 會員權限
   - `free` 只能使用 `quick`
   - `premium` 可使用 `quick` 與 `verified`

2. Agent 決策鏈
   - `allowed_tools` 先由外部 resolver 計算
   - `ManagerAgent` 產生 `market_resolution` 與 `query_profile`
   - `BaseReActAgent` 依 policy 決定 `discovery_lookup` 或 `market_lookup`

3. 回應可觀測性
   - `analysis_mode`
   - `verification_status`
   - `used_tools`
   - `data_as_of`
   - `query_type`
   - `resolved_market`
   - `policy_path`

4. 前端模式守門
   - free 使用者 selector 應鎖住 `verified`
   - premium 使用者可選 `verified`

## 本機執行

```bash
./scripts/run_verified_mode_checks.sh
```

若你的 Python 不在 `.venv/bin/python`，可指定：

```bash
PYTHON_BIN=/path/to/python ./scripts/run_verified_mode_checks.sh
```

## E2E 依賴

若要讓 E2E 不再 skip，需先安裝 Playwright：

```bash
pip install playwright
python -m playwright install chromium
```

## CI

GitHub Actions workflow:

- [test-suite.yml](/Users/a1031737/agent_stock/stock_agent/.github/workflows/test-suite.yml)

目前 CI 會跑：

- 關鍵 backend tests
- verified mode Playwright E2E
