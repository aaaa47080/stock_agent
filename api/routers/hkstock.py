"""
HK Stock Market Router — 港股市場
Data source: Yahoo Finance batch quote API (query1.finance.yahoo.com)
Directly calls Yahoo's underlying API for batch efficiency (vs yfinance one-by-one).
Follows the same pattern as api/routers/usstock.py
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException

from api.deps import get_optional_current_user
from api.user_llm import resolve_user_llm_credentials
from api.utils import logger

router = APIRouter(prefix="/api/hkstock", tags=["HK Stock"])

MARKET_DATA_UNAVAILABLE_MESSAGE = "目前無法取得港股行情，已回傳空資料供前端安全降級"

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


# ── Yahoo Finance batch API headers (mimic browser to reduce blocking risk) ───
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Curated HK stock name table ────────────────────────────────────────────────
_HK_STOCK_NAMES: dict[str, dict] = {
    # 科技 / 互聯網
    "0700.HK": {"zh": "騰訊", "en": "Tencent"},
    "9988.HK": {"zh": "阿里巴巴", "en": "Alibaba"},
    "3690.HK": {"zh": "美團", "en": "Meituan"},
    "9618.HK": {"zh": "京東", "en": "JD.com"},
    "0992.HK": {"zh": "聯想", "en": "Lenovo"},
    "0241.HK": {"zh": "阿里健康", "en": "Alibaba Health"},
    # 金融
    "0005.HK": {"zh": "匯豐", "en": "HSBC"},
    "0939.HK": {"zh": "建設銀行", "en": "CCB"},
    "1398.HK": {"zh": "工商銀行", "en": "ICBC"},
    "3988.HK": {"zh": "中國銀行", "en": "Bank of China"},
    "0011.HK": {"zh": "恒生銀行", "en": "Hang Seng Bank"},
    "2318.HK": {"zh": "中國平安", "en": "Ping An"},
    # 地產 / 基建
    "0016.HK": {"zh": "新鴻基地產", "en": "Sun Hung Kai"},
    "0001.HK": {"zh": "長和", "en": "CK Hutchison"},
    "0002.HK": {"zh": "中電控股", "en": "CLP Holdings"},
    "0003.HK": {"zh": "香港中華煤氣", "en": "Hong Kong Gas"},
    # 消費 / 零售
    "0291.HK": {"zh": "華潤啤酒", "en": "CR Beer"},
    "0027.HK": {"zh": "銀河娛樂", "en": "Galaxy Entertainment"},
    "1928.HK": {"zh": "金沙中國", "en": "Sands China"},
    # 交易所 / 指數相關
    "0388.HK": {"zh": "港交所", "en": "HKEX"},
    # 醫療 / 生物
    "1177.HK": {"zh": "中國生物製藥", "en": "Sino Biopharm"},
    "6160.HK": {"zh": "百濟神州", "en": "BeiGene"},
    # 汽車 / 新能源
    "0175.HK": {"zh": "吉利汽車", "en": "Geely"},
    "2015.HK": {"zh": "理想汽車", "en": "Li Auto"},
    "9866.HK": {"zh": "蔚來", "en": "NIO"},
    # ETF
    "2800.HK": {"zh": "盈富基金", "en": "Tracker Fund (HSI ETF)"},
    "3032.HK": {"zh": "恒生科技ETF", "en": "HS Tech ETF"},
}

DEFAULT_HK_SYMBOLS = [
    "0700.HK", "9988.HK", "0005.HK", "0388.HK",
    "3690.HK", "2318.HK", "0939.HK", "2800.HK",
]

# ── Yahoo Finance batch quote API ──────────────────────────────────────────────

async def _fetch_quote_v8(client: httpx.AsyncClient, symbol: str) -> dict | None:
    """Fetch a single HK stock quote via Yahoo v8 chart API (meta fields only)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        resp = await client.get(url, params={"range": "1d", "interval": "1d"})
        resp.raise_for_status()
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        price = round(float(meta["regularMarketPrice"]), 3)
        prev  = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
        change = round(price - prev, 3)
        change_pct = round((change / prev) * 100, 2) if prev else 0.0
        names = _HK_STOCK_NAMES.get(symbol)
        if names:
            name_zh = names["zh"]
            name_en = names["en"]
        else:
            fallback = meta.get("shortName") or symbol
            name_zh = fallback
            name_en = fallback
        return {
            "symbol": symbol,
            "name": name_zh,       # backward compat
            "name_zh": name_zh,
            "name_en": name_en,
            "price": price,
            "change": change,
            "changePercent": change_pct,
            "currency": meta.get("currency", "HKD"),
        }
    except Exception as e:
        logger.warning(f"[hkstock] quote failed {symbol}: {e}")
        return None


async def _fetch_quotes_yahoo_batch(symbols: list[str]) -> list[dict]:
    """Fetch quotes for multiple HK symbols concurrently via Yahoo v8 chart API."""
    async with httpx.AsyncClient(timeout=10, headers=_YF_HEADERS) as client:
        results = await asyncio.gather(*[_fetch_quote_v8(client, s) for s in symbols])
    return [r for r in results if r]


