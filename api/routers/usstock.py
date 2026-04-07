import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import yfinance as yf
from fastapi import APIRouter, Depends, Header, HTTPException

from api.deps import get_optional_current_user
from api.user_llm import resolve_user_llm_credentials
from api.utils import logger
from core.tools.us_data_provider import get_us_data_provider

router = APIRouter(prefix="/api/usstock", tags=["US Stock"])

# ── Optional Finnhub API key (free commercial use: https://finnhub.io) ─────────
# Set FINNHUB_API_KEY in .env to use Finnhub as primary quote source (legal).
# Falls back to yfinance if key is absent.
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

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


# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_US_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVDA", "NFLX", "AMD", "INTC",
]
INDEX_SYMBOLS = [
    {"symbol": "^DJI", "name": "道瓊工業指數"},
    {"symbol": "^GSPC", "name": "S&P 500"},
    {"symbol": "^IXIC", "name": "那斯達克"},
]

# Yahoo Finance headers (for search endpoint)
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Static name table for curated symbols (avoids slow yfinance .info calls)
# US names are English-only: zh = en = English name
_US_STOCK_NAMES: dict[str, dict] = {
    # 科技
    "AAPL": {"zh": "Apple", "en": "Apple"},
    "MSFT": {"zh": "Microsoft", "en": "Microsoft"},
    "GOOGL": {"zh": "Alphabet", "en": "Alphabet"},
    "AMZN": {"zh": "Amazon", "en": "Amazon"},
    "META": {"zh": "Meta", "en": "Meta"},
    "NVDA": {"zh": "NVIDIA", "en": "NVIDIA"},
    "TSLA": {"zh": "Tesla", "en": "Tesla"},
    "NFLX": {"zh": "Netflix", "en": "Netflix"},
    "AMD": {"zh": "AMD", "en": "AMD"},
    "INTC": {"zh": "Intel", "en": "Intel"},
    "QCOM": {"zh": "Qualcomm", "en": "Qualcomm"},
    "AVGO": {"zh": "Broadcom", "en": "Broadcom"},
    "TSM": {"zh": "TSMC ADR", "en": "TSMC ADR"},
    "ORCL": {"zh": "Oracle", "en": "Oracle"},
    "CRM": {"zh": "Salesforce", "en": "Salesforce"},
    # 金融
    "JPM": {"zh": "JPMorgan", "en": "JPMorgan"},
    "BAC": {"zh": "Bank of America", "en": "Bank of America"},
    "GS": {"zh": "Goldman Sachs", "en": "Goldman Sachs"},
    "WFC": {"zh": "Wells Fargo", "en": "Wells Fargo"},
    "V": {"zh": "Visa", "en": "Visa"},
    "MA": {"zh": "Mastercard", "en": "Mastercard"},
    # 消費
    "WMT": {"zh": "Walmart", "en": "Walmart"},
    "COST": {"zh": "Costco", "en": "Costco"},
    "HD": {"zh": "Home Depot", "en": "Home Depot"},
    "NKE": {"zh": "Nike", "en": "Nike"},
    "MCD": {"zh": "McDonald's", "en": "McDonald's"},
    "SBUX": {"zh": "Starbucks", "en": "Starbucks"},
    # 醫療
    "JNJ": {"zh": "J&J", "en": "J&J"},
    "UNH": {"zh": "UnitedHealth", "en": "UnitedHealth"},
    "PFE": {"zh": "Pfizer", "en": "Pfizer"},
    "ABBV": {"zh": "AbbVie", "en": "AbbVie"},
    "MRK": {"zh": "Merck", "en": "Merck"},
    # 能源
    "XOM": {"zh": "ExxonMobil", "en": "ExxonMobil"},
    "CVX": {"zh": "Chevron", "en": "Chevron"},
    # ETF
    "SPY": {"zh": "S&P 500 ETF", "en": "S&P 500 ETF"},
    "QQQ": {"zh": "Nasdaq ETF", "en": "Nasdaq ETF"},
    "DIA": {"zh": "Dow Jones ETF", "en": "Dow Jones ETF"},
    "GLD": {"zh": "Gold ETF", "en": "Gold ETF"},
    "IWM": {"zh": "Russell 2000 ETF", "en": "Russell 2000 ETF"},
}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fetch_quote_sync(symbol: str) -> dict | None:
    """Fetch a single quote synchronously via yfinance (fallback)."""
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        price = round(float(fi.last_price), 2)
        prev = round(float(fi.previous_close), 2)
        chg = round(price - prev, 2)
        chg_p = round((chg / prev) * 100, 2) if prev else 0.0
        names = _US_STOCK_NAMES.get(symbol)
        if names:
            name_zh = names["zh"]
            name_en = names["en"]
        else:
            fallback = symbol
            name_zh = fallback
            name_en = fallback
        return {
            "symbol": symbol,
            "name": name_zh,       # backward compat
            "name_zh": name_zh,
            "name_en": name_en,
            "price": price,
            "change": chg,
            "changePercent": chg_p,
        }
    except Exception as e:
        logger.warning(f"[usstock] yfinance quote failed {symbol}: {e}")
        return None


