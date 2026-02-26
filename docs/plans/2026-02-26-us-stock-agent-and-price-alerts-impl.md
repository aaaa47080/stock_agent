# USStockAgent + Price Alert System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Activate the already-written USStockAgent for full three-market coverage, then add a price alert system (target price + % change, three markets, one-shot or persistent) backed by the existing notification + WebSocket infrastructure.

**Architecture:** USStockAgent activation is pure bootstrap.py wiring — tools already exist in `core/tools/us_stock_tools.py`, agent class in `core/agents/agents/us_stock_agent.py`. Price alerts add a new DB table + API router + background polling task + watchlist UI extension. All notification delivery reuses `create_and_push_notification()` from `api/routers/notifications.py`.

**Tech Stack:** FastAPI, PostgreSQL (psycopg2), asyncio background tasks, yfinance (US), existing tw_stock_tools / crypto_tools for price fetch, vanilla JS watchlist UI.

---

## Part A: USStockAgent Activation

---

### Task A1: Import US stock tool functions into bootstrap

**Files:**
- Modify: `core/agents/bootstrap.py` (line ~21, imports section)

**Context:** `us_stock_price`, `us_technical_analysis`, etc. live in `core/tools/us_stock_tools.py`. They are NOT imported anywhere in bootstrap.py yet. The TW stock tools follow the same pattern (imported at top, registered with ToolMetadata blocks).

**Step 1: Add import line**

In `core/agents/bootstrap.py`, after the existing imports block (around line 22), add:

```python
# Import @tool functions — US stock
from core.tools.us_stock_tools import (
    us_stock_price, us_technical_analysis, us_fundamentals,
    us_earnings, us_news, us_institutional_holders, us_insider_transactions,
)
```

**Step 2: Verify import works**

```bash
cd D:/okx/stock_agent
python -c "from core.agents.bootstrap import bootstrap; print('OK')"
```

Expected: `OK` (no ImportError)

**Step 3: Commit**

```bash
git add core/agents/bootstrap.py
git commit -m "feat(us-stock): import US stock tool functions into bootstrap"
```

---

### Task A2: Register US stock tools in ToolRegistry

**Files:**
- Modify: `core/agents/bootstrap.py` (after TW Stock Tools block, before `# ── Wrap LLM ──`)

**Context:** Each tool needs a `ToolMetadata` entry. Look at how TW stock tools are registered (lines ~152–182) — same pattern. `allowed_agents` controls which agents can call a tool.

**Step 1: Add US stock tools block**

After the `# ── Register TW Stock Tools ──` block in `bootstrap()`, add:

```python
    # ── Register US Stock Tools ──
    tool_registry.register(ToolMetadata(
        name="us_stock_price",
        description="獲取美股即時價格數據（15分鐘延遲，Yahoo Finance）",
        input_schema={"symbol": "str"},
        handler=us_stock_price,
        allowed_agents=["us_stock", "chat"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_technical_analysis",
        description="計算美股技術指標：RSI、MACD、布林帶、均線",
        input_schema={"symbol": "str"},
        handler=us_technical_analysis,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_fundamentals",
        description="獲取美股基本面：P/E、EPS、ROE、市值、股息率",
        input_schema={"symbol": "str"},
        handler=us_fundamentals,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_earnings",
        description="獲取美股財報數據和財報日曆",
        input_schema={"symbol": "str"},
        handler=us_earnings,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_news",
        description="獲取美股相關最新新聞",
        input_schema={"symbol": "str", "limit": "int (optional, default 5)"},
        handler=us_news,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_institutional_holders",
        description="獲取美股機構持倉數據",
        input_schema={"symbol": "str"},
        handler=us_institutional_holders,
        allowed_agents=["us_stock"],
    ))
    tool_registry.register(ToolMetadata(
        name="us_insider_transactions",
        description="獲取美股內部人交易記錄",
        input_schema={"symbol": "str"},
        handler=us_insider_transactions,
        allowed_agents=["us_stock"],
    ))
```

Also update `get_current_time_taipei` registration — add `"us_stock"` to its `allowed_agents` list.

**Step 2: Verify bootstrap runs without error**

```bash
python -c "
from unittest.mock import MagicMock
from core.agents.bootstrap import bootstrap
mgr = bootstrap(MagicMock())
tools = [t for t in mgr.agent_registry.list_all()]
print([a.name for a in tools])
"
```

Expected output includes `us_stock` agent (not yet — this verifies no crash).

**Step 3: Commit**

```bash
git add core/agents/bootstrap.py
git commit -m "feat(us-stock): register 7 US stock tools in ToolRegistry"
```