async def _fetch_technicals_yahoo(symbol: str) -> dict:
    """Fetch RSI(14) and 52w high/low via Yahoo chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
    try:
        async with httpx.AsyncClient(timeout=15, headers=_YF_HEADERS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"[hkstock] technicals fetch failed {symbol}: {e}")
        return {}

    try:
        result = data["chart"]["result"][0]
        closes_raw = result["indicators"]["quote"][0].get("close", [])
        closes = [c for c in closes_raw if c is not None]
        if len(closes) < 15:
            return {}

        # RSI(14)
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        def avg(lst, n): return sum(lst[-n:]) / n if len(lst) >= n else 0
        avg_gain = avg(gains, 14)
        avg_loss = avg(losses, 14)
        rsi = round(100 - (100 / (1 + avg_gain / avg_loss)), 1) if avg_loss else 100.0

        # 52w high / low
        highs_raw = result["indicators"]["quote"][0].get("high", [])
        lows_raw  = result["indicators"]["quote"][0].get("low", [])
        highs = [h for h in highs_raw if h is not None]
        lows  = [l for l in lows_raw  if l is not None]
        high_52w = round(max(highs), 3) if highs else None
        low_52w  = round(min(lows),  3) if lows  else None

        return {"rsi": rsi, "52w_high": high_52w, "52w_low": low_52w}
    except Exception as e:
        logger.warning(f"[hkstock] technicals parse failed {symbol}: {e}")
        return {}


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.get("/market")
async def get_hk_market(symbols: Optional[str] = None):
    """Current price data for HK stocks."""
    targets = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols else DEFAULT_HK_SYMBOLS
    )
    cache_key = "market:" + ",".join(targets)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    quotes = await _fetch_quotes_yahoo_batch(targets)
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
async def get_hk_pulse(
    symbol: str,
    deep_analysis: bool = False,
    x_user_llm_provider: Optional[str] = Header(None),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    """Market pulse analysis for a single HK stock."""
    sym = symbol.upper()
    # Normalise: accept 700 → 0700.HK, 700.HK → 0700.HK
    if not sym.endswith(".HK"):
        sym = sym.zfill(4) + ".HK"

    cache_key = f"pulse:{sym}"
    if not deep_analysis:
        cached = _get_cache(cache_key)
        if cached:
            return cached

    quotes, tech = await asyncio.gather(
        _fetch_quotes_yahoo_batch([sym]),
        _fetch_technicals_yahoo(sym),
    )
    if not quotes:
        raise HTTPException(status_code=404, detail=f"查無港股代號「{sym}」或目前無法獲取數據")

    q = quotes[0]
    price = q["price"]
    chg_p = q["changePercent"]
    display_name = q["name"]
    currency = q.get("currency", "HKD")

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
            f"港股: {display_name} ({sym})\n"
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
async def get_hk_klines(symbol: str, interval: str = "1d", limit: int = 200):
    """Historical OHLCV kline data via Yahoo Finance chart API."""
    sym = symbol.upper()
    if not sym.endswith(".HK"):
        sym = sym.zfill(4) + ".HK"

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
        raise HTTPException(status_code=404, detail=f"無法獲取港股歷史數據: {e}")

    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        opens  = ohlcv.get("open", [])
        highs  = ohlcv.get("high", [])
        lows   = ohlcv.get("low", [])
        closes = ohlcv.get("close", [])
        volumes = ohlcv.get("volume", [])

        klines = []
        for i, ts in enumerate(timestamps):
            try:
                o, h, l, c = opens[i], highs[i], lows[i], closes[i]
                if None in (o, h, l, c):
                    continue
                klines.append({
                    "time": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "open":   round(float(o), 3),
                    "high":   round(float(h), 3),
                    "low":    round(float(l), 3),
                    "close":  round(float(c), 3),
                    "volume": int(volumes[i] or 0),
                })
            except Exception:
                continue
        klines = klines[-limit:]
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"解析港股歷史數據失敗: {e}")

    result_data = {"symbol": sym, "interval": interval, "data": klines}
    _set_cache(cache_key, result_data, ttl=300)
    return result_data


@router.get("/search")
async def search_hk_stocks(q: str):
    """Search HK stocks via Yahoo Finance search API."""
    if not q or len(q.strip()) < 1:
        return {"results": []}
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {
            "q": q,
            "lang": "en-US",
            "region": "US",
            "quotesCount": 10,
            "newsCount": 0,
            "enableFuzzyQuery": False,
            "quotesQueryId": "tss_match_phrase_query",
        }
        async with httpx.AsyncClient(timeout=8, headers=_YF_HEADERS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        quotes = data.get("quotes", [])
        results = [
            {"symbol": q["symbol"], "name": q.get("shortname") or q.get("longname") or q["symbol"]}
            for q in quotes
            if q.get("symbol", "").endswith(".HK") and q.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")
        ]
        return {"results": results}
    except Exception as e:
        logger.warning(f"[hkstock] search failed: {e}")
        return {"results": []}
