# Commodity & Forex Market Tabs Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Commodity (黃金/石油/天然氣) and Forex (外匯) market tabs following the exact same pattern as the existing usstock tab — backend router, frontend JS module, HTML tab, nav registration.

**Architecture:** Two independent market modules, each following `api/routers/usstock.py` + `web/js/usstock.js` patterns. Data source: yfinance (already installed). Commodity uses futures symbols (GC=F, CL=F, etc.); Forex uses yfinance currency pair symbols (EURUSD=X, TWD=X, etc.). Tab visibility toggle is already handled by `nav-config.js` `enabledItems` mechanism — just add `defaultEnabled: true` to nav items.

**Tech Stack:** Python, FastAPI, yfinance, vanilla JavaScript SPA, Lightweight Charts

---

## Chunk 1: Backend — Commodity & Forex Routers

### Task 1: Create `api/routers/commodity.py`

**Files:**
- Create: `api/routers/commodity.py`

- [ ] **Step 1: Create the router file**

Create `api/routers/commodity.py` with the following content:

```python
"""
Commodity Market Router — 大宗商品市場
Data source: yfinance (futures & ETF symbols)
Follows the same pattern as api/routers/usstock.py
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import asyncio
import yfinance as yf
from datetime import datetime, timedelta

from api.utils import logger

router = APIRouter(prefix="/api/commodity", tags=["Commodity"])

# ── Cache ──────────────────────────────────────────────────────────────────────
_cache: dict = {}

def _get_cache(key: str):
    if key in _cache:
        data, expiry = _cache[key]
        if datetime.now() < expiry:
            return data
    return None

def _set_cache(key: str, data, ttl: int = 300):
    _cache[key] = (data, datetime.now() + timedelta(seconds=ttl))

# ── Default symbols ─────────────────────────────────────────────────────────────
DEFAULT_COMMODITIES = [
    {"symbol": "GC=F",  "name": "黃金 Gold",       "unit": "USD/oz"},
    {"symbol": "SI=F",  "name": "白銀 Silver",      "unit": "USD/oz"},
    {"symbol": "CL=F",  "name": "WTI 原油 Oil",     "unit": "USD/bbl"},
    {"symbol": "BZ=F",  "name": "布蘭特原油 Brent", "unit": "USD/bbl"},
    {"symbol": "NG=F",  "name": "天然氣 Nat.Gas",   "unit": "USD/MMBtu"},
    {"symbol": "HG=F",  "name": "銅 Copper",        "unit": "USD/lb"},
]

# ── Helpers ─────────────────────────────────────────────────────────────────────
def _fetch_commodity_sync(symbol: str, name: str, unit: str) -> dict | None:
    """Fetch a single commodity quote synchronously (run in thread)."""
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        price = round(float(fi.last_price), 4)
        prev  = round(float(fi.previous_close), 4)
        chg   = round(price - prev, 4)
        chg_p = round((chg / prev) * 100, 2) if prev else 0.0
        return {
            "symbol": symbol,
            "name": name,
            "price": price,
            "change": chg,
            "changePercent": chg_p,
            "unit": unit,
        }
    except Exception as e:
        logger.warning(f"[commodity] quote failed {symbol}: {e}")
        return None


def _fetch_technicals_sync(symbol: str) -> dict:
    """Compute RSI(14) and MACD from daily history."""
    try:
        import pandas as pd
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 15:
            return {}
        closes = hist["Close"]

        # RSI(14)
        delta = closes.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, float("nan"))
        rsi   = round(float(100 - (100 / (1 + rs.iloc[-1]))), 1)

        # MACD
        ema12 = closes.ewm(span=12).mean()
        ema26 = closes.ewm(span=26).mean()
        macd_line  = ema12 - ema26
        signal     = macd_line.ewm(span=9).mean()
        histogram  = round(float(macd_line.iloc[-1] - signal.iloc[-1]), 4)

        # 52-week high/low
        hist_52w = ticker.history(period="1y", interval="1d")
        high_52w = round(float(hist_52w["High"].max()), 4) if not hist_52w.empty else None
        low_52w  = round(float(hist_52w["Low"].min()), 4) if not hist_52w.empty else None

        return {
            "rsi": rsi,
            "macd_histogram": histogram,
            "52w_high": high_52w,
            "52w_low": low_52w,
        }
    except Exception as e:
        logger.warning(f"[commodity] technicals failed {symbol}: {e}")
        return {}


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("/market")
async def get_commodity_market(symbols: Optional[str] = None):
    """Current price data for default commodities or custom symbols."""
    if symbols:
        targets = []
        for s in symbols.split(","):
            s = s.strip().upper()
            # Find name from defaults, or use symbol as name
            meta = next((c for c in DEFAULT_COMMODITIES if c["symbol"] == s), None)
            targets.append(meta or {"symbol": s, "name": s, "unit": "USD"})
    else:
        targets = DEFAULT_COMMODITIES

    cache_key = "market:" + ",".join(t["symbol"] for t in targets)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    results = await asyncio.gather(*[
        asyncio.to_thread(_fetch_commodity_sync, t["symbol"], t["name"], t["unit"])
        for t in targets
    ])
    commodities = [r for r in results if r]
    if not commodities:
        raise HTTPException(status_code=404, detail="無法獲取商品數據，請稍後再試")

    data = {"commodities": commodities, "last_updated": datetime.now().isoformat()}
    _set_cache(cache_key, data)
    return data


@router.get("/pulse/{symbol}")
async def get_commodity_pulse(symbol: str):
    """Market pulse analysis for a single commodity."""
    sym = symbol.upper()
    cache_key = f"pulse:{sym}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # Find display name
    meta = next((c for c in DEFAULT_COMMODITIES if c["symbol"] == sym), None)
    display_name = meta["name"] if meta else sym
    unit = meta["unit"] if meta else "USD"

    quote, tech = await asyncio.gather(
        asyncio.to_thread(_fetch_commodity_sync, sym, display_name, unit),
        asyncio.to_thread(_fetch_technicals_sync, sym),
    )

    if not quote:
        raise HTTPException(status_code=404, detail=f"查無商品代號「{sym}」或目前無法獲取數據")

    price     = quote["price"]
    chg_p     = quote["changePercent"]
    trend_str = "走勢偏強" if chg_p > 0 else ("走勢偏弱" if chg_p < 0 else "走勢持平")
    rsi       = tech.get("rsi")
    rsi_str   = ""
    if isinstance(rsi, (int, float)):
        if rsi > 70:
            rsi_str = "，RSI 顯示可能處於超買區間"
        elif rsi < 30:
            rsi_str = "，RSI 顯示可能處於超賣區間"
        else:
            rsi_str = "，RSI 落在中性區間"

    summary = (
        f"{display_name} ({sym}) 目前報價為 {price} {unit}，"
        f"24小時{trend_str} ({chg_p:+.2f}%){rsi_str}。"
        f"此為 CryptoMind AI 根據即時行情自動合成之脈動報告。"
    )

    key_points = [
        f"RSI(14): {tech.get('rsi', 'N/A')}",
        f"MACD Histogram: {tech.get('macd_histogram', 'N/A')}",
        f"52W High: {tech.get('52w_high', 'N/A')} {unit}",
        f"52W Low: {tech.get('52w_low', 'N/A')} {unit}",
        f"24H Change: {chg_p:+.2f}%",
    ]

    result = {
        "symbol": sym,
        "name": display_name,
        "current_price": price,
        "unit": unit,
        "change_24h": chg_p,
        "report": {"summary": summary, "key_points": key_points},
        "technical_indicators": tech,
    }
    _set_cache(cache_key, result, ttl=300)
    return result


@router.get("/klines/{symbol}")
async def get_commodity_klines(symbol: str, interval: str = "1d", limit: int = 200):
    """Historical OHLCV kline data for charting."""
    sym = symbol.upper()
    cache_key = f"klines:{sym}:{interval}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    period_map = {"1d": "1y", "1wk": "2y", "1mo": "5y"}
    period = period_map.get(interval, "1y")

    def fetch():
        ticker = yf.Ticker(sym)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            raise ValueError("無交易資料")
        klines = []
        for idx, row in hist.iterrows():
            try:
                klines.append({
                    "time":   idx.strftime("%Y-%m-%d"),
                    "open":   round(float(row["Open"]),   4),
                    "high":   round(float(row["High"]),   4),
                    "low":    round(float(row["Low"]),    4),
                    "close":  round(float(row["Close"]),  4),
                    "volume": int(row["Volume"]),
                })
            except Exception:
                continue
        return klines[-limit:]

    try:
        klines = await asyncio.to_thread(fetch)
    except Exception:
        raise HTTPException(status_code=404, detail="無法獲取商品歷史數據")

    data = {"symbol": sym, "interval": interval, "data": klines}
    _set_cache(cache_key, data, ttl=300)
    return data
```