---

### Task A3: Register USStockAgent in AgentRegistry

**Files:**
- Modify: `core/agents/bootstrap.py` (the commented-out us_stock block, lines ~258–266)

**Context:** `USStockAgent` class is fully implemented in `core/agents/agents/us_stock_agent.py`. The class is already imported via `core/agents/agents/__init__.py`. Just uncomment and update the registration.

**Step 1: Replace the commented block**

Remove the comment block and replace with:

```python
    us = USStockAgent(lang_llm, tool_registry)
    agent_registry.register(us, AgentMetadata(
        name="us_stock",
        display_name="US Stock Agent",
        description="美股全方位分析 — 即時價格（15分鐘延遲）、技術指標（RSI/MACD/MA/布林帶）、"
                    "基本面（P/E、EPS、ROE、市值）、財報數據與日曆、機構持倉、"
                    "內部人交易、最新新聞。適合 AAPL/TSLA/NVDA/TSM/MSFT/AMZN/GOOGL/META 等 "
                    "NYSE/NASDAQ 股票查詢，接受股票代號或公司名稱（如 Apple、Tesla）。",
        capabilities=[
            "美股", "US stock", "NYSE", "NASDAQ",
            "AAPL", "TSLA", "NVDA", "TSM", "MSFT", "AMZN", "GOOGL", "META",
            "標普500", "道瓊", "那斯達克", "S&P500", "Apple", "Tesla", "Nvidia",
        ],
        allowed_tools=[
            "us_stock_price", "us_technical_analysis", "us_fundamentals",
            "us_earnings", "us_news", "us_institutional_holders",
            "us_insider_transactions", "get_current_time_taipei",
        ],
        priority=8,
    ))
```

**Step 2: Write the test**

In `tests/test_multi_market_integration.py`, add to `test_bootstrap_creates_all_agents`:

```python
    assert "us_stock" in agent_names, "USStockAgent not registered"
```

(This test was previously removed — now re-add it since the agent is active.)

**Step 3: Run the test**

```bash
python -m pytest tests/test_multi_market_integration.py::test_bootstrap_creates_all_agents -v --no-cov
```

Expected: PASS

**Step 4: Commit**

```bash
git add core/agents/bootstrap.py tests/test_multi_market_integration.py
git commit -m "feat(us-stock): activate USStockAgent in bootstrap registry"
```

---

### Task A4: Smoke test routing end-to-end

**Files:**
- No file changes — manual verification only

**Step 1: Run quick routing test**

```bash
python -c "
from unittest.mock import MagicMock, patch
from core.agents.bootstrap import bootstrap

mock_llm = MagicMock()
mock_llm.invoke.return_value = MagicMock(content='{\"market\": \"us_stock\", \"symbol\": \"AAPL\", \"intent\": \"price\"}')
mgr = bootstrap(mock_llm)

from core.agents.agent_registry import AgentRegistry
agents = {a.name: a for a in mgr.agent_registry.list_all()}
print('Registered agents:', list(agents.keys()))
assert 'us_stock' in agents, 'FAIL: us_stock not registered'
print('PASS: us_stock agent registered')
print('US stock tools:', agents['us_stock'].metadata.allowed_tools)
"
```

Expected: prints `us_stock` in agent list with 8 tools.

**Step 2: Commit Part A tag**

```bash
git commit --allow-empty -m "feat(us-stock): Part A complete — USStockAgent fully activated"
```

---

## Part B: Price Alert System

---

### Task B1: Create price_alerts database module

**Files:**
- Create: `core/database/price_alerts.py`

**Step 1: Write the test first**

Add to `tests/test_database_price_alerts.py`:

```python
"""Tests for price_alerts database functions."""
import pytest
from unittest.mock import MagicMock, patch, call
from core.database.price_alerts import (
    create_price_alerts_table,
    create_alert,
    get_user_alerts,
    delete_alert,
    get_active_alerts,
    mark_alert_triggered,
)


class TestCreateAlert:
    def test_create_alert_returns_dict_with_id(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            result = create_alert(
                user_id="u1",
                symbol="AAPL",
                market="us_stock",
                condition="above",
                target=200.0,
                repeat=False,
            )

        assert "id" in result
        assert result["symbol"] == "AAPL"
        assert result["market"] == "us_stock"
        assert result["condition"] == "above"
        assert result["target"] == 200.0
        assert result["repeat"] == 0

    def test_invalid_market_raises(self):
        with pytest.raises(ValueError, match="market"):
            create_alert("u1", "AAPL", "invalid_market", "above", 200.0)

    def test_invalid_condition_raises(self):
        with pytest.raises(ValueError, match="condition"):
            create_alert("u1", "AAPL", "us_stock", "invalid_cond", 200.0)


class TestGetUserAlerts:
    def test_returns_list(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            result = get_user_alerts("u1")

        assert isinstance(result, list)


class TestDeleteAlert:
    def test_delete_returns_bool(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            result = delete_alert("alert-id", "u1")

        assert isinstance(result, bool)


class TestMarkAlertTriggered:
    def test_one_shot_deletes_alert(self):
        """repeat=0 alert should be deleted when triggered."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            mark_alert_triggered("alert-id", repeat=False)

        # Should call DELETE
        call_args = mock_cursor.execute.call_args[0][0]
        assert "DELETE" in call_args.upper()

    def test_persistent_sets_triggered_flag(self):
        """repeat=1 alert should set triggered=1, not delete."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            mark_alert_triggered("alert-id", repeat=True)

        call_args = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in call_args.upper()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_database_price_alerts.py -v --no-cov
```

Expected: `ModuleNotFoundError: No module named 'core.database.price_alerts'`

**Step 3: Implement `core/database/price_alerts.py`**

```python
"""
Price Alerts Database Module

Manages user price alerts for Crypto, TW Stock, and US Stock markets.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any

from .connection import get_connection

VALID_MARKETS = {"crypto", "tw_stock", "us_stock"}
VALID_CONDITIONS = {"above", "below", "change_pct_up", "change_pct_down"}


def create_price_alerts_table() -> None:
    """Create price_alerts table if it doesn't exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    symbol      TEXT NOT NULL,
                    market      TEXT NOT NULL,
                    condition   TEXT NOT NULL,
                    target      REAL NOT NULL,
                    repeat      INTEGER NOT NULL DEFAULT 0,
                    triggered   INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    CONSTRAINT fk_alert_user
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_price_alerts_user
                    ON price_alerts(user_id);
                CREATE INDEX IF NOT EXISTS idx_price_alerts_active
                    ON price_alerts(triggered) WHERE triggered = 0;
            """)
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def create_alert(
    user_id: str,
    symbol: str,
    market: str,
    condition: str,
    target: float,
    repeat: bool = False,
) -> Dict[str, Any]:
    """Create a new price alert. Returns the created alert dict."""
    if market not in VALID_MARKETS:
        raise ValueError(f"Invalid market '{market}'. Must be one of {VALID_MARKETS}")
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Invalid condition '{condition}'. Must be one of {VALID_CONDITIONS}")

    alert_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    repeat_int = 1 if repeat else 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO price_alerts (id, user_id, symbol, market, condition, target, repeat, triggered, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s)
                """,
                (alert_id, user_id, symbol.upper(), market, condition, target, repeat_int, created_at),
            )
            conn.commit()
    finally:
        conn.close()

    return {
        "id": alert_id,
        "user_id": user_id,
        "symbol": symbol.upper(),
        "market": market,
        "condition": condition,
        "target": target,
        "repeat": repeat_int,
        "triggered": 0,
        "created_at": created_at,
    }


def get_user_alerts(user_id: str) -> List[Dict[str, Any]]:
    """Return all alerts for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, symbol, market, condition, target, repeat, triggered, created_at "
                "FROM price_alerts WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "user_id": r[1], "symbol": r[2],
                    "market": r[3], "condition": r[4], "target": r[5],
                    "repeat": r[6], "triggered": r[7], "created_at": r[8],
                }
                for r in rows
            ]
    finally:
        conn.close()


def delete_alert(alert_id: str, user_id: str) -> bool:
    """Delete an alert. Returns True if deleted, False if not found/unauthorized."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM price_alerts WHERE id = %s AND user_id = %s",
                (alert_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_active_alerts() -> List[Dict[str, Any]]:
    """Return all alerts that have not been permanently deactivated (for background task)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # one-shot: triggered=0
            # persistent (repeat=1): always active (triggered resets each cycle)
            cur.execute(
                "SELECT id, user_id, symbol, market, condition, target, repeat, triggered, created_at "
                "FROM price_alerts WHERE triggered = 0 OR repeat = 1"
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "user_id": r[1], "symbol": r[2],
                    "market": r[3], "condition": r[4], "target": r[5],
                    "repeat": r[6], "triggered": r[7], "created_at": r[8],
                }
                for r in rows
            ]
    finally:
        conn.close()


def mark_alert_triggered(alert_id: str, repeat: bool) -> None:
    """
    Handle triggered alert:
    - repeat=False (one-shot): delete the alert
    - repeat=True (persistent): reset triggered=0 so it can fire again next cycle
      (we keep triggered=0 always for persistent; the background task handles cooldown)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if not repeat:
                cur.execute("DELETE FROM price_alerts WHERE id = %s", (alert_id,))
            else:
                # For persistent alerts, we set triggered=1 temporarily to prevent
                # immediate re-trigger within the same cycle. The task resets it next cycle.
                cur.execute(
                    "UPDATE price_alerts SET triggered = 1 WHERE id = %s",
                    (alert_id,),
                )
            conn.commit()
    finally:
        conn.close()


def count_user_alerts(user_id: str) -> int:
    """Count total alerts for a user (for limit enforcement)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM price_alerts WHERE user_id = %s", (user_id,))
            return cur.fetchone()[0]
    finally:
        conn.close()
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_database_price_alerts.py -v --no-cov
```