async def _fetch_quotes_finnhub(symbols: list[str]) -> list[dict]:
    """Fetch quotes from Finnhub API (primary, legal, free 60 req/min).
    Returns only successfully fetched results; caller falls back to yfinance."""
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [
            client.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": s, "token": FINNHUB_API_KEY},
            )
            for s in symbols
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
    for sym, resp in zip(symbols, responses):
        try:
            if isinstance(resp, Exception):
                raise resp
            resp.raise_for_status()
            d = resp.json()
            price = round(float(d["c"]), 2)
            prev = round(float(d["pc"]), 2)
            if price == 0:
                continue  # Finnhub returns 0 for unknown symbols
            chg = round(price - prev, 2)
            chg_p = round((chg / prev) * 100, 2) if prev else 0.0
            names = _US_STOCK_NAMES.get(sym)
            if names:
                name_zh = names["zh"]
                name_en = names["en"]
            else:
                name_zh = sym
                name_en = sym
            results.append({
                "symbol": sym,
                "name": name_zh,       # backward compat
                "name_zh": name_zh,
                "name_en": name_en,
                "price": price,
                "change": chg,
                "changePercent": chg_p,
            })
        except Exception as e:
            logger.warning(f"[usstock] Finnhub quote failed {sym}: {e}")
    return results


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/market")
async def get_us_market(symbols: Optional[str] = None):
    """Current price data for watchlist symbols."""
    target = (
        [s.strip().upper() for s in symbols.split(",")]
        if symbols
        else DEFAULT_US_SYMBOLS
    )
    cache_key = "market:" + ",".join(target)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    if FINNHUB_API_KEY:
        stocks = await _fetch_quotes_finnhub(target)
        # Fallback to yfinance for any symbols Finnhub couldn't return
        fetched = {s["symbol"] for s in stocks}
        missing = [s for s in target if s not in fetched]
        if missing:
            fallback = await asyncio.gather(*[asyncio.to_thread(_fetch_quote_sync, s) for s in missing])
            stocks += [r for r in fallback if r]
    else:
        results = await asyncio.gather(*[asyncio.to_thread(_fetch_quote_sync, s) for s in target])
        stocks = [r for r in results if r]

    if not stocks and target:
        raise HTTPException(status_code=404, detail="找不到股票代號或目前無法獲取數據")
    data = {"stocks": stocks, "last_updated": datetime.now(timezone.utc).isoformat()}
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
    data = {"indices": indices, "last_updated": datetime.now(timezone.utc).isoformat()}
    _set_cache("indices", data, ttl=60)
    return data