- [ ] **Step 2: Verify router imports cleanly**

```bash
.venv/bin/python -c "from api.routers.commodity import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add api/routers/commodity.py
git commit -m "Add: commodity market router (market, pulse, klines endpoints)"
```

---

### Task 2: Create `api/routers/forex.py`

**Files:**
- Create: `api/routers/forex.py`

- [ ] **Step 1: Create the router file**

Create `api/routers/forex.py`:

```python
"""
Forex Market Router — 外匯市場
Data source: yfinance currency pair symbols
Follows the same pattern as api/routers/usstock.py
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import asyncio
import yfinance as yf
from datetime import datetime, timedelta

from api.utils import logger

router = APIRouter(prefix="/api/forex", tags=["Forex"])

# ── Cache ──────────────────────────────────────────────────────────────────────
_cache: dict = {}

def _get_cache(key: str):
    if key in _cache:
        data, expiry = _cache[key]
        if datetime.now() < expiry:
            return data
    return None

def _set_cache(key: str, data, ttl: int = 60):
    """Default TTL 60s for forex (higher frequency updates)."""
    _cache[key] = (data, datetime.now() + timedelta(seconds=ttl))

# ── Default pairs ───────────────────────────────────────────────────────────────
DEFAULT_PAIRS = [
    {"symbol": "TWD=X",    "name": "USD/TWD", "base": "USD", "quote": "TWD"},
    {"symbol": "EURUSD=X", "name": "EUR/USD", "base": "EUR", "quote": "USD"},
    {"symbol": "GBPUSD=X", "name": "GBP/USD", "base": "GBP", "quote": "USD"},
    {"symbol": "JPY=X",    "name": "USD/JPY", "base": "USD", "quote": "JPY"},
    {"symbol": "AUDUSD=X", "name": "AUD/USD", "base": "AUD", "quote": "USD"},
    {"symbol": "CNY=X",    "name": "USD/CNY", "base": "USD", "quote": "CNY"},
]

def _normalize_forex_symbol(pair: str) -> str:
    """Accept common formats: EURUSD, EUR/USD, EUR_USD → EURUSD=X.
    Also accept direct yfinance symbols like TWD=X."""
    s = pair.upper().replace("/", "").replace("_", "").replace("-", "")
    if s.endswith("=X"):
        return s
    # Special handling for USD-quote pairs that yfinance uses without EUR prefix
    DIRECT_MAP = {
        "USDTWD": "TWD=X", "USDJPY": "JPY=X", "USDCNY": "CNY=X",
        "USDKRW": "KRW=X", "USDSGD": "SGD=X",
    }
    if s in DIRECT_MAP:
        return DIRECT_MAP[s]
    return s + "=X"


def _fetch_forex_sync(symbol: str, name: str, base: str, quote: str) -> dict | None:
    """Fetch a single forex pair synchronously."""
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        rate = round(float(fi.last_price), 6)
        prev = round(float(fi.previous_close), 6)
        chg  = round(rate - prev, 6)
        chg_p = round((chg / prev) * 100, 3) if prev else 0.0
        return {
            "symbol": symbol,
            "name": name,
            "rate": rate,
            "change": chg,
            "changePercent": chg_p,
            "base": base,
            "quote": quote,
        }
    except Exception as e:
        logger.warning(f"[forex] quote failed {symbol}: {e}")
        return None


def _fetch_forex_technicals_sync(symbol: str) -> dict:
    """Compute RSI(14) from daily history for a forex pair."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 15:
            return {}
        closes = hist["Close"]
        delta  = closes.diff()
        gain   = delta.clip(lower=0).rolling(14).mean()
        loss   = (-delta.clip(upper=0)).rolling(14).mean()
        rs     = gain / loss.replace(0, float("nan"))
        rsi    = round(float(100 - (100 / (1 + rs.iloc[-1]))), 1)

        hist_52w = ticker.history(period="1y", interval="1d")
        high_52w = round(float(hist_52w["High"].max()), 6) if not hist_52w.empty else None
        low_52w  = round(float(hist_52w["Low"].min()), 6) if not hist_52w.empty else None

        return {"rsi": rsi, "52w_high": high_52w, "52w_low": low_52w}
    except Exception as e:
        logger.warning(f"[forex] technicals failed {symbol}: {e}")
        return {}


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("/market")
async def get_forex_market(pairs: Optional[str] = None):
    """Current rates for default forex pairs or custom pair list."""
    if pairs:
        targets = []
        for p in pairs.split(","):
            sym = _normalize_forex_symbol(p.strip())
            meta = next((d for d in DEFAULT_PAIRS if d["symbol"] == sym), None)
            targets.append(meta or {"symbol": sym, "name": p.strip().upper(), "base": "?", "quote": "?"})
    else:
        targets = DEFAULT_PAIRS

    cache_key = "market:" + ",".join(t["symbol"] for t in targets)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    results = await asyncio.gather(*[
        asyncio.to_thread(_fetch_forex_sync, t["symbol"], t["name"], t["base"], t["quote"])
        for t in targets
    ])
    fx_pairs = [r for r in results if r]
    if not fx_pairs:
        raise HTTPException(status_code=404, detail="無法獲取外匯數據，請稍後再試")

    data = {"pairs": fx_pairs, "last_updated": datetime.now().isoformat()}
    _set_cache(cache_key, data)
    return data


@router.get("/pulse/{pair}")
async def get_forex_pulse(pair: str):
    """Market pulse analysis for a single forex pair."""
    sym = _normalize_forex_symbol(pair)
    cache_key = f"pulse:{sym}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    meta = next((d for d in DEFAULT_PAIRS if d["symbol"] == sym), None)
    display_name = meta["name"] if meta else sym

    quote, tech = await asyncio.gather(
        asyncio.to_thread(_fetch_forex_sync, sym,
                          display_name,
                          meta["base"] if meta else "?",
                          meta["quote"] if meta else "?"),
        asyncio.to_thread(_fetch_forex_technicals_sync, sym),
    )

    if not quote:
        raise HTTPException(status_code=404, detail=f"查無貨幣對「{pair}」或目前無法獲取數據")

    rate  = quote["rate"]
    chg_p = quote["changePercent"]
    trend_str = "走升" if chg_p > 0 else ("走貶" if chg_p < 0 else "持平")
    rsi   = tech.get("rsi")
    rsi_str = ""
    if isinstance(rsi, (int, float)):
        if rsi > 70:
            rsi_str = "，RSI 顯示動能偏強，注意超買風險"
        elif rsi < 30:
            rsi_str = "，RSI 顯示動能偏弱，或有反彈契機"
        else:
            rsi_str = "，RSI 落在中性區間"

    summary = (
        f"{display_name} 目前匯率為 {rate}，"
        f"24小時{trend_str} ({chg_p:+.3f}%){rsi_str}。"
        f"此為 CryptoMind AI 根據即時行情自動合成之脈動報告。"
    )

    key_points = [
        f"RSI(14): {tech.get('rsi', 'N/A')}",
        f"52W High: {tech.get('52w_high', 'N/A')}",
        f"52W Low: {tech.get('52w_low', 'N/A')}",
        f"24H Change: {chg_p:+.3f}%",
    ]

    result = {
        "symbol": sym,
        "name": display_name,
        "rate": rate,
        "change_24h": chg_p,
        "report": {"summary": summary, "key_points": key_points},
        "technical_indicators": tech,
    }
    _set_cache(cache_key, result, ttl=60)
    return result


@router.get("/klines/{pair}")
async def get_forex_klines(pair: str, interval: str = "1d", limit: int = 200):
    """Historical OHLCV kline data for charting."""
    sym = _normalize_forex_symbol(pair)
    cache_key = f"klines:{sym}:{interval}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    period_map = {"1d": "1y", "1wk": "2y", "1mo": "5y"}
    period = period_map.get(interval, "1y")

    def fetch():
        ticker = yf.Ticker(sym)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            raise ValueError("無交易資料")
        klines = []
        for idx, row in hist.iterrows():
            try:
                klines.append({
                    "time":   idx.strftime("%Y-%m-%d"),
                    "open":   round(float(row["Open"]),   6),
                    "high":   round(float(row["High"]),   6),
                    "low":    round(float(row["Low"]),    6),
                    "close":  round(float(row["Close"]),  6),
                    "volume": int(row["Volume"]),
                })
            except Exception:
                continue
        return klines[-limit:]

    try:
        klines = await asyncio.to_thread(fetch)
    except Exception:
        raise HTTPException(status_code=404, detail="無法獲取外匯歷史數據")

    data = {"symbol": sym, "interval": interval, "data": klines}
    _set_cache(cache_key, data, ttl=60)
    return data
```