Expected: All PASS

**Step 5: Commit**

```bash
git add core/database/price_alerts.py tests/test_database_price_alerts.py
git commit -m "feat(alerts): add price_alerts DB module with CRUD functions"
```

---

### Task B2: Export from core/database/__init__.py and initialize table

**Files:**
- Modify: `core/database/__init__.py`
- Modify: `api/routers/alerts.py` (will be created in B3, table init goes there)

**Step 1: Add exports to `core/database/__init__.py`**

At the end of `core/database/__init__.py`, add:

```python
# Price Alerts
from .price_alerts import (
    create_price_alerts_table,
    create_alert,
    get_user_alerts,
    delete_alert,
    get_active_alerts,
    mark_alert_triggered,
    count_user_alerts,
)
```

**Step 2: Verify import**

```bash
python -c "from core.database import create_alert, get_active_alerts; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add core/database/__init__.py
git commit -m "feat(alerts): export price_alerts functions from core.database"
```

---

### Task B3: Create alerts API router

**Files:**
- Create: `api/routers/alerts.py`
- Modify: `api/models.py` (add CreateAlertRequest)
- Modify: `api_server.py` (register router)

**Step 1: Write the test**

Create `tests/test_router_alerts.py`:

```python
"""Tests for price alerts API router."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create test client with mocked auth."""
    from api_server import app
    with patch("api.deps.get_current_user", return_value={"user_id": "test-user-001", "username": "TestUser"}):
        with TestClient(app) as c:
            yield c


class TestCreateAlert:
    def test_create_alert_success(self, client):
        with patch("api.routers.alerts.count_user_alerts", return_value=0):
            with patch("api.routers.alerts.create_alert", return_value={
                "id": "alert-1", "symbol": "AAPL", "market": "us_stock",
                "condition": "above", "target": 200.0, "repeat": 0,
                "triggered": 0, "created_at": "2026-02-26T00:00:00",
            }):
                resp = client.post("/api/alerts", json={
                    "symbol": "AAPL",
                    "market": "us_stock",
                    "condition": "above",
                    "target": 200.0,
                    "repeat": False,
                }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["alert"]["symbol"] == "AAPL"

    def test_create_alert_limit_exceeded(self, client):
        with patch("api.routers.alerts.count_user_alerts", return_value=20):
            resp = client.post("/api/alerts", json={
                "symbol": "BTC",
                "market": "crypto",
                "condition": "above",
                "target": 100000.0,
            }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 400

    def test_create_alert_invalid_market(self, client):
        resp = client.post("/api/alerts", json={
            "symbol": "BTC",
            "market": "invalid",
            "condition": "above",
            "target": 100000.0,
        }, headers={"Authorization": "Bearer test"})
        assert resp.status_code == 422


class TestGetAlerts:
    def test_get_alerts_returns_list(self, client):
        with patch("api.routers.alerts.get_user_alerts", return_value=[]):
            resp = client.get("/api/alerts", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert "alerts" in resp.json()


class TestDeleteAlert:
    def test_delete_alert_success(self, client):
        with patch("api.routers.alerts.delete_alert", return_value=True):
            resp = client.delete("/api/alerts/alert-1", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200

    def test_delete_alert_not_found(self, client):
        with patch("api.routers.alerts.delete_alert", return_value=False):
            resp = client.delete("/api/alerts/nonexistent", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 404
```

**Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_router_alerts.py -v --no-cov
```

Expected: fails (module not found or 404)

**Step 3: Add `CreateAlertRequest` to `api/models.py`**

At the end of `api/models.py` add:

```python
from typing import Literal

class CreateAlertRequest(BaseModel):
    symbol: str
    market: Literal["crypto", "tw_stock", "us_stock"]
    condition: Literal["above", "below", "change_pct_up", "change_pct_down"]
    target: float
    repeat: bool = False
