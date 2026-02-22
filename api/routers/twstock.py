from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import httpx

from api.utils import logger
from core.tools.tw_stock_tools import (
    tw_stock_price,
    tw_technical_analysis,
    tw_fundamentals,
    tw_institutional,
    tw_news
)

# ── Simple in-memory cache (key → (data, expiry_time)) ──────────────────────
_twse_cache: dict = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes

async def _fetch_twse(url: str, params: dict = None, cache_key: str = None) -> Any:
    """Fetch from TWSE OpenAPI with optional caching."""
    ck = cache_key or url
    if ck in _twse_cache:
        data, expiry = _twse_cache[ck]
        if datetime.now() < expiry:
            return data
    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            _twse_cache[ck] = (data, datetime.now() + timedelta(seconds=_CACHE_TTL_SECONDS))
            return data
    except Exception as e:
        logger.error(f"[TWSE fetch] {url} failed: {e}")
        raise

router = APIRouter(prefix="/api/twstock", tags=["TW Stock"])

# Default preset symbols for Taiwan Stocks (e.g., TSMC, Foxconn, MediaTek)
DEFAULT_TW_SYMBOLS = ["2330", "2317", "2454", "2308", "2881", "2412", "2882", "2891", "1301", "2002"]

import asyncio
import yfinance as yf

_STOCK_INFO_CACHE = {}

async def _get_stock_info(symbol: str):
    """
    獲取台股名稱及所屬交易所(處理.TW與.TWO)。
    This function caches the result to avoid slow repeated yfinance info calls.
    """
    symbol = symbol.replace('.TW', '').replace('.TWO', '')
    if symbol in _STOCK_INFO_CACHE:
        return _STOCK_INFO_CACHE[symbol]
    
    def fetch():
        # 1. 嘗試 TWSE (.TW)
        tw_ticker = yf.Ticker(f"{symbol}.TW")
        try:
            info = tw_ticker.info
            if 'shortName' in info or 'longName' in info:
                name = info.get('shortName') or info.get('longName') or symbol
                return {"formatted_symbol": f"{symbol}.TW", "name": name, "exchange": "TWSE"}
        except Exception:
            pass
            
        # 2. 嘗試 TPEx (.TWO)
        two_ticker = yf.Ticker(f"{symbol}.TWO")
        try:
            info = two_ticker.info
            if 'shortName' in info or 'longName' in info:
                name = info.get('shortName') or info.get('longName') or symbol
                return {"formatted_symbol": f"{symbol}.TWO", "name": name, "exchange": "TPEx"}
        except Exception:
            pass
            
        return {"formatted_symbol": f"{symbol}.TW", "name": symbol, "exchange": "TWSE"} # Fallback

    result = await asyncio.to_thread(fetch)
    _STOCK_INFO_CACHE[symbol] = result
    return result