- [ ] **Step 2: Verify forex router imports cleanly**

```bash
.venv/bin/python -c "from api.routers.forex import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add api/routers/forex.py
git commit -m "Add: forex market router (market, pulse, klines endpoints)"
```

---

### Task 3: Register routers in api_server.py and write tests

**Files:**
- Modify: `api_server.py`
- Create: `tests/test_router_commodity.py`
- Create: `tests/test_router_forex.py`

- [ ] **Step 1: Import and register routers in api_server.py**

In `api_server.py`, find:
```python
from api.routers import system, analysis, market, user, twstock, usstock
```
Change to:
```python
from api.routers import system, analysis, market, user, twstock, usstock, commodity, forex
```

Find the router registration block (around `app.include_router(usstock.router)`) and add:
```python
app.include_router(commodity.router)
app.include_router(forex.router)
```

- [ ] **Step 2: Verify server starts cleanly**

```bash
.venv/bin/python -c "from api_server import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Write router tests**

Create `tests/test_router_commodity.py`:

```python
"""Tests for commodity market router."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api_server import app
    return TestClient(app)


def test_commodity_router_registered(client):
    """Verify /api/commodity routes are accessible (auth not required for market)."""
    # Routes should exist (may return 401 or 200, not 404)
    response = client.get("/api/commodity/market")
    assert response.status_code != 404


def test_commodity_router_prefix():
    """Verify router has correct prefix and tags."""
    from api.routers.commodity import router
    assert router.prefix == "/api/commodity"
    assert "Commodity" in router.tags


def test_normalize_commodity_defaults():
    """Verify default commodity list has expected symbols."""
    from api.routers.commodity import DEFAULT_COMMODITIES
    symbols = [c["symbol"] for c in DEFAULT_COMMODITIES]
    assert "GC=F" in symbols   # Gold
    assert "CL=F" in symbols   # WTI Oil
    assert "NG=F" in symbols   # Natural Gas


def test_commodity_klines_cache_key():
    """Verify klines cache key format."""
    from api.routers.commodity import _get_cache, _set_cache
    _set_cache("klines:GC=F:1d", {"test": True}, ttl=300)
    result = _get_cache("klines:GC=F:1d")
    assert result == {"test": True}


def test_commodity_cache_expiry():
    """Verify expired cache returns None."""
    import time
    from api.routers.commodity import _get_cache, _set_cache
    _set_cache("test_expired", {"data": 1}, ttl=0)
    time.sleep(0.01)
    result = _get_cache("test_expired")
    assert result is None
```

Create `tests/test_router_forex.py`:

```python
"""Tests for forex market router."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api_server import app
    return TestClient(app)