@router.get("/news")
async def get_us_news(symbols: Optional[str] = None, limit: int = 15):
    """Recent news for given symbols (or top symbols if none specified)."""
    target = (
        [s.strip().upper() for s in symbols.split(",")]
        if symbols
        else DEFAULT_US_SYMBOLS[:5]
    )
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
        for item in items or []:
            title = item.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_news.append(
                    {
                        "symbol": sym,
                        "title": title,
                        "url": item.get("url") or item.get("link", "#"),
                        "publisher": item.get("source") or item.get("publisher", ""),
                        "published": item.get("published_at")
                        or item.get("providerPublishTime")
                        or item.get("published", ""),
                    }
                )

    # Sort by publish time descending (best-effort)
    all_news.sort(key=lambda x: x.get("published", 0), reverse=True)
    all_news = all_news[:limit]
    data = {"data": all_news, "last_updated": datetime.now(timezone.utc).isoformat()}
    _set_cache(cache_key, data, ttl=300)
    return data


@router.get("/pulse/{symbol}")
async def get_us_pulse(
    symbol: str,
    deep_analysis: bool = False,
    x_user_llm_provider: Optional[str] = Header(None),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    """Deep AI pulse analysis for a single US stock."""
    sym = symbol.upper()
    cache_key = f"pulse:{sym}"
    if not deep_analysis:
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
        raise HTTPException(
            status_code=404, detail=f"查無美股代號「{sym}」或目前無法獲取數據"
        )

    curr_price = price_data.get("price", 0)
    change_pct = round(price_data.get("change_percent", 0), 2)
    company = price_data.get("name") or sym

    # Build AI summary
    trend_str = (
        "呈現上漲趨勢"
        if change_pct > 0
        else ("呈現下跌態勢" if change_pct < 0 else "走勢平穩")
    )
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

    source_mode = "on_demand"
    credentials = None
    if deep_analysis:
        credentials = await resolve_user_llm_credentials(
            current_user, x_user_llm_provider
        )
    if credentials:
        from api.routers.deep_analysis_helper import deep_analyze_generic

        context = (
            f"公司: {company} ({sym})\n"
            f"現價: ${curr_price}\n"
            f"24H 漲跌幅: {change_pct:+.2f}%\n"
            f"RSI(14): {tech_data.get('rsi', 'N/A')}\n"
            f"MACD: {tech_data.get('macd', {}).get('histogram', 'N/A') if isinstance(tech_data.get('macd'), dict) else tech_data.get('macd', 'N/A')}\n"
            f"P/E Ratio: {fund_data.get('pe_ratio', 'N/A')}\n"
            f"市值: {fund_data.get('market_cap', 'N/A')}\n"
            f"52W High: {price_data.get('fifty_two_week_high', 'N/A')}\n"
            f"52W Low: {price_data.get('fifty_two_week_low', 'N/A')}"
        )
        ai_text = await deep_analyze_generic(
            sym, context, credentials["api_key"], credentials["provider"]
        )
        if ai_text:
            summary = ai_text
            source_mode = "deep_analysis"

    result = {
        "symbol": sym,
        "company_name": company,
        "current_price": curr_price,
        "change_24h": change_pct,
        "source_mode": source_mode,
        "report": {
            "summary": summary,
            "key_points": key_points,
            "highlights": highlights,
        },
        "technical_indicators": tech_data,
        "fundamentals": fund_data,
    }
    if not deep_analysis:
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
                klines.append(
                    {
                        "time": idx.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "volume": int(row["Volume"]),
                    }
                )
            except Exception:
                continue
        return klines[-limit:]

    try:
        klines = await asyncio.to_thread(fetch)
    except Exception:
        raise HTTPException(status_code=404, detail="無法獲取股票數據")

    data = {"symbol": sym, "interval": interval, "data": klines}
    _set_cache(cache_key, data, ttl=300)
    return data


@router.get("/search")
async def search_us_stocks(q: str):
    """Search US stocks via Yahoo Finance search API."""
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
        _us_exchanges = {"NMS", "NYQ", "NGM", "NCM", "PCX", "ASE"}
        results = [
            {"symbol": q["symbol"], "name": q.get("shortname") or q.get("longname") or q["symbol"]}
            for q in quotes
            if "." not in q.get("symbol", "")
            and q.get("quoteType") == "EQUITY"
            and q.get("exchange") in _us_exchanges
        ]
        return {"results": results}
    except Exception as e:
        logger.warning(f"[usstock] search failed: {e}")
        return {"results": []}