@router.get("/market")
async def get_tw_market(symbols: Optional[str] = None):
    """
    Get current market data for a list of TW Stock symbols.
    If no symbols are provided, returns data for the top preset symbols.
    """
    try:
        target_symbols = [s.strip() for s in symbols.split(',')] if symbols else DEFAULT_TW_SYMBOLS
        results = []

        # Fetch all stock infos concurrently
        infos = await asyncio.gather(*[_get_stock_info(sym) for sym in target_symbols])

        for symbol, info in zip(target_symbols, infos):
            formatted_symbol = info["formatted_symbol"]
            
            # Use to_thread to avoid blocking the event loop with synchronous tool invocation
            price_data = await asyncio.to_thread(lambda sym=formatted_symbol: tw_stock_price.invoke({"ticker": sym}))
            
            if "error" not in price_data:
                results.append({
                    "Symbol": symbol,
                    "Name": info["name"],
                    "Exchange": info["exchange"],
                    "Close": price_data.get("current_price") or price_data.get("prev_close"),
                    "price_change_24h": price_data.get("change_pct", 0),
                    "Volume": price_data.get("recent_ohlcv", [-1])[0].get("volume", 0) if price_data.get("recent_ohlcv") else 0,
                })

        return {
            "top_performers": results,
            "last_updated": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to fetch TW market data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pulse/{symbol}")
async def get_tw_pulse(symbol: str):
    """
    Get detailed pulse data (Technical, Fundamental, Institutional, News) for a single TW Stock.
    """
    try:
        info = await _get_stock_info(symbol)
        formatted_symbol = info["formatted_symbol"]
        company_name = info["name"]
        
        price = await asyncio.to_thread(lambda: tw_stock_price.invoke({"ticker": formatted_symbol}))
        
        # Check for invalid symbols gracefully
        if "error" in price or not price.get("current_price"):
            raise HTTPException(status_code=404, detail=f"查無台股代號「{symbol}」或目前無法獲取其即時數據。")
            
        tech = await asyncio.to_thread(lambda: tw_technical_analysis.invoke({"ticker": formatted_symbol}))
        funds = await asyncio.to_thread(lambda: tw_fundamentals.invoke({"ticker": formatted_symbol}))
        inst = await asyncio.to_thread(lambda: tw_institutional.invoke({"ticker": formatted_symbol}))
        news = await asyncio.to_thread(lambda: tw_news.invoke({"ticker": formatted_symbol, "company_name": company_name}))

        # Generate a dynamic AI-like summary based on the data
        curr_price = price.get("current_price", 0)
        change = price.get("change_pct", 0)
        rsi = tech.get("rsi_14")
        foreign = inst.get("foreign_net")
        
        trend_str = "呈現上漲趨勢" if change > 0 else ("呈現下跌態勢" if change < 0 else "走勢平穩")
        rsi_str = ""
        if isinstance(rsi, (int, float)):
            if rsi > 70:
                rsi_str = "，RSI 指標顯示目前可能處於超買區間，短期需留意回檔風險"
            elif rsi < 30:
                rsi_str = "，RSI 指標顯示目前可能處於超賣區間，或有反彈契機"
            else:
                rsi_str = "，RSI 指標落在中性區間"
                
        foreign_str = ""
        if foreign and str(foreign) not in ["", "N/A"]:
            try:
                f_val = int(str(foreign).replace(",", ""))
                if f_val > 0:
                    foreign_str = f"；籌碼方面，外資近期呈現買超 ({f_val:,} 股)"
                elif f_val < 0:
                    foreign_str = f"；籌碼方面，外資近期呈現賣超 ({f_val:,} 股)"
            except ValueError:
                pass

        dynamic_summary = f"根據最新市場數據，{company_name} ({symbol}) 目前股價為 ${curr_price}，24小時{trend_str} ({change}%){rsi_str}{foreign_str}。此為由 CryptoMind AI 根據即時技術與籌碼指標自動合成之脈動報告。"

        # Only pass valid news items with links
        valid_news = [{"title": n.get("title", ""), "url": n.get("url", "")} for n in news[:3]] if isinstance(news, list) and len(news) > 0 and "error" not in news[0] else []

        # Filter out N/A foreign_net from key_points
        key_points = [
            f"RSI(14): {tech.get('rsi_14', 'N/A')}",
            f"MACD: {tech.get('macd', {}).get('histogram', 'N/A')}",
            f"本益比 (P/E): {funds.get('pe_ratio', 'N/A')}"
        ]
        
        foreign_net = inst.get('foreign_net', 'N/A')
        if foreign_net and str(foreign_net) != "N/A":
            key_points.append(f"外資買賣超: {foreign_net} 股")

        # Format structure to match Market Pulse
        return {
            "symbol": symbol,
            "company_name": company_name,
            "current_price": curr_price,
            "change_24h": change,
            "status": "completed",
            "source_mode": "on_demand",
            "report": {
                "summary": dynamic_summary,
                "key_points": key_points,
                "highlights": valid_news,
                "risks": []
            },
            "technical_indicators": tech,
            "fundamentals": funds,
            "institutional": inst,
            "news": news
        }

    except Exception as e:
        logger.error(f"Failed to fetch TW pulse data for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/klines/{symbol}")
async def get_tw_klines(symbol: str, interval: str = "1d", limit: int = 100):
    """
    Get historical K-line (OHLCV) data for TW Stock to render charts.
    interval: '1d', '1wk', '1mo'
    """
    try:
        import yfinance as yf
        formatted_symbol = f"{symbol}.TW" if not symbol.endswith(".TW") and not symbol.endswith(".TWO") else symbol
        
        # Calculate period based on interval and limit
        # For TW stocks via yfinance, 1d is usually fine for a few months/years
        period = "1y"
        if interval == "1wk":
            period = "2y"
        elif interval == "1mo":
            period = "5y"
            
        ticker = yf.Ticker(formatted_symbol)
        hist = ticker.history(period=period, interval=interval)
        
        if hist.empty:
             raise HTTPException(status_code=404, detail="無交易資料或該股票已下市")

        # Format for Lightweight Charts: { time, open, high, low, close, volume }
        klines = []
        for index, row in hist.iterrows():
            # index is a pandas Timestamp
            # Lightweight Charts expects 'time' as a string 'YYYY-MM-DD' for daily chart
            # Or unix timestamp
            try:
                time_val = index.strftime('%Y-%m-%d')
                klines.append({
                    "time": time_val,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"])
                })
            except Exception:
                continue
                
        # Keep only the requested limit
        klines = klines[-limit:]
        
        return {
            "symbol": symbol,
            "interval": interval,
            "data": klines
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch TW klines data for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── TWSE OpenAPI 代理端點 ─────────────────────────────────────────────────────

TWSE_BASE = "https://openapi.twse.com.tw/v1"

@router.get("/opendata/news")
async def get_tw_major_news(limit: int = 15, symbols: str = Query(None, description="Comma-separated stock codes to filter (e.g., '2330,2317')")):
    """
    取得上市公司每日重大訊息（來源：TWSE t187ap04_L）。
    """
    try:
        data = await _fetch_twse(f"{TWSE_BASE}/opendata/t187ap04_L", cache_key="twse_news")
        
        if symbols:
            target_symbols = [s.strip() for s in symbols.split(",")]
            data = [d for d in (data or []) if d.get("公司代號") in target_symbols]
            
        results = []
        for item in (data or [])[:limit]:
            results.append({
                "date":        item.get("發言日期", ""),
                "time":        item.get("發言時間", ""),
                "code":        item.get("公司代號", ""),
                "name":        item.get("公司名稱", ""),
                "subject":     item.get("主旨 ", "").strip() or item.get("主旨", "").strip(),
                "rule":        item.get("符合條款", ""),
                "fact_date":   item.get("事實發生日", ""),
                "description": item.get("說明", ""),
            })
        return {"data": results, "total": len(results), "last_updated": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"[TW News] {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"TWSE 重大訊息 API 呼叫失敗：{e}")


@router.get("/opendata/pe_ratio/{symbol}")
async def get_tw_pe_ratio(symbol: str):
    """
    取得個股本益比、殖利率、股價淨值比（來源：TWSE BWIBBU_d）。
    symbol: 股票代號，如 2330
    """
    try:
        data = await _fetch_twse(f"{TWSE_BASE}/exchangeReport/BWIBBU_d", cache_key="twse_pe_all")
        matching = [d for d in (data or []) if d.get("Code", "") == symbol]
        if not matching:
            # Try BWIBBU_ALL as fallback
            data2 = await _fetch_twse(f"{TWSE_BASE}/exchangeReport/BWIBBU_ALL", cache_key="twse_pe_all2")
            matching = [d for d in (data2 or []) if d.get("Code", "") == symbol]
        if not matching:
            raise HTTPException(status_code=404, detail=f"查無股票代號 {symbol} 的本益比資料")
        d = matching[0]
        return {
            "code":           d.get("Code", symbol),
            "name":           d.get("Name", ""),
            "date":           d.get("Date", ""),
            "pe_ratio":       d.get("PEratio", "N/A"),
            "dividend_yield": d.get("DividendYield", "N/A"),
            "pb_ratio":       d.get("PBratio", "N/A"),
            "dividend_year":  d.get("DividendYear", ""),
            "fiscal_quarter": d.get("FiscalYearQuarter", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TW PE Ratio] {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"TWSE 本益比 API 呼叫失敗：{e}")


@router.get("/opendata/monthly_revenue")
async def get_tw_monthly_revenue(limit: int = 50):
    """
    取得上市公司每月營業收入彙總（來源：TWSE t187ap05_L）。
    """
    try:
        data = await _fetch_twse(f"{TWSE_BASE}/opendata/t187ap05_L", cache_key="twse_monthly_rev")
        results = []
        for item in (data or [])[:limit]:
            results.append({
                "code":             item.get("公司代號", ""),
                "name":             item.get("公司名稱", ""),
                "industry":         item.get("產業別", ""),
                "ym":               item.get("資料年月", ""),
                "current_revenue":  item.get("營業收入-當月營收", ""),
                "mom_change_pct":   item.get("營業收入-上月比較增減(%)", ""),
                "yoy_change_pct":   item.get("營業收入-去年當月增減(%)", ""),
                "ytd_revenue":      item.get("累計營業收入-當月累計營收", ""),
                "ytd_yoy_pct":      item.get("累計營業收入-前期比較增減(%)", ""),
            })
        return {"data": results, "total": len(results), "last_updated": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"[TW Monthly Revenue] {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"TWSE 月營收 API 呼叫失敗：{e}")


@router.get("/opendata/dividend")
async def get_tw_dividend(limit: int = 50, symbols: str = Query(None, description="Comma-separated stock codes to filter")):
    """
    取得上市公司股利分派情形（來源：TWSE t187ap45_L）。
    """
    try:
        data = await _fetch_twse(f"{TWSE_BASE}/opendata/t187ap45_L", cache_key="twse_dividend")
        
        if symbols:
            target_symbols = [s.strip() for s in symbols.split(",")]
            data = [d for d in (data or []) if d.get("公司代號") in target_symbols]
            
        results = []
        for item in (data or [])[:limit]:
            results.append({
                "code":            item.get("公司代號", ""),
                "name":            item.get("公司名稱", ""),
                "year":            item.get("股利年度", ""),
                "progress":        item.get("決議（擬議）進度", ""),
                "board_date":      item.get("董事會（擬議）股利分派日", ""),
                "shareholder_meeting": item.get("股東會日期", ""),
                "cash_dividend":   item.get("股東配發-盈餘分配之現金股利(元/股)", ""),
                "stock_dividend":  item.get("股東配發-盈餘轉增資配股(元/股)", ""),
                "net_profit":      item.get("本期淨利(淨損)(元)", ""),
            })
        return {"data": results, "total": len(results), "last_updated": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"[TW Dividend] {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"TWSE 股利 API 呼叫失敗：{e}")


@router.get("/opendata/foreign_holding")
async def get_tw_foreign_holding():
    """
    取得集中市場外資及陸資持股前 20 名（來源：TWSE MI_QFIIS_sort_20）。
    """
    try:
        data = await _fetch_twse(f"{TWSE_BASE}/fund/MI_QFIIS_sort_20", cache_key="twse_foreign_top20")
        results = []
        for item in (data or []):
            results.append({
                "rank":              item.get("Rank", ""),
                "code":              item.get("Code", ""),
                "name":              item.get("Name", ""),
                "total_shares":      item.get("ShareNumber", ""),
                "available_shares":  item.get("AvailableShare", ""),
                "held_shares":       item.get("SharesHeld", ""),
                "available_pct":     item.get("AvailableInvestPer", ""),
                "held_pct":          item.get("SharesHeldPer", ""),
                "upper_limit_pct":   item.get("Upperlimit", ""),
            })
        return {"data": results, "total": len(results), "last_updated": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"[TW Foreign Holding] {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"TWSE 外資持股 API 呼叫失敗：{e}")
