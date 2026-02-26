# Design: USStockAgent Activation + Price Alert System

**Date**: 2026-02-26
**Status**: Approved
**Branch**: feature/us-stock-agent-and-alerts

---

## Overview

Two immediately actionable features that extend the existing multi-market agent infrastructure:

1. **USStockAgent Activation** — All 7 US stock tools are implemented; this activates them in the agent registry and classify routing.
2. **Price Alert System** — Three-market (Crypto / TW Stock / US Stock) price alert with target price and percentage change conditions, backed by the existing notification and WebSocket infrastructure.

---

## Feature 1: USStockAgent Activation

### Problem

`us_stock_agent.py` and all 7 US stock tools (`us_data_provider.py`, `us_stock_tools.py`) are fully implemented but commented out in `bootstrap.py`. Users asking about AAPL/TSLA/NVDA fall through to the Chat Agent.

### Architecture Changes

#### `core/agents/bootstrap.py`

Add a `── Register US Stock Tools ──` block with 7 `ToolMetadata` registrations:

| Tool name | Function | Allowed agents |
|---|---|---|
| `us_stock_price` | `us_stock_price` | `us_stock`, `chat` |
| `us_technical_analysis` | `us_technical_analysis` | `us_stock` |
| `us_fundamentals` | `us_fundamentals` | `us_stock` |
| `us_earnings` | `us_earnings` | `us_stock` |
| `us_news` | `us_news` | `us_stock` |
| `us_institutional_holders` | `us_institutional_holders` | `us_stock` |
| `us_insider_transactions` | `us_insider_transactions` | `us_stock` |

Uncomment and update `USStockAgent` registration:

```python
us = USStockAgent(lang_llm, tool_registry)
agent_registry.register(us, AgentMetadata(
    name="us_stock",
    display_name="US Stock Agent",
    description="美股全方位分析 — 即時價格（15分鐘延遲）、技術指標（RSI/MACD/MA/BB）、"
                "基本面（P/E/EPS/ROE）、財報數據、機構持倉、內部人交易、最新新聞。"
                "適合 AAPL/TSLA/NVDA/TSM/MSFT/AMZN 等 NYSE/NASDAQ 股票查詢，"
                "接受股票代號或公司名稱。",
    capabilities=[
        "美股", "US stock", "NYSE", "NASDAQ",
        "AAPL", "TSLA", "NVDA", "TSM", "MSFT", "AMZN", "GOOGL", "META",
        "標普500", "道瓊", "那斯達克", "S&P500",
    ],
    allowed_tools=[
        "us_stock_price", "us_technical_analysis", "us_fundamentals",
        "us_earnings", "us_news", "us_institutional_holders",
        "us_insider_transactions", "get_current_time_taipei",
    ],
    priority=8,
))
```

Also add `"us_stock"` to `get_current_time_taipei`'s `allowed_agents`.

#### Classify Routing

The Manager's `_classify_node` uses `agent_registry.list_all()` to build the routing context for the LLM. Adding the agent with the above `capabilities` and `description` is sufficient — no prompt changes needed. The LLM will match "AAPL 分析" → `us_stock` automatically.

### Data Source

Yahoo Finance via `yfinance` (already in `requirements.txt`). 15-minute delayed data for price; fundamentals/earnings are end-of-day.

### Error Handling

`us_data_provider.py` already has:
- Try/except around all yfinance calls
- In-memory cache with TTL (5 min for price, 30 min for fundamentals)
- Fallback error messages in Chinese

---

## Feature 2: Price Alert System

### Problem

Users cannot set automated price notifications. Watchlist stores symbols but has no alert logic.

### Architecture

```
User sets alert
     │
     ▼
POST /api/alerts ──► price_alerts table
                          │
                    price_alert_check_task() [every 60s]
                          │
                    fetch current price (by market)
                          │
                    condition met? ──► create_and_push_notification()
                                            │
                                      WebSocket /ws/notifications
                                            │
                                      Frontend notification bell 🔔
```

