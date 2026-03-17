"""
Commodity Market Router — 大宗商品市場
Data source: yfinance (futures & ETF symbols)
Follows the same pattern as api/routers/usstock.py
"""
from fastapi import APIRouter, HTTPException, Header
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
async def get_commodity_pulse(
    symbol: str,
    deep_analysis: bool = False,
    x_user_llm_key: Optional[str] = Header(None),
    x_user_llm_provider: Optional[str] = Header(None),
):
    """Market pulse analysis for a single commodity."""
    sym = symbol.upper()
    cache_key = f"pulse:{sym}"
    if not deep_analysis:
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

    source_mode = "on_demand"
    if deep_analysis and x_user_llm_key and x_user_llm_provider:
        from api.routers.deep_analysis_helper import deep_analyze_generic
        context = (
            f"商品: {display_name} ({sym})\n"
            f"現價: {price} {unit}\n"
            f"24H 漲跌幅: {chg_p:+.2f}%\n"
            f"RSI(14): {tech.get('rsi', 'N/A')}\n"
            f"MACD Histogram: {tech.get('macd_histogram', 'N/A')}\n"
            f"52W High: {tech.get('52w_high', 'N/A')} {unit}\n"
            f"52W Low: {tech.get('52w_low', 'N/A')} {unit}"
        )
        ai_text = await deep_analyze_generic(sym, context, x_user_llm_key, x_user_llm_provider)
        if ai_text:
            summary = ai_text
            source_mode = "deep_analysis"

    result = {
        "symbol": sym,
        "name": display_name,
        "current_price": price,
        "unit": unit,
        "change_24h": chg_p,
        "source_mode": source_mode,
        "report": {"summary": summary, "key_points": key_points},
        "technical_indicators": tech,
    }
    if not deep_analysis:
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
