from fastapi import APIRouter, HTTPException
from typing import Optional
import asyncio
import yfinance as yf
from datetime import datetime, timedelta

from api.utils import logger
from core.tools.us_data_provider import get_us_data_provider

router = APIRouter(prefix="/api/usstock", tags=["US Stock"])

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

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_US_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "AMD", "INTC"]
INDEX_SYMBOLS = [
    {"symbol": "^DJI",  "name": "道瓊工業指數"},
    {"symbol": "^GSPC", "name": "S&P 500"},
    {"symbol": "^IXIC", "name": "那斯達克"},
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def _fetch_quote_sync(symbol: str) -> dict | None:
    """Fetch a single quote synchronously (run in thread)."""
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        price = round(float(fi.last_price), 2)
        prev  = round(float(fi.previous_close), 2)
        chg   = round(price - prev, 2)
        chg_p = round((chg / prev) * 100, 2) if prev else 0.0
        try:
            name = ticker.info.get("shortName") or symbol
        except Exception:
            name = symbol
        return {
            "symbol": symbol,
            "name": name,
            "price": price,
            "change": chg,
            "changePercent": chg_p,
        }
    except Exception as e:
        logger.warning(f"[usstock] quote failed {symbol}: {e}")
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/market")
async def get_us_market(symbols: Optional[str] = None):
    """Current price data for watchlist symbols."""
    target = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_US_SYMBOLS
    cache_key = "market:" + ",".join(target)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    results = await asyncio.gather(*[asyncio.to_thread(_fetch_quote_sync, s) for s in target])
    stocks = [r for r in results if r]
    # Validate: if no results, return error-friendly empty
    if not stocks and target:
        raise HTTPException(status_code=404, detail=f"找不到股票代號或目前無法獲取數據")
    data = {"stocks": stocks, "last_updated": datetime.now().isoformat()}
    _set_cache(cache_key, data)
    return data


@router.get("/indices")
async def get_us_indices():
    """Current data for major US market indices."""
    cached = _get_cache("indices")
    if cached:
        return cached

    async def fetch_index(idx):
        result = await asyncio.to_thread(_fetch_quote_sync, idx["symbol"])
        if result:
            result["name"] = idx["name"]
        return result

    results = await asyncio.gather(*[fetch_index(i) for i in INDEX_SYMBOLS])
    indices = [r for r in results if r]
    data = {"indices": indices, "last_updated": datetime.now().isoformat()}
    _set_cache("indices", data, ttl=60)
    return data


@router.get("/news")
async def get_us_news(symbols: Optional[str] = None, limit: int = 15):
    """Recent news for given symbols (or top symbols if none specified)."""
    target = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_US_SYMBOLS[:5]
    cache_key = "news:" + ",".join(target)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    provider = get_us_data_provider()
    all_news = []
    seen_titles = set()

    async def fetch_news_for(sym):
        try:
            items = await provider.get_news(sym, limit=5)
            return sym, items
        except Exception:
            return sym, []

    results = await asyncio.gather(*[fetch_news_for(s) for s in target])
    for sym, items in results:
        for item in (items or []):
            title = item.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_news.append({
                    "symbol": sym,
                    "title": title,
                    "url": item.get("url") or item.get("link", "#"),
                    "publisher": item.get("source") or item.get("publisher", ""),
                    "published": item.get("published_at") or item.get("providerPublishTime") or item.get("published", ""),
                })

    # Sort by publish time descending (best-effort)
    all_news.sort(key=lambda x: x.get("published", 0), reverse=True)
    all_news = all_news[:limit]
    data = {"data": all_news, "last_updated": datetime.now().isoformat()}
    _set_cache(cache_key, data, ttl=300)
    return data


@router.get("/pulse/{symbol}")
async def get_us_pulse(symbol: str):
    """Deep AI pulse analysis for a single US stock."""
    sym = symbol.upper()
    cache_key = f"pulse:{sym}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    provider = get_us_data_provider()

    try:
        price_data, tech_data, fund_data, news_data = await asyncio.gather(
            provider.get_price(sym),
            provider.get_technicals(sym),
            provider.get_fundamentals(sym),
            provider.get_news(sym, limit=3),
        )
    except Exception as e:
        logger.error(f"[usstock] pulse failed for {sym}: {e}")
        raise HTTPException(status_code=404, detail=f"查無美股代號「{sym}」或目前無法獲取數據")

    curr_price  = price_data.get("price", 0)
    change_pct  = round(price_data.get("change_percent", 0), 2)
    company     = price_data.get("name") or sym

    # Build AI summary
    trend_str = "呈現上漲趨勢" if change_pct > 0 else ("呈現下跌態勢" if change_pct < 0 else "走勢平穩")
    rsi = tech_data.get("rsi")
    rsi_str = ""
    if isinstance(rsi, (int, float)):
        if rsi > 70:
            rsi_str = "，RSI 顯示可能處於超買區間，短期留意回檔"
        elif rsi < 30:
            rsi_str = "，RSI 顯示可能處於超賣區間，或有反彈契機"
        else:
            rsi_str = "，RSI 落在中性區間"

    pe = fund_data.get("pe_ratio", "N/A")
    pe_str = f"；本益比 (P/E) 約為 {pe}" if pe and pe != "N/A" else ""

    summary = (
        f"根據最新市場數據，{company} ({sym}) 目前股價為 ${curr_price}，"
        f"24小時{trend_str} ({change_pct:+.2f}%){rsi_str}{pe_str}。"
        f"此為由 CryptoMind AI 根據即時技術與基本面指標自動合成之脈動報告。"
    )

    key_points = [
        f"RSI(14): {tech_data.get('rsi', 'N/A')}",
        f"MACD: {tech_data.get('macd', {}).get('histogram', 'N/A') if isinstance(tech_data.get('macd'), dict) else tech_data.get('macd', 'N/A')}",
        f"P/E Ratio: {fund_data.get('pe_ratio', 'N/A')}",
        f"EPS: {fund_data.get('eps', 'N/A')}",
        f"Market Cap: {fund_data.get('market_cap', 'N/A')}",
        f"52W High: {price_data.get('fifty_two_week_high', 'N/A')}",
        f"52W Low: {price_data.get('fifty_two_week_low', 'N/A')}",
        f"Volume: {price_data.get('volume', 'N/A')}",
    ]

    highlights = [
        {"title": n.get("title", ""), "url": n.get("url") or n.get("link", "#")}
        for n in (news_data or [])[:3]
        if n.get("title")
    ]

    result = {
        "symbol": sym,
        "company_name": company,
        "current_price": curr_price,
        "change_24h": change_pct,
        "report": {
            "summary": summary,
            "key_points": key_points,
            "highlights": highlights,
        },
        "technical_indicators": tech_data,
        "fundamentals": fund_data,
    }
    _set_cache(cache_key, result, ttl=300)
    return result


@router.get("/klines/{symbol}")
async def get_us_klines(symbol: str, interval: str = "1d", limit: int = 200):
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
                    "time": idx.strftime("%Y-%m-%d"),
                    "open":   round(float(row["Open"]),   2),
                    "high":   round(float(row["High"]),   2),
                    "low":    round(float(row["Low"]),    2),
                    "close":  round(float(row["Close"]),  2),
                    "volume": int(row["Volume"]),
                })
            except Exception:
                continue
        return klines[-limit:]

    try:
        klines = await asyncio.to_thread(fetch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = {"symbol": sym, "interval": interval, "data": klines}
    _set_cache(cache_key, data, ttl=300)
    return data