```

**Step 4: Create `api/routers/alerts.py`**

```python
"""
Price Alerts API Router

Endpoints for managing user price alerts.
"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from api.deps import get_current_user
from api.models import CreateAlertRequest
from core.database import (
    create_alert, get_user_alerts, delete_alert,
    count_user_alerts, create_price_alerts_table,
)
from api.utils import logger
from functools import partial

router = APIRouter()

# Initialize table on import (same pattern as notifications router)
try:
    create_price_alerts_table()
    logger.info("Price alerts table initialized")
except Exception as e:
    logger.warning(f"Could not initialize price_alerts table: {e}")

MAX_ALERTS_PER_USER = 20


@router.post("/api/alerts")
async def create_alert_endpoint(
    request: CreateAlertRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new price alert."""
    user_id = current_user["user_id"]
    loop = asyncio.get_running_loop()

    # Enforce limit
    count = await loop.run_in_executor(None, count_user_alerts, user_id)
    if count >= MAX_ALERTS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"已達警報上限（最多 {MAX_ALERTS_PER_USER} 個），請刪除舊警報後再試。"
        )

    try:
        alert = await loop.run_in_executor(
            None,
            partial(
                create_alert,
                user_id=user_id,
                symbol=request.symbol,
                market=request.market,
                condition=request.condition,
                target=request.target,
                repeat=request.repeat,
            ),
        )
        return {"success": True, "alert": alert}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"建立警報失敗: {e}")
        raise HTTPException(status_code=500, detail="建立警報失敗")


@router.get("/api/alerts")
async def get_alerts_endpoint(current_user: dict = Depends(get_current_user)):
    """Get all alerts for the current user."""
    user_id = current_user["user_id"]
    loop = asyncio.get_running_loop()
    try:
        alerts = await loop.run_in_executor(None, get_user_alerts, user_id)
        return {"success": True, "alerts": alerts}
    except Exception as e:
        logger.error(f"獲取警報失敗: {e}")
        raise HTTPException(status_code=500, detail="獲取警報失敗")