def test_forex_router_registered(client):
    """Verify /api/forex routes exist."""
    response = client.get("/api/forex/market")
    assert response.status_code != 404


def test_forex_router_prefix():
    """Verify router prefix and tags."""
    from api.routers.forex import router
    assert router.prefix == "/api/forex"
    assert "Forex" in router.tags


def test_normalize_forex_symbol():
    """Verify _normalize_forex_symbol handles common input formats."""
    from api.routers.forex import _normalize_forex_symbol
    assert _normalize_forex_symbol("EURUSD") == "EURUSD=X"
    assert _normalize_forex_symbol("EUR/USD") == "EURUSD=X"
    assert _normalize_forex_symbol("EUR_USD") == "EURUSD=X"
    assert _normalize_forex_symbol("USDJPY") == "JPY=X"
    assert _normalize_forex_symbol("USDTWD") == "TWD=X"
    assert _normalize_forex_symbol("TWD=X")  == "TWD=X"


def test_forex_default_pairs():
    """Verify default pair list includes key currencies."""
    from api.routers.forex import DEFAULT_PAIRS
    symbols = [p["symbol"] for p in DEFAULT_PAIRS]
    assert "TWD=X"    in symbols  # USD/TWD
    assert "EURUSD=X" in symbols  # EUR/USD
    assert "JPY=X"    in symbols  # USD/JPY


