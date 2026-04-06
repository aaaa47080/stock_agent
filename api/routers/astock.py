"""
A-Share Market Router — 陸股（滬深 A 股）
Data source: Yahoo Finance v8 chart API
Symbols: 600xxx.SS (Shanghai), 000xxx/300xxx.SZ (Shenzhen)
Follows the same pattern as api/routers/hkstock.py
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException

from api.deps import get_optional_current_user
from api.user_llm import resolve_user_llm_credentials
from api.utils import logger

router = APIRouter(prefix="/api/astock", tags=["A Stock"])

MARKET_DATA_UNAVAILABLE_MESSAGE = "目前無法取得 A 股行情，已回傳空資料供前端安全降級"

# ── Cache ──────────────────────────────────────────────────────────────────────
_cache: dict = {}


def _get_cache(key: str):
    if key in _cache:
        data, expiry = _cache[key]
        if datetime.now(timezone.utc) < expiry:
            return data
    return None


def _set_cache(key: str, data, ttl: int = 300):
    _cache[key] = (data, datetime.now(timezone.utc) + timedelta(seconds=ttl))


_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Curated A-share name table ─────────────────────────────────────────────────
_A_STOCK_NAMES: dict[str, str] = {
    # 消費 / 白酒
    "600519.SS": "貴州茅台",
    "000858.SZ": "五糧液",
    "600036.SS": "招商銀行",
    # 金融 / 銀行
    "601318.SS": "中國平安",
    "600000.SS": "浦發銀行",
    "601398.SS": "工商銀行",
    "601288.SS": "農業銀行",
    "600016.SS": "民生銀行",
    # 科技 / 半導體
    "688981.SS": "中芯國際",
    "002594.SZ": "比亞迪",
    "300750.SZ": "寧德時代",
    "601012.SS": "隆基綠能",
    "600276.SS": "恒瑞醫藥",
    # 互聯網 / 科技
    "600測.SS": "科大訊飛",  # placeholder removed below
    "002475.SZ": "立訊精密",
    "300059.SZ": "東方財富",
    # 能源
    "600028.SS": "中國石化",
    "601857.SS": "中國石油",
    "600941.SS": "中國移動",
    # 地產
    "000002.SZ": "萬科A",
    "600048.SS": "保利發展",
    # 食品 / 消費
    "600887.SS": "伊利股份",
    "603288.SS": "海天味業",
    # 醫療
    "300015.SZ": "愛爾眼科",
    "600196.SS": "復星醫藥",
    # ETF
    "510300.SS": "滬深300ETF",
    "510500.SS": "中證500ETF",
    "159915.SZ": "創業板ETF",
}

# 移除測試用佔位符
_A_STOCK_NAMES.pop("600測.SS", None)

DEFAULT_A_SYMBOLS = [
    "600519.SS", "000858.SZ", "600036.SS", "601318.SS",
    "002594.SZ", "300750.SZ", "600028.SS", "510300.SS",
]


# ── Yahoo Finance v8 chart API ─────────────────────────────────────────────────

async def _fetch_quote_v8(client: httpx.AsyncClient, symbol: str) -> dict | None:
    """Fetch a single A-share quote via Yahoo v8 chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        resp = await client.get(url, params={"range": "1d", "interval": "1d"})
        resp.raise_for_status()
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        price = round(float(meta["regularMarketPrice"]), 2)
        prev  = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
        change = round(price - prev, 2)
        change_pct = round((change / prev) * 100, 2) if prev else 0.0
        display_name = _A_STOCK_NAMES.get(symbol) or meta.get("shortName") or symbol
        return {
            "symbol": symbol,
            "name": display_name,
            "price": price,
            "change": change,
            "changePercent": change_pct,
            "currency": meta.get("currency", "CNY"),
        }
    except Exception as e:
        logger.warning(f"[astock] quote failed {symbol}: {e}")
        return None


async def _fetch_quotes_batch(symbols: list[str]) -> list[dict]:
    """Fetch quotes for multiple A-share symbols concurrently."""
    async with httpx.AsyncClient(timeout=10, headers=_YF_HEADERS) as client:
        results = await asyncio.gather(*[_fetch_quote_v8(client, s) for s in symbols])
    return [r for r in results if r]


