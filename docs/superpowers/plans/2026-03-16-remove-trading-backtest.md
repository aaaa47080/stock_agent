# Remove Trading Execution & Backtesting Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the OKX trading execution module and backtesting engine from the codebase, as neither is actively used and both add unnecessary complexity and risk.

**Architecture:** Two independent cleanup passes — backtest removal first (simpler, no downstream coupling), then trading removal (requires moving `okx_api_connector.py` to `utils/` since it's still needed for market data).

**Tech Stack:** Python, FastAPI, pytest

---

## Chunk 1: Remove Backtesting

### Task 1: Remove backtest files and dependency

**Files:**
- Delete: `analysis/backtest_engine.py`
- Delete: `analysis/simple_backtester.py`
- Delete: `tests/test_backtest_engine.py`
- Modify: `requirements.txt`
- Modify: `requirements.lock.txt`

- [ ] **Step 1: Delete backtest source files**

```bash
rm analysis/backtest_engine.py
rm analysis/simple_backtester.py
```

- [ ] **Step 2: Remove backtrader from requirements**

In `requirements.txt`, delete the line:
```
backtrader==1.9.78.123
```

In `requirements.lock.txt`, delete the line:
```
backtrader==1.9.78.123
```

- [ ] **Step 3: Delete backtest test file**

```bash
rm tests/test_backtest_engine.py
```

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "Remove: delete backtest engine files and backtrader dependency"
```

---

### Task 2: Remove backtest references from data_processor.py

**Files:**
- Modify: `data/data_processor.py`

- [ ] **Step 1: Remove import and usage**

In `data/data_processor.py`, remove the import:
```python
from analysis.backtest_engine import BacktestEngine
```
And remove any code that instantiates or calls `BacktestEngine` (around lines 361-362):
```python
# remove these two lines:
backtest_engine = BacktestEngine()
backtest_results = backtest_engine.run_all_strategies(df)
```
Also remove any variable assignment or usage of `backtest_results` in the same function.

- [ ] **Step 2: Run tests to verify no breakage**

```bash
pytest tests/ -x -q --ignore=tests/test_trade_executor.py --ignore=tests/test_router_trading.py --ignore=tests/test_okx_api_connector.py 2>&1 | head -40
```

Expected: no import errors related to backtest_engine

- [ ] **Step 3: Commit**

```bash
git add data/data_processor.py
git commit -m "Remove: backtest_engine usage from data_processor"
```

---

### Task 3: Remove backtest from crypto_modules analysis

**Files:**
- Modify: `core/tools/crypto_modules/analysis.py`

- [ ] **Step 1: Remove conditional import and usage**

In `core/tools/crypto_modules/analysis.py` around line 186, remove:
```python
from analysis.backtest_engine import BacktestEngine
```
And remove any code block that uses `BacktestEngine` in that file. Keep the surrounding logic intact — just remove the backtest branch.

- [ ] **Step 2: Verify**

```bash
python -c "from core.tools.crypto_modules.analysis import *" 2>&1
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add core/tools/crypto_modules/analysis.py
git commit -m "Remove: backtest_engine reference from crypto_modules/analysis"
```

---

### Task 4: Remove /backtest endpoint from analysis router

**Files:**
- Modify: `api/routers/analysis.py`
- Modify: `api/models.py`

- [ ] **Step 1: Remove BacktestRequest import and endpoint**

In `api/routers/analysis.py`:
- Remove `BacktestRequest` from the import on line 8:
  ```python
  # before:
  from api.models import QueryRequest, BacktestRequest
  # after:
  from api.models import QueryRequest
  ```
- Delete the entire `run_backtest_api` function (around line 407) and its `@router.post(...)` decorator.

- [ ] **Step 2: Remove BacktestRequest from models**

In `api/models.py`, delete the `BacktestRequest` class (around line 50).

- [ ] **Step 3: Verify router loads**

```bash
python -c "from api.routers.analysis import router" 2>&1
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add api/routers/analysis.py api/models.py
git commit -m "Remove: /backtest endpoint and BacktestRequest model"
```

---

## Chunk 2: Remove Trading Execution

### Task 5: Move OKXAPIConnector to utils/

`okx_api_connector.py` is still needed for market data (funding rates, OKX prices). It must be moved out of `trading/` before deleting that directory.

**Files:**
- Move: `trading/okx_api_connector.py` → `utils/okx_api_connector.py`
- Modify: `api_server.py`
- Modify: `utils/okx_auth.py`
- Modify: `api/services.py`
- Modify: `api/routers/market/rest.py`
- Modify: `api/routers/system.py`
- Modify: `tests/test_okx_api_connector.py`

- [ ] **Step 1: Move the file**

```bash
cp trading/okx_api_connector.py utils/okx_api_connector.py
```

- [ ] **Step 2: Update all imports**

Change `from trading.okx_api_connector import OKXAPIConnector` → `from utils.okx_api_connector import OKXAPIConnector` in each of these files:
- `api_server.py`
- `utils/okx_auth.py`
- `api/services.py`
- `api/routers/market/rest.py`
- `api/routers/system.py`
- `tests/test_okx_api_connector.py`

- [ ] **Step 3: Verify import works**

```bash
python -c "from utils.okx_api_connector import OKXAPIConnector; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add utils/okx_api_connector.py api_server.py utils/okx_auth.py api/services.py api/routers/market/rest.py api/routers/system.py tests/test_okx_api_connector.py
git commit -m "Refactor: move OKXAPIConnector from trading/ to utils/"
```

---

### Task 6: Delete trading module

**Files:**
- Delete: `trading/okx_api_connector.py` (already copied)
- Delete: `trading/trade_executor.py`
- Delete: `trading/okx_auto_trader.py`
- Delete: `trading/__init__.py`
- Delete: `api/routers/trading.py`
- Delete: `tests/test_trade_executor.py`
- Delete: `tests/test_router_trading.py`

- [ ] **Step 1: Delete trading directory files**

```bash
rm trading/okx_api_connector.py
rm trading/trade_executor.py
rm trading/okx_auto_trader.py
rm trading/__init__.py
rmdir trading/
```

- [ ] **Step 2: Delete trading router and tests**

```bash
rm api/routers/trading.py
rm tests/test_trade_executor.py
rm tests/test_router_trading.py
```

- [ ] **Step 3: Remove trading router from api_server.py**

In `api_server.py`, make two changes:

Change the import line:
```python
# before:
from api.routers import system, analysis, market, trading, user, twstock, usstock
# after:
from api.routers import system, analysis, market, user, twstock, usstock
```

Remove the router registration line:
```python
app.include_router(trading.router)
```

- [ ] **Step 4: Verify server starts cleanly**

```bash
python -c "from api_server import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -x -q --ignore=tests/pw_test 2>&1 | tail -20
```

Expected: no failures related to trading or backtest

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "Remove: OKX trading execution module and trading router"
```

---

## Final Verification

- [ ] **Verify no stale references remain**

```bash
grep -r "from trading\." . --include="*.py" | grep -v ".bak"
grep -r "backtest_engine\|simple_backtester\|backtrader" . --include="*.py" | grep -v ".bak"
```

Expected: no output

- [ ] **Run full test suite one more time**

```bash
pytest tests/ -q --ignore=tests/pw_test 2>&1 | tail -20
```

- [ ] **Final commit if any cleanup needed**

```bash
git add -u
git commit -m "Cleanup: final stale reference removal after trading/backtest purge"
```