def test_forex_cache():
    """Verify cache set/get works."""
    from api.routers.forex import _get_cache, _set_cache
    _set_cache("market:test", {"pairs": []}, ttl=60)
    assert _get_cache("market:test") == {"pairs": []}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_router_commodity.py tests/test_router_forex.py -v 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add api_server.py tests/test_router_commodity.py tests/test_router_forex.py
git commit -m "Add: register commodity/forex routers and router tests"
```

---

## Chunk 2: Frontend — Commodity & Forex Tabs

### Task 4: Create `web/js/commodity.js`

**Files:**
- Create: `web/js/commodity.js`

- [ ] **Step 1: Create the JS module**

Create `web/js/commodity.js`:

```javascript
// ============================================================
// Commodity Market Tab — 大宗商品市場
// Follows the same pattern as usstock.js / twstock.js
// ============================================================

window.CommodityTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',

    DEFAULT_SYMBOLS: [
        { symbol: 'GC=F',  name: '黃金',   unit: 'USD/oz'  },
        { symbol: 'CL=F',  name: 'WTI原油', unit: 'USD/bbl' },
        { symbol: 'SI=F',  name: '白銀',   unit: 'USD/oz'  },
        { symbol: 'NG=F',  name: '天然氣', unit: 'USD/MMBtu'},
        { symbol: 'HG=F',  name: '銅',     unit: 'USD/lb'  },
        { symbol: 'BZ=F',  name: '布蘭特原油', unit: 'USD/bbl'},
    ],

    // ── Init ──────────────────────────────────────────────────

    init: function () {
        this.renderMarket();
    },

    // ── Sub-tab switching ─────────────────────────────────────

    switchSubTab: function (subTab, symbol) {
        this.activeSubTab = subTab;
        const marketEl = document.getElementById('commodity-market-section');
        const pulseEl  = document.getElementById('commodity-pulse-section');
        if (!marketEl || !pulseEl) return;

        if (subTab === 'market') {
            marketEl.classList.remove('hidden');
            pulseEl.classList.add('hidden');
            this.destroyChart();
        } else if (subTab === 'pulse' && symbol) {
            this.activeSymbol = symbol;
            marketEl.classList.add('hidden');
            pulseEl.classList.remove('hidden');
            this.renderPulse(symbol);
        }
    },

    backToMarket: function () {
        this.switchSubTab('market');
    },

    // ── Market View ───────────────────────────────────────────

    renderMarket: async function () {
        const listEl = document.getElementById('commodity-list');
        if (!listEl) return;
        listEl.innerHTML = '<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">載入中...</p></div>';
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch('/api/commodity/market');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            listEl.innerHTML = '';
            (data.commodities || []).forEach(item => {
                const isUp   = item.changePercent >= 0;
                const color  = isUp ? 'text-success' : 'text-danger';
                const arrow  = isUp ? '▲' : '▼';
                const card = document.createElement('div');
                card.className = 'bg-surface border border-white/5 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:border-primary/30 transition';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div>
                        <div class="font-bold text-secondary text-sm">${item.name}</div>
                        <div class="text-xs text-textMuted">${item.symbol} · ${item.unit}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-secondary">${item.price.toLocaleString(undefined, {maximumFractionDigits: 4})}</div>
                        <div class="text-xs font-bold ${color}">${arrow} ${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                    </div>`;
                listEl.appendChild(card);
            });

            const updEl = document.getElementById('commodity-last-updated');
            if (updEl && data.last_updated) {
                updEl.textContent = '更新: ' + new Date(data.last_updated).toLocaleTimeString('zh-TW');
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${e.message}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('commodity-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch(`/api/commodity/pulse/${encodeURIComponent(symbol)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const d = await res.json();

            const isUp  = d.change_24h >= 0;
            const color = isUp ? 'text-success' : 'text-danger';

            pulseEl.innerHTML = `
                <div class="space-y-4">
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="text-textMuted text-xs uppercase tracking-wider mb-1">${d.name}</div>
                        <div class="text-3xl font-serif text-secondary font-bold">${d.current_price?.toLocaleString(undefined, {maximumFractionDigits: 4})} <span class="text-sm font-normal text-textMuted">${d.unit}</span></div>
                        <div class="text-sm font-bold ${color} mt-1">${d.change_24h > 0 ? '+' : ''}${d.change_24h?.toFixed(2)}% 24H</div>
                    </div>
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">市場脈動</h4>
                        <p class="text-sm text-secondary leading-relaxed">${d.report?.summary || ''}</p>
                    </div>
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">技術指標</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${(d.report?.key_points || []).map(pt => `
                                <div class="bg-background rounded-xl px-3 py-2 text-xs">
                                    <span class="text-textMuted">${pt.split(':')[0]}:</span>
                                    <span class="text-secondary font-mono ml-1">${pt.split(':').slice(1).join(':').trim()}</span>
                                </div>`).join('')}
                        </div>
                    </div>
                    <div id="commodity-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="CommodityTab.changeInterval('${iv}')" id="commodity-interval-${iv}" class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}</button>`).join('')}
                            </div>
                        </div>
                        <div id="commodity-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            if (window.lucide) lucide.createIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${e.message}</div>`;
        }
    },

    // ── Chart ─────────────────────────────────────────────────

    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('commodity-chart');
        if (!chartEl) return;
        this.destroyChart();

        try {
            const res = await fetch(`/api/commodity/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
            if (!res.ok) return;
            const data = await res.json();
            const klines = data.data || [];
            if (!klines.length) return;

            if (typeof LightweightCharts === 'undefined') return;
            this.chartInstance = LightweightCharts.createChart(chartEl, {
                width: chartEl.clientWidth,
                height: 200,
                layout: { background: { color: 'transparent' }, textColor: '#8899a6' },
                grid: { vertLines: { color: '#1a2332' }, horzLines: { color: '#1a2332' } },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: '#1a2332' },
                timeScale: { borderColor: '#1a2332', timeVisible: true },
            });
            this.chartSeries = this.chartInstance.addCandlestickSeries({
                upColor: '#22c55e', downColor: '#ef4444',
                borderUpColor: '#22c55e', borderDownColor: '#ef4444',
                wickUpColor: '#22c55e', wickDownColor: '#ef4444',
            });
            this.chartSeries.setData(klines.map(k => ({
                time: k.time, open: k.open, high: k.high, low: k.low, close: k.close,
            })));
            this.chartInstance.timeScale().fitContent();
        } catch (e) {
            console.warn('[CommodityTab] chart load failed:', e);
        }
    },

    changeInterval: function (interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`commodity-interval-${iv}`);
            if (!btn) return;
            btn.className = iv === interval
                ? 'text-xs px-2 py-1 rounded-lg bg-primary text-background transition'
                : 'text-xs px-2 py-1 rounded-lg bg-surface text-textMuted hover:bg-surfaceHighlight transition';
        });
        if (this.activeSymbol) this.loadChart(this.activeSymbol, interval);
    },

    destroyChart: function () {
        if (this.chartInstance) {
            try { this.chartInstance.remove(); } catch (_) {}
            this.chartInstance = null;
            this.chartSeries = null;
        }
    },
};
```

- [ ] **Step 2: Commit**

```bash
git add web/js/commodity.js
git commit -m "Add: commodity.js frontend tab module"
```

---

### Task 5: Create `web/js/forex.js`

**Files:**
- Create: `web/js/forex.js`

- [ ] **Step 1: Create the JS module**

Create `web/js/forex.js`:

```javascript
// ============================================================
// Forex Market Tab — 外匯市場
// Follows the same pattern as commodity.js / usstock.js
// ============================================================

window.ForexTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',

    DEFAULT_PAIRS: [
        { symbol: 'TWD=X',    name: 'USD/TWD', desc: '美元 / 台幣' },
        { symbol: 'EURUSD=X', name: 'EUR/USD', desc: '歐元 / 美元' },
        { symbol: 'GBPUSD=X', name: 'GBP/USD', desc: '英鎊 / 美元' },
        { symbol: 'JPY=X',    name: 'USD/JPY', desc: '美元 / 日圓' },
        { symbol: 'AUDUSD=X', name: 'AUD/USD', desc: '澳幣 / 美元' },
        { symbol: 'CNY=X',    name: 'USD/CNY', desc: '美元 / 人民幣'},
    ],

    // ── Init ──────────────────────────────────────────────────

    init: function () {
        this.renderMarket();
    },

    // ── Sub-tab switching ─────────────────────────────────────

    switchSubTab: function (subTab, symbol) {
        this.activeSubTab = subTab;
        const marketEl = document.getElementById('forex-market-section');
        const pulseEl  = document.getElementById('forex-pulse-section');
        if (!marketEl || !pulseEl) return;

        if (subTab === 'market') {
            marketEl.classList.remove('hidden');
            pulseEl.classList.add('hidden');
            this.destroyChart();
        } else if (subTab === 'pulse' && symbol) {
            this.activeSymbol = symbol;
            marketEl.classList.add('hidden');
            pulseEl.classList.remove('hidden');
            this.renderPulse(symbol);
        }
    },

    backToMarket: function () {
        this.switchSubTab('market');
    },

    // ── Market View ───────────────────────────────────────────

    renderMarket: async function () {
        const listEl = document.getElementById('forex-list');
        if (!listEl) return;
        listEl.innerHTML = '<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">載入中...</p></div>';
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch('/api/forex/market');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            listEl.innerHTML = '';
            (data.pairs || []).forEach(item => {
                const isUp   = item.changePercent >= 0;
                const color  = isUp ? 'text-success' : 'text-danger';
                const arrow  = isUp ? '▲' : '▼';
                // Find display info
                const meta   = this.DEFAULT_PAIRS.find(p => p.symbol === item.symbol);
                const desc   = meta?.desc || item.name;

                const card = document.createElement('div');
                card.className = 'bg-surface border border-white/5 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:border-primary/30 transition';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div>
                        <div class="font-bold text-secondary text-sm">${item.name}</div>
                        <div class="text-xs text-textMuted">${desc}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-secondary">${item.rate.toLocaleString(undefined, {maximumFractionDigits: 6})}</div>
                        <div class="text-xs font-bold ${color}">${arrow} ${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(3)}%</div>
                    </div>`;
                listEl.appendChild(card);
            });

            const updEl = document.getElementById('forex-last-updated');
            if (updEl && data.last_updated) {
                updEl.textContent = '更新: ' + new Date(data.last_updated).toLocaleTimeString('zh-TW');
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${e.message}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('forex-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch(`/api/forex/pulse/${encodeURIComponent(symbol)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const d = await res.json();

            const isUp  = d.change_24h >= 0;
            const color = isUp ? 'text-success' : 'text-danger';

            pulseEl.innerHTML = `
                <div class="space-y-4">
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="text-textMuted text-xs uppercase tracking-wider mb-1">${d.name}</div>
                        <div class="text-3xl font-serif text-secondary font-bold">${d.rate?.toLocaleString(undefined, {maximumFractionDigits: 6})}</div>
                        <div class="text-sm font-bold ${color} mt-1">${d.change_24h > 0 ? '+' : ''}${d.change_24h?.toFixed(3)}% 24H</div>
                    </div>
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">市場脈動</h4>
                        <p class="text-sm text-secondary leading-relaxed">${d.report?.summary || ''}</p>
                    </div>
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">技術指標</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${(d.report?.key_points || []).map(pt => `
                                <div class="bg-background rounded-xl px-3 py-2 text-xs">
                                    <span class="text-textMuted">${pt.split(':')[0]}:</span>
                                    <span class="text-secondary font-mono ml-1">${pt.split(':').slice(1).join(':').trim()}</span>
                                </div>`).join('')}
                        </div>
                    </div>
                    <div id="forex-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="ForexTab.changeInterval('${iv}')" id="forex-interval-${iv}" class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}</button>`).join('')}
                            </div>
                        </div>
                        <div id="forex-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            if (window.lucide) lucide.createIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${e.message}</div>`;
        }
    },

    // ── Chart ─────────────────────────────────────────────────

    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('forex-chart');
        if (!chartEl) return;
        this.destroyChart();

        try {
            const res = await fetch(`/api/forex/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
            if (!res.ok) return;
            const data = await res.json();
            const klines = data.data || [];
            if (!klines.length) return;

            if (typeof LightweightCharts === 'undefined') return;
            this.chartInstance = LightweightCharts.createChart(chartEl, {
                width: chartEl.clientWidth,
                height: 200,
                layout: { background: { color: 'transparent' }, textColor: '#8899a6' },
                grid: { vertLines: { color: '#1a2332' }, horzLines: { color: '#1a2332' } },
                rightPriceScale: { borderColor: '#1a2332' },
                timeScale: { borderColor: '#1a2332', timeVisible: true },
            });
            this.chartSeries = this.chartInstance.addLineSeries({
                color: '#8B5CF6', lineWidth: 2,
            });
            this.chartSeries.setData(klines.map(k => ({ time: k.time, value: k.close })));
            this.chartInstance.timeScale().fitContent();
        } catch (e) {
            console.warn('[ForexTab] chart load failed:', e);
        }
    },

    changeInterval: function (interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`forex-interval-${iv}`);
            if (!btn) return;
            btn.className = iv === interval
                ? 'text-xs px-2 py-1 rounded-lg bg-primary text-background transition'
                : 'text-xs px-2 py-1 rounded-lg bg-surface text-textMuted hover:bg-surfaceHighlight transition';
        });
        if (this.activeSymbol) this.loadChart(this.activeSymbol, interval);
    },

    destroyChart: function () {
        if (this.chartInstance) {
            try { this.chartInstance.remove(); } catch (_) {}
            this.chartInstance = null;
            this.chartSeries = null;
        }
    },
};
```

- [ ] **Step 2: Commit**

```bash
git add web/js/forex.js
git commit -m "Add: forex.js frontend tab module"
```

---

### Task 6: Add HTML tabs, script tags, nav, and SPA registration

**Files:**
- Modify: `web/index.html`
- Modify: `web/js/spa.js`
- Modify: `web/js/nav-config.js`
- Modify: `web/js/app.js`

- [ ] **Step 1: Add commodity-tab and forex-tab HTML to index.html**

In `web/index.html`, find the line:
```html
            <!-- Tab: Friends (Global Social Hub) -->
```

Insert the following **before** that line:

```html
            <!-- Tab: Commodity (大宗商品市場) -->
            <div id="commodity-tab"
                class="tab-content hidden h-full overflow-y-auto custom-scrollbar px-4 md:pl-6 md:pr-16 py-6 pb-40">
                <div class="max-w-2xl mx-auto">
                    <!-- Header -->
                    <div id="commodity-market-section">
                        <div class="flex justify-between items-end mb-6 md:pr-14">
                            <h2 class="font-serif text-3xl text-secondary">大宗商品</h2>
                            <div class="flex items-center gap-2">
                                <span id="commodity-last-updated" class="text-xs text-textMuted"></span>
                                <button onclick="CommodityTab.renderMarket()"
                                    class="p-2 bg-surface hover:bg-surfaceHighlight rounded-full text-textMuted transition">
                                    <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>
                        <div id="commodity-list" class="space-y-3">
                            <!-- Injected by commodity.js -->
                        </div>
                    </div>
                    <!-- Pulse Section (hidden by default) -->
                    <div id="commodity-pulse-section" class="hidden">
                        <div class="flex items-center gap-3 mb-6 md:pr-14">
                            <button onclick="CommodityTab.backToMarket()"
                                class="p-2 bg-surface hover:bg-surfaceHighlight rounded-full text-textMuted transition">
                                <i data-lucide="arrow-left" class="w-4 h-4"></i>
                            </button>
                            <h2 class="font-serif text-2xl text-secondary">商品脈動</h2>
                        </div>
                        <div id="commodity-pulse-content">
                            <!-- Injected by commodity.js -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Forex (外匯市場) -->
            <div id="forex-tab"
                class="tab-content hidden h-full overflow-y-auto custom-scrollbar px-4 md:pl-6 md:pr-16 py-6 pb-40">
                <div class="max-w-2xl mx-auto">
                    <!-- Header -->
                    <div id="forex-market-section">
                        <div class="flex justify-between items-end mb-6 md:pr-14">
                            <h2 class="font-serif text-3xl text-secondary">外匯市場</h2>
                            <div class="flex items-center gap-2">
                                <span id="forex-last-updated" class="text-xs text-textMuted"></span>
                                <button onclick="ForexTab.renderMarket()"
                                    class="p-2 bg-surface hover:bg-surfaceHighlight rounded-full text-textMuted transition">
                                    <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>
                        <div id="forex-list" class="space-y-3">
                            <!-- Injected by forex.js -->
                        </div>
                    </div>
                    <!-- Pulse Section (hidden by default) -->
                    <div id="forex-pulse-section" class="hidden">
                        <div class="flex items-center gap-3 mb-6 md:pr-14">
                            <button onclick="ForexTab.backToMarket()"
                                class="p-2 bg-surface hover:bg-surfaceHighlight rounded-full text-textMuted transition">
                                <i data-lucide="arrow-left" class="w-4 h-4"></i>
                            </button>
                            <h2 class="font-serif text-2xl text-secondary">外匯脈動</h2>
                        </div>
                        <div id="forex-pulse-content">
                            <!-- Injected by forex.js -->
                        </div>
                    </div>
                </div>
            </div>

```

- [ ] **Step 2: Add script tags to index.html**

Find the line with `<script defer src="/static/js/pulse.js`:
```html
    <script defer src="/static/js/pulse.js?v=53"></script>
```

Add the two new script tags **after** it:
```html
    <script defer src="/static/js/commodity.js?v=1"></script>
    <script defer src="/static/js/forex.js?v=1"></script>
```

- [ ] **Step 3: Add 'commodity' and 'forex' to spa.js validTabs**

In `web/js/spa.js`, find every array that lists the valid tabs. There are 3 occurrences of this pattern:
```javascript
        'usstock',
        'wallet',
```

Change each one to:
```javascript
        'usstock',
        'commodity',
        'forex',
        'wallet',
```

Also add the tab init handlers in `spa.js`. Find the section with:
```javascript
    if (tabId === 'wallet') {
```

Add before it:
```javascript
    if (tabId === 'commodity' && typeof CommodityTab !== 'undefined') CommodityTab.init();
    if (tabId === 'forex' && typeof ForexTab !== 'undefined') ForexTab.init();
```

- [ ] **Step 4: Add commodity and forex to nav-config.js**

In `web/js/nav-config.js`, find:
```javascript
    { id: 'friends',
```

Insert before it:
```javascript
    { id: 'commodity', icon: 'bar-chart-2', label: 'Commodity', i18nKey: 'nav.commodity', defaultEnabled: true },
    { id: 'forex',     icon: 'arrow-left-right', label: 'Forex', i18nKey: 'nav.forex', defaultEnabled: true },
```

- [ ] **Step 5: Verify no JS errors (check spa.js validTabs)**

```bash
grep -n "'commodity'\|'forex'" web/js/spa.js
```

Expected: 3 occurrences of 'commodity' and 3 of 'forex' (one per validTabs array)

- [ ] **Step 6: Verify server loads**

```bash
.venv/bin/python -c "from api_server import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/js/spa.js web/js/nav-config.js
git commit -m "Add: commodity and forex tabs to HTML, SPA router, and nav config"
```

---

## Final Verification

- [ ] **Check no stale references**

```bash
grep -r "commodity\|forex" api_server.py | grep "import\|include_router"
grep -n "commodity\|forex" web/js/nav-config.js
```

Expected: routers registered, nav items present

- [ ] **Run full backend test suite**

```bash
.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/pw_test \
  --ignore=tests/test_agent_scenarios.py \
  --ignore=tests/test_pi_routing_fix.py \
  --ignore=tests/test_router_governance_routes.py \
  --ignore=tests/test_router_market.py \
  --ignore=tests/test_router_market_extended.py \
  --deselect=tests/test_bootstrap_runtime.py::test_language_aware_llm_ainvoke_injects_system_message \
  2>&1 | tail -5
```

Expected: all pass, no new failures

- [ ] **Final commit if needed**

```bash
git add -u
git commit -m "Cleanup: final commodity/forex integration cleanup"
```