async def _fetch_technicals(symbol: str) -> dict:
    """Fetch RSI(14) and 52w high/low via Yahoo v8 chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
    try:
        async with httpx.AsyncClient(timeout=15, headers=_YF_HEADERS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"[astock] technicals fetch failed {symbol}: {e}")
        return {}

    try:
        result = data["chart"]["result"][0]
        closes_raw = result["indicators"]["quote"][0].get("close", [])
        closes = [c for c in closes_raw if c is not None]
        if len(closes) < 15:
            return {}

        # RSI(14)
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains  = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else 0
        avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else 0
        rsi = round(100 - (100 / (1 + avg_gain / avg_loss)), 1) if avg_loss else 100.0

        highs = [h for h in result["indicators"]["quote"][0].get("high", []) if h is not None]
        lows  = [l for l in result["indicators"]["quote"][0].get("low",  []) if l is not None]
        return {
            "rsi": rsi,
            "52w_high": round(max(highs), 2) if highs else None,
            "52w_low":  round(min(lows),  2) if lows  else None,
        }
    except Exception as e:
        logger.warning(f"[astock] technicals parse failed {symbol}: {e}")
        return {}


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("/market")
async def get_a_market(symbols: Optional[str] = None):
    """Current price data for A-share stocks."""
    targets = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols else DEFAULT_A_SYMBOLS
    )
    cache_key = "market:" + ",".join(targets)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    quotes = await _fetch_quotes_batch(targets)
    data = {
        "stocks": quotes,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    if len(quotes) != len(targets):
        data["partial_failure"] = True
        data["warning"] = MARKET_DATA_UNAVAILABLE_MESSAGE

    _set_cache(cache_key, data)
    return data


@router.get("/pulse/{symbol}")
async def get_a_pulse(
    symbol: str,
    deep_analysis: bool = False,
    x_user_llm_provider: Optional[str] = Header(None),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    """Market pulse analysis for a single A-share stock."""
    sym = symbol.upper()
    # Normalise: accept 600519 → 600519.SS, 000858 → 000858.SZ
    if "." not in sym:
        if sym.startswith("6") or sym.startswith("9"):
            sym = sym + ".SS"
        else:
            sym = sym + ".SZ"

    cache_key = f"pulse:{sym}"
    if not deep_analysis:
        cached = _get_cache(cache_key)
        if cached:
            return cached

    quotes, tech = await asyncio.gather(
        _fetch_quotes_batch([sym]),
        _fetch_technicals(sym),
    )
    if not quotes:
        raise HTTPException(status_code=404, detail=f"查無 A 股代號「{sym}」或目前無法獲取數據")

    q = quotes[0]
    price = q["price"]
    chg_p = q["changePercent"]
    display_name = q["name"]
    currency = q.get("currency", "CNY")

    trend_str = "走升" if chg_p > 0 else ("走跌" if chg_p < 0 else "持平")
    rsi = tech.get("rsi")
    rsi_str = ""
    if isinstance(rsi, (int, float)):
        if rsi > 70:
            rsi_str = "，RSI 顯示可能處於超買區間"
        elif rsi < 30:
            rsi_str = "，RSI 顯示可能處於超賣區間"
        else:
            rsi_str = "，RSI 落在中性區間"

    summary = (
        f"{display_name} ({sym}) 目前報價為 {price} {currency}，"
        f"24小時{trend_str} ({chg_p:+.2f}%){rsi_str}。"
        f"此為 CryptoMind AI 根據即時行情自動合成之脈動報告。"
    )
    key_points = [
        f"RSI(14): {tech.get('rsi', 'N/A')}",
        f"52W High: {tech.get('52w_high', 'N/A')} {currency}",
        f"52W Low: {tech.get('52w_low', 'N/A')} {currency}",
        f"24H Change: {chg_p:+.2f}%",
    ]

    source_mode = "on_demand"
    credentials = None
    if deep_analysis:
        credentials = await resolve_user_llm_credentials(current_user, x_user_llm_provider)
    if credentials:
        from api.routers.deep_analysis_helper import deep_analyze_generic
        context = (
            f"A 股: {display_name} ({sym})\n"
            f"現價: {price} {currency}\n"
            f"24H 漲跌幅: {chg_p:+.2f}%\n"
            f"RSI(14): {tech.get('rsi', 'N/A')}\n"
            f"52W High: {tech.get('52w_high', 'N/A')} {currency}\n"
            f"52W Low: {tech.get('52w_low', 'N/A')} {currency}"
        )
        ai_text = await deep_analyze_generic(sym, context, credentials["api_key"], credentials["provider"])
        if ai_text:
            summary = ai_text
            source_mode = "deep_analysis"

    result = {
        "symbol": sym,
        "name": display_name,
        "current_price": price,
        "currency": currency,
        "change_24h": chg_p,
        "source_mode": source_mode,
        "report": {"summary": summary, "key_points": key_points},
        "technical_indicators": tech,
    }
    if not deep_analysis:
        _set_cache(cache_key, result, ttl=300)
    return result


@router.get("/klines/{symbol}")
async def get_a_klines(symbol: str, interval: str = "1d", limit: int = 200):
    """Historical OHLCV kline data via Yahoo Finance chart API."""
    sym = symbol.upper()
    if "." not in sym:
        sym = sym + ".SS" if sym.startswith("6") or sym.startswith("9") else sym + ".SZ"

    cache_key = f"klines:{sym}:{interval}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    range_map = {"1d": "1y", "1wk": "2y", "1mo": "5y"}
    yf_range = range_map.get(interval, "1y")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    params = {"range": yf_range, "interval": interval, "includePrePost": "false"}

    try:
        async with httpx.AsyncClient(timeout=15, headers=_YF_HEADERS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"無法獲取 A 股歷史數據: {e}")

    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        opens   = ohlcv.get("open", [])
        highs   = ohlcv.get("high", [])
        lows    = ohlcv.get("low", [])
        closes  = ohlcv.get("close", [])
        volumes = ohlcv.get("volume", [])

        klines = []
        for i, ts in enumerate(timestamps):
            try:
                o, h, l, c = opens[i], highs[i], lows[i], closes[i]
                if None in (o, h, l, c):
                    continue
                klines.append({
                    "time":   datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "open":   round(float(o), 2),
                    "high":   round(float(h), 2),
                    "low":    round(float(l), 2),
                    "close":  round(float(c), 2),
                    "volume": int(volumes[i] or 0),
                })
            except Exception:
                continue
        klines = klines[-limit:]
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"解析 A 股歷史數據失敗: {e}")

    result_data = {"symbol": sym, "interval": interval, "data": klines}
    _set_cache(cache_key, result_data, ttl=300)
    return result_data