### Database: `core/database/price_alerts.py`

```sql
CREATE TABLE IF NOT EXISTS price_alerts (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL CHECK (market IN ('crypto', 'tw_stock', 'us_stock')),
    condition   TEXT NOT NULL CHECK (condition IN ('above', 'below', 'change_pct_up', 'change_pct_down')),
    target      REAL NOT NULL,
    repeat      INTEGER NOT NULL DEFAULT 0,  -- 0=one-shot, 1=persistent
    triggered   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX idx_price_alerts_user ON price_alerts(user_id);
CREATE INDEX idx_price_alerts_active ON price_alerts(triggered) WHERE triggered = 0;
```

DB functions:
- `create_alert(user_id, symbol, market, condition, target, repeat) → dict`
- `get_user_alerts(user_id) → list`
- `delete_alert(alert_id, user_id) → bool`
- `get_active_alerts() → list`  (for background task)
- `mark_alert_triggered(alert_id)` (deletes one-shot, sets triggered=1 for persistent)

### API: `api/routers/alerts.py`

```
POST   /api/alerts              Create alert (auth required)
GET    /api/alerts              List my alerts (auth required)
DELETE /api/alerts/{id}         Delete alert (auth required, ownership check)
```

Request model:
```python
class CreateAlertRequest(BaseModel):
    symbol: str
    market: Literal["crypto", "tw_stock", "us_stock"]
    condition: Literal["above", "below", "change_pct_up", "change_pct_down"]
    target: float
    repeat: bool = False
```

### Background Task: `api/services/alert_checker.py`

```python
async def price_alert_check_task():
    while True:
        await asyncio.sleep(60)  # check every 60 seconds
        alerts = get_active_alerts()

        for alert in alerts:
            price = await fetch_price(alert["symbol"], alert["market"])
            if price and is_triggered(alert, price):
                create_and_push_notification(
                    user_id=alert["user_id"],
                    type="price_alert",
                    title=f"🔔 {alert['symbol']} 價格警報",
                    body=build_alert_body(alert, price),
                )
                mark_alert_triggered(alert["id"])
```

Price fetching per market:
- **Crypto**: `get_crypto_price(symbol)` (existing tool, real-time)
- **TW Stock**: `tw_stock_price(ticker)` (existing tool, ~20min delay)
- **US Stock**: `us_stock_price(symbol)` (yfinance, 15min delay)

Condition logic:
- `above`: `current_price >= target`
- `below`: `current_price <= target`
- `change_pct_up`: `(current - open) / open * 100 >= target`
- `change_pct_down`: `(open - current) / open * 100 >= target`

### Frontend: watchlist UI extension

In the existing watchlist section, add a 🔔 icon per symbol. Clicking opens an inline form:
- Condition dropdown: 高於 / 低於 / 漲幅達 / 跌幅達
- Target value input
- Repeat toggle
- Submit → `POST /api/alerts`

Alert list shown below watchlist with delete button.

### Error Handling

- Max 20 alerts per user (enforced at API level)
- Market hours awareness: TW/US stock alerts skip polling outside market hours (9:00–13:30 TW, 9:30–16:00 EST)
- yfinance / TWSE failures → log and skip, retry next cycle
- Notification delivery failure → log, alert remains active

---

## Implementation Order

1. **USStockAgent** (bootstrap.py only, ~30 lines) — highest ROI, lowest risk
2. **DB + functions** (`core/database/price_alerts.py`)
3. **API router** (`api/routers/alerts.py` + register in `api_server.py`)
4. **Background task** (`api/services/alert_checker.py` + hook into `lifespan`)
5. **Frontend** (watchlist UI bell + alert list)

---

## Testing

- USStockAgent: query "分析 AAPL", "TSLA 技術分析", "NVDA 基本面" — verify routes to `us_stock`
- Alert create/list/delete API unit tests
- Background task: mock price fetch, verify notification created when condition met
- E2E: set alert → wait 60s (or mock sleep) → verify notification appears in bell
