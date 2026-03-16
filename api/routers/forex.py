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