@router.delete("/api/alerts/{alert_id}")
async def delete_alert_endpoint(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a specific alert (ownership enforced)."""
    user_id = current_user["user_id"]
    loop = asyncio.get_running_loop()
    try:
        deleted = await loop.run_in_executor(None, partial(delete_alert, alert_id, user_id))
        if not deleted:
            raise HTTPException(status_code=404, detail="警報不存在或無權限刪除")
        return {"success": True, "message": "警報已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除警報失敗: {e}")
        raise HTTPException(status_code=500, detail="刪除警報失敗")
```

**Step 5: Register router in `api_server.py`**

In `api_server.py`, add after the existing router imports:

```python
from api.routers.alerts import router as alerts_router
```

And in the router registration section (where `app.include_router(...)` calls are), add:

```bash
# search for: app.include_router(notifications_router)
# add after it:
app.include_router(alerts_router)
```

**Step 6: Run tests**

```bash
python -m pytest tests/test_router_alerts.py -v --no-cov
```

Expected: All PASS

**Step 7: Commit**

```bash
git add api/routers/alerts.py api/models.py api_server.py core/database/__init__.py tests/test_router_alerts.py
git commit -m "feat(alerts): add price alerts API router (POST/GET/DELETE /api/alerts)"
```

---

### Task B4: Add background alert checker task

**Files:**
- Create: `api/services/alert_checker.py` (or add to `api/services.py`)
- Modify: `api_server.py` (hook into lifespan)

**Context:** The existing background tasks (screener, pulse, funding rate) all follow the `async def X_task(): while True: await asyncio.sleep(N); ...` pattern, launched via `asyncio.create_task()` in `lifespan`. Price alerts use the same pattern. Price fetching reuses existing tool functions.

**Step 1: Write the test**

Create `tests/test_alert_checker.py`:

```python
"""Tests for price alert background checker."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


class TestIsConditionMet:
    """Test the condition evaluation logic."""

    def test_above_triggered(self):
        from api.services.alert_checker import is_condition_met
        assert is_condition_met("above", 200.0, current_price=205.0, open_price=195.0) is True

    def test_above_not_triggered(self):
        from api.services.alert_checker import is_condition_met
        assert is_condition_met("above", 200.0, current_price=195.0, open_price=190.0) is False

    def test_below_triggered(self):
        from api.services.alert_checker import is_condition_met
        assert is_condition_met("below", 180.0, current_price=175.0, open_price=185.0) is True

    def test_below_not_triggered(self):
        from api.services.alert_checker import is_condition_met
        assert is_condition_met("below", 180.0, current_price=185.0, open_price=182.0) is False

    def test_change_pct_up_triggered(self):
        from api.services.alert_checker import is_condition_met
        # 10% up: current=110, open=100 → (110-100)/100*100 = 10%
        assert is_condition_met("change_pct_up", 5.0, current_price=110.0, open_price=100.0) is True

    def test_change_pct_up_not_triggered(self):
        from api.services.alert_checker import is_condition_met
        # 3% up: current=103, open=100 → 3% < 5%
        assert is_condition_met("change_pct_up", 5.0, current_price=103.0, open_price=100.0) is False

    def test_change_pct_down_triggered(self):
        from api.services.alert_checker import is_condition_met
        # 10% down: current=90, open=100 → (100-90)/100*100 = 10%
        assert is_condition_met("change_pct_down", 5.0, current_price=90.0, open_price=100.0) is True

    def test_zero_open_price_returns_false(self):
        from api.services.alert_checker import is_condition_met
        assert is_condition_met("change_pct_up", 5.0, current_price=105.0, open_price=0.0) is False


class TestBuildAlertMessage:
    def test_above_message(self):
        from api.services.alert_checker import build_alert_body
        alert = {"symbol": "AAPL", "condition": "above", "target": 200.0}
        msg = build_alert_body(alert, current_price=205.50)
        assert "AAPL" in msg
        assert "205" in msg

    def test_change_pct_message(self):
        from api.services.alert_checker import build_alert_body
        alert = {"symbol": "BTC", "condition": "change_pct_up", "target": 5.0}
        msg = build_alert_body(alert, current_price=55000.0)
        assert "BTC" in msg
```

**Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_alert_checker.py -v --no-cov
```

Expected: ImportError (module doesn't exist yet)

**Step 3: Create `api/services/` package (or add to `api/services.py`)**

If `api/services/` doesn't exist as a package, add the checker as a standalone file. Check:

```bash
ls api/services* 2>/dev/null || echo "api/services.py exists as file"
```

If `api/services.py` is a file (not a directory), create a separate file `api/alert_checker.py`.

Create `api/services/alert_checker.py` (or `api/alert_checker.py` if services is not a package):

```python
"""
Price Alert Background Checker

Polls current prices every 60 seconds and fires notifications when
alert conditions are met. Integrates with existing notification system.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60  # seconds


def is_condition_met(
    condition: str,
    target: float,
    current_price: float,
    open_price: float,
) -> bool:
    """Evaluate whether an alert condition is triggered."""
    if condition == "above":
        return current_price >= target
    if condition == "below":
        return current_price <= target
    if open_price == 0:
        return False
    pct_change = (current_price - open_price) / open_price * 100
    if condition == "change_pct_up":
        return pct_change >= target
    if condition == "change_pct_down":
        return (-pct_change) >= target
    return False


def build_alert_body(alert: dict, current_price: float) -> str:
    """Build human-readable notification body for a triggered alert."""
    symbol = alert["symbol"]
    condition = alert["condition"]
    target = alert["target"]

    condition_labels = {
        "above": f"已突破目標價 {target:,.2f}",
        "below": f"已跌破目標價 {target:,.2f}",
        "change_pct_up": f"漲幅已達 {target:.1f}%",
        "change_pct_down": f"跌幅已達 {target:.1f}%",
    }
    label = condition_labels.get(condition, "條件已觸發")
    return f"{symbol} {label}，當前價格：{current_price:,.2f}"


async def _fetch_price(symbol: str, market: str) -> Optional[tuple[float, float]]:
    """
    Fetch (current_price, open_price) for a symbol.
    Returns None on failure.
    """
    loop = asyncio.get_running_loop()
    try:
        if market == "crypto":
            from core.tools.crypto_tools import get_crypto_price
            result = await loop.run_in_executor(None, get_crypto_price, symbol)
            price = result.get("price") or result.get("last")
            return (float(price), float(price)) if price else None

        if market == "tw_stock":
            from core.tools.tw_stock_tools import tw_stock_price
            result = await loop.run_in_executor(None, tw_stock_price, symbol)
            price = result.get("close") or result.get("price")
            open_p = result.get("open", price)
            return (float(price), float(open_p)) if price else None

        if market == "us_stock":
            from core.tools.us_stock_tools import us_stock_price
            result = await loop.run_in_executor(None, us_stock_price, symbol)
            price = result.get("regularMarketPrice") or result.get("price")
            open_p = result.get("regularMarketOpen") or result.get("open", price)
            return (float(price), float(open_p)) if price else None

    except Exception as e:
        logger.debug(f"Price fetch failed for {symbol} ({market}): {e}")
    return None


async def price_alert_check_task():
    """
    Background task: check all active alerts every POLL_INTERVAL seconds.
    Launched from api_server.py lifespan.
    """
    # Delay startup to let DB initialize
    await asyncio.sleep(30)
    logger.info("✅ Price alert checker started")

    while True:
        try:
            await _check_all_alerts()
        except Exception as e:
            logger.error(f"Alert checker error: {e}")
        await asyncio.sleep(POLL_INTERVAL)


async def _check_all_alerts():
    """Run one check cycle across all active alerts."""
    from core.database import get_active_alerts, mark_alert_triggered
    from api.routers.notifications import create_and_push_notification
    import asyncio

    loop = asyncio.get_running_loop()
    alerts = await loop.run_in_executor(None, get_active_alerts)

    if not alerts:
        return

    logger.debug(f"Checking {len(alerts)} active alerts")

    for alert in alerts:
        prices = await _fetch_price(alert["symbol"], alert["market"])
        if prices is None:
            continue

        current_price, open_price = prices
        triggered = is_condition_met(
            alert["condition"], alert["target"], current_price, open_price
        )

        if triggered:
            body = build_alert_body(alert, current_price)
            try:
                create_and_push_notification(
                    user_id=alert["user_id"],
                    notification_type="price_alert",
                    title=f"🔔 {alert['symbol']} 價格警報",
                    body=body,
                    data={
                        "symbol": alert["symbol"],
                        "market": alert["market"],
                        "current_price": current_price,
                        "alert_id": alert["id"],
                    },
                )
                logger.info(f"Alert triggered: {alert['symbol']} ({alert['condition']} {alert['target']})")
            except Exception as e:
                logger.error(f"Failed to send alert notification: {e}")
                continue

            repeat = bool(alert.get("repeat"))
            await loop.run_in_executor(
                None, mark_alert_triggered, alert["id"], repeat
            )
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_alert_checker.py -v --no-cov
```

Expected: All PASS

**Step 5: Hook into `api_server.py` lifespan**

In `api_server.py`, add import:

```python
from api.alert_checker import price_alert_check_task
```

(adjust path if you created it as `api/services/alert_checker.py`)

In the `lifespan` function, after the existing `asyncio.create_task(...)` calls:

```python
    # Startup: 啟動價格警報檢查任務
    asyncio.create_task(price_alert_check_task())
    logger.info("✅ Price alert checker task started")
```

**Step 6: Run all tests**

```bash
python -m pytest tests/ -q --no-cov --tb=short
```

Expected: All pass (no regressions)

**Step 7: Commit**

```bash
git add api/alert_checker.py api_server.py tests/test_alert_checker.py
git commit -m "feat(alerts): add background price alert checker task"
```

---

### Task B5: Frontend — alert UI in watchlist

**Files:**
- Modify: `web/js/components.js` or whichever file renders the watchlist
- Modify: `web/js/wallet.js` or `web/js/app.js` (depending on where watchlist UI lives)

**Context:** Find where watchlist symbols are rendered. Look for `get_watchlist` or `/api/watchlist` fetch calls in the JS. Add a 🔔 button per symbol that opens an inline alert creation form.

**Step 1: Locate watchlist rendering code**

```bash
grep -n "watchlist\|/api/watchlist" web/js/*.js | grep -i "render\|fetch\|html\|innerHTML" | head -20
```

**Step 2: Add alert button to each watchlist row**

In the watchlist item render function, add after each symbol display:

```javascript
// After existing symbol HTML, add:
<button class="alert-btn" onclick="openAlertModal('${symbol}', '${market}')"
        title="設定價格警報">🔔</button>
```

**Step 3: Add alert modal HTML**

In the relevant HTML/component template, add:

```html
<!-- Price Alert Modal -->
<div id="alert-modal" class="modal hidden">
  <div class="modal-content">
    <h3>🔔 設定價格警報</h3>
    <p id="alert-symbol-label"></p>
    <select id="alert-condition">
      <option value="above">價格高於</option>
      <option value="below">價格低於</option>
      <option value="change_pct_up">漲幅達</option>
      <option value="change_pct_down">跌幅達</option>
    </select>
    <input type="number" id="alert-target" placeholder="目標值" step="0.01" />
    <label>
      <input type="checkbox" id="alert-repeat" />
      持續通知（觸發後不刪除）
    </label>
    <button onclick="submitAlert()">確認</button>
    <button onclick="closeAlertModal()">取消</button>
  </div>
</div>
```

**Step 4: Add JS functions**

```javascript
let _alertSymbol = '';
let _alertMarket = '';

function openAlertModal(symbol, market) {
  _alertSymbol = symbol;
  _alertMarket = market;
  document.getElementById('alert-symbol-label').textContent = `${symbol} (${market})`;
  document.getElementById('alert-modal').classList.remove('hidden');
}

function closeAlertModal() {
  document.getElementById('alert-modal').classList.add('hidden');
}

async function submitAlert() {
  const condition = document.getElementById('alert-condition').value;
  const target = parseFloat(document.getElementById('alert-target').value);
  const repeat = document.getElementById('alert-repeat').checked;

  if (!target || isNaN(target)) {
    alert('請輸入有效的目標值');
    return;
  }

  try {
    const token = AuthManager.currentUser?.accessToken || localStorage.getItem('access_token');
    const resp = await fetch('/api/alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ symbol: _alertSymbol, market: _alertMarket, condition, target, repeat }),
    });
    if (resp.ok) {
      showToast('✅ 警報已設定');
      closeAlertModal();
      loadUserAlerts();
    } else {
      const err = await resp.json();
      showToast(`❌ ${err.detail || '設定失敗'}`, 'error');
    }
  } catch (e) {
    showToast('❌ 網路錯誤', 'error');
  }
}

async function loadUserAlerts() {
  const token = AuthManager.currentUser?.accessToken || localStorage.getItem('access_token');
  const resp = await fetch('/api/alerts', { headers: { 'Authorization': `Bearer ${token}` } });
  if (!resp.ok) return;
  const data = await resp.json();
  renderAlertList(data.alerts);
}

async function deleteAlert(alertId) {
  const token = AuthManager.currentUser?.accessToken || localStorage.getItem('access_token');
  await fetch(`/api/alerts/${alertId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` },
  });
  loadUserAlerts();
}

function renderAlertList(alerts) {
  const container = document.getElementById('alert-list');
  if (!container) return;
  container.innerHTML = alerts.length === 0
    ? '<p class="text-gray-400 text-sm">尚無警報</p>'
    : alerts.map(a => `
      <div class="alert-item flex justify-between items-center py-1">
        <span>${a.symbol} ${conditionLabel(a.condition)} ${a.target} ${a.repeat ? '🔁' : ''}</span>
        <button onclick="deleteAlert('${a.id}')" class="text-red-400 text-xs">刪除</button>
      </div>
    `).join('');
}

function conditionLabel(c) {
  return { above: '>', below: '<', change_pct_up: '漲幅≥', change_pct_down: '跌幅≥' }[c] || c;
}
```

**Step 5: Test manually**

Start the server: `python api_server.py`
Navigate to watchlist, click 🔔, set an alert, verify it appears in the list.

**Step 6: Commit**

```bash
git add web/js/*.js web/index.html  # adjust paths as needed
git commit -m "feat(alerts): add price alert UI to watchlist (bell button + modal + list)"
```

---

### Task B6: Final integration test and PR

**Step 1: Run full test suite**

```bash
python -m pytest tests/ -q --no-cov
```

Expected: ≥783 passed, 0 failed (same baseline + new tests passing)

**Step 2: Push and create PR**

```bash
git push origin HEAD
# Then open PR on GitHub: feature branch → main
```

**Step 3: PR description should cover:**
- USStockAgent now active (7 tools, priority=8)
- Price alerts: 3 markets, target price + % change, one-shot / persistent
- New endpoints: POST/GET/DELETE `/api/alerts`
- Background checker polling every 60s
- Frontend: 🔔 per watchlist symbol

---

## Summary of Files Changed

| File | Action |
|---|---|
| `core/agents/bootstrap.py` | Add 7 US tool registrations + uncomment USStockAgent |
| `core/tools/us_stock_tools.py` | No change (already complete) |
| `core/database/price_alerts.py` | **New** — CRUD for price_alerts table |
| `core/database/__init__.py` | Export new functions |
| `api/models.py` | Add `CreateAlertRequest` |
| `api/routers/alerts.py` | **New** — POST/GET/DELETE endpoints |
| `api/alert_checker.py` | **New** — background task |
| `api_server.py` | Register alerts router + launch checker task |
| `tests/test_database_price_alerts.py` | **New** |
| `tests/test_router_alerts.py` | **New** |
| `tests/test_alert_checker.py` | **New** |
| `tests/test_multi_market_integration.py` | Re-add `us_stock` assertion |
| `web/js/*.js` + HTML | Alert modal + bell button + list |
