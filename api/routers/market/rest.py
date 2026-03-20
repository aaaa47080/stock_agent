"""
Market REST API Endpoints
"""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from api.deps import get_current_user
from api.globals import (
    ANALYSIS_STATUS,
    FUNDING_RATE_CACHE,
    MARKET_PULSE_CACHE,
    cached_screener_result,
    screener_lock,
)
from api.models import KlineRequest, RefreshPulseRequest, ScreenerRequest
from api.services import (
    refresh_all_market_pulse_data,
    trigger_on_demand_analysis,
    update_funding_rates,
)
from api.utils import logger
from data.market_data import get_klines
from utils.okx_api_connector import OKXAPIConnector

from .helpers import (
    compute_top_bottom_rates,
    create_pending_pulse_response,
    filter_funding_data_by_symbols,
    format_funding_rates_response,
    normalize_funding_symbol,
    normalize_market_symbol,
    parse_symbols_param,
    perform_deep_analysis,
    perform_on_demand_analysis,
    run_custom_screener,
    run_default_screener,
    run_sync,
    sort_funding_rates,
    try_get_cached_pulse,
    try_get_cached_screener,
)

router = APIRouter()

# Analysis semaphore for rate limiting
_analysis_semaphore = None


def get_analysis_semaphore():
    global _analysis_semaphore
    if _analysis_semaphore is None:
        _analysis_semaphore = asyncio.Semaphore(5)
    return _analysis_semaphore


@router.get("/api/market/symbols")
async def get_market_symbols(exchange: str = "okx"):
    """Get all available symbols for a given exchange (Cached for 60 minutes)."""
    from api.routers.market.helpers import SYMBOL_CACHE

    now = datetime.now().timestamp()
    if exchange in SYMBOL_CACHE:
        cache = SYMBOL_CACHE[exchange]
        if cache["data"] and (now - cache["timestamp"]) < 3600:
            return {"symbols": cache["data"]}

    logger.info(f"Requesting symbol list for exchange: {exchange}")
    try:
        from data.data_fetcher import get_data_fetcher

        def fetch_task():
            fetcher = get_data_fetcher(exchange)
            return fetcher.get_all_symbols()

        symbols = await run_sync(fetch_task)

        SYMBOL_CACHE[exchange] = {"data": symbols, "timestamp": now}

        logger.info(f"Successfully fetched {len(symbols)} symbols from {exchange}")
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"Failed to fetch symbols from {exchange}: {e}")
        if exchange in SYMBOL_CACHE and SYMBOL_CACHE[exchange]["data"]:
            logger.warning("Returning stale cache due to error.")
            return {"symbols": SYMBOL_CACHE[exchange]["data"]}

        raise HTTPException(status_code=500, detail="Failed to fetch symbol list")


@router.post("/api/screener")
async def run_screener(request: ScreenerRequest):
    """Return market screener data (uses cache first, supports background task wait)."""

    # 1. Custom symbol request - execute directly
    if request.symbols and len(request.symbols) > 0:
        try:
            return await run_custom_screener(
                request, MARKET_PULSE_CACHE, trigger_on_demand_analysis
            )
        except Exception as e:
            logger.error(f"Custom screener failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Custom screener failed")

    # 2. Try to return cached result
    cached = try_get_cached_screener(request.refresh)
    if cached:
        return cached

    # 3. If background task is running, wait for it
    if screener_lock.locked():
        logger.info("Cache miss/refresh (locked), waiting for background analysis...")
        async with screener_lock:
            if cached_screener_result["data"] is not None:
                return cached_screener_result["data"]

    # 4. Double-check locking pattern - execute if still no data
    async with screener_lock:
        cached = try_get_cached_screener(request.refresh)
        if cached:
            return cached

        logger.info(f"No cache, running screener: {request.exchange}")
        try:
            return await run_default_screener(request.exchange, MARKET_PULSE_CACHE)
        except Exception as e:
            logger.error(f"Screener error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Screener failed")


@router.post("/api/klines")
async def get_klines_data(request: KlineRequest):
    """Get K-line data for chart display."""
    try:
        df = await run_sync(
            lambda: get_klines(
                symbol=request.symbol,
                exchange=request.exchange,
                interval=request.interval,
                limit=request.limit,
            )
        )

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {request.symbol}")

        klines = []
        for _, row in df.iterrows():
            kline_data = {
                "time": int(row["timestamp"].timestamp())
                if hasattr(row["timestamp"], "timestamp")
                else int(row["timestamp"] / 1000),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            if "volume" in row.index and row["volume"] is not None:
                kline_data["volume"] = float(row["volume"])
            klines.append(kline_data)

        return {
            "symbol": request.symbol,
            "interval": request.interval,
            "klines": klines,
            "updated_at": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get klines: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get klines")


@router.get("/api/funding-rates")
async def get_funding_rates(refresh: bool = False, symbols: str = None, limit: int = 5):
    """Get funding rates (supports filtering by symbols)."""
    try:
        if refresh or not FUNDING_RATE_CACHE.get("data"):
            await update_funding_rates()

        data = FUNDING_RATE_CACHE.get("data", {})
        timestamp = FUNDING_RATE_CACHE.get("timestamp")

        if symbols:
            symbol_list = parse_symbols_param(symbols)
            filtered_data = filter_funding_data_by_symbols(data, symbol_list)

            if filtered_data:
                sorted_rates = sort_funding_rates(filtered_data)
                top_bullish = sorted_rates[: min(5, len(sorted_rates))]
                top_bearish = (
                    sorted_rates[-min(5, len(sorted_rates)) :][::-1]
                    if len(sorted_rates) > 5
                    else []
                )
            else:
                top_bullish = []
                top_bearish = []

            return format_funding_rates_response(
                timestamp=timestamp,
                total_count=len(data),
                top_bullish=top_bullish,
                top_bearish=top_bearish,
                filtered_data=filtered_data,
                filtered_count=len(filtered_data),
            )

        sorted_rates = sort_funding_rates(data)
        top_bullish, top_bearish = compute_top_bottom_rates(sorted_rates, limit)

        return format_funding_rates_response(
            timestamp=timestamp,
            total_count=len(data),
            top_bullish=top_bullish,
            top_bearish=top_bearish,
        )

    except Exception as e:
        logger.error(f"Failed to get funding rates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get funding rates")


@router.get("/api/funding-rate/{symbol}")
async def get_single_funding_rate(symbol: str):
    """Get funding rate for a single symbol."""
    try:
        base_symbol = normalize_funding_symbol(symbol)
        if not base_symbol:
            raise HTTPException(status_code=422, detail=f"Invalid symbol: {symbol}")

        if FUNDING_RATE_CACHE.get("data") and base_symbol in FUNDING_RATE_CACHE["data"]:
            return FUNDING_RATE_CACHE["data"][base_symbol]

        okx = OKXAPIConnector()
        instId = f"{base_symbol}-USDT-SWAP"
        result = okx.get_funding_rate(instId)

        if result.get("code") == "0" and result.get("data"):
            data = result["data"][0]
            return {
                "symbol": base_symbol,
                "instId": instId,
                "fundingRate": float(data.get("fundingRate", 0)) * 100,
                "nextFundingRate": float(data.get("nextFundingRate", 0)) * 100
                if data.get("nextFundingRate")
                else None,
                "fundingTime": data.get("fundingTime"),
                "nextFundingTime": data.get("nextFundingTime"),
            }
        return {"error": "Not found"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching single funding rate: {e}")
        return {"error": "Failed to get funding rate"}


@router.get("/api/funding-rate-history/{symbol}")
async def get_funding_rate_history(symbol: str):
    """Get funding rate history for a symbol."""
    try:
        base = normalize_funding_symbol(symbol)
        if not base:
            raise HTTPException(status_code=422, detail=f"Invalid symbol: {symbol}")
        instId = f"{base}-USDT-SWAP"

        logger.info(f"[History] Fetching for symbol: {symbol} -> instId: {instId}")

        okx = OKXAPIConnector()
        result = await run_sync(okx.get_funding_rate_history, instId)

        if result.get("code") == "0" and result.get("data"):
            history = []
            for item in result["data"]:
                history.append(
                    {
                        "time": item["fundingTime"],
                        "rate": float(item["fundingRate"]) * 100,
                        "realRate": float(item["realizedRate"]) * 100
                        if "realizedRate" in item
                        else float(item["fundingRate"]) * 100,
                    }
                )
            return {"data": history[::-1], "symbol": base}

        return {"error": "Failed to fetch history", "details": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return {"error": "Failed to get history"}


@router.post("/api/market-pulse/refresh-all", dependencies=[Depends(get_current_user)])
async def api_refresh_all_market_pulse(request: RefreshPulseRequest):
    """Trigger a global refresh of specified Market Pulse targets."""
    try:
        timestamp = await refresh_all_market_pulse_data(request.symbols)
        return {"status": "success", "timestamp": timestamp}
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")
        raise HTTPException(status_code=500, detail="Refresh failed")


@router.get("/api/market-pulse/progress")
async def get_market_pulse_progress():
    """Get the current status of background analysis task."""
    return ANALYSIS_STATUS


@router.get("/api/market-pulse/{symbol}")
async def get_market_pulse_api(
    symbol: str,
    sources: Optional[str] = None,
    refresh: bool = False,
    deep_analysis: bool = False,
    x_user_llm_key: Optional[str] = Header(None),
    x_user_llm_provider: Optional[str] = Header(None),
):
    """Get market pulse analysis with tiered access."""
    try:
        base_symbol = normalize_market_symbol(symbol)
        if not base_symbol:
            raise HTTPException(status_code=422, detail=f"Invalid symbol: {symbol}")

        # 1. Try public cache first
        cached = try_get_cached_pulse(base_symbol, deep_analysis)
        if cached:
            return cached

        # 2. Deep analysis mode with user's LLM key
        if deep_analysis and x_user_llm_key and x_user_llm_provider:
            try:
                result = await perform_deep_analysis(
                    base_symbol, sources, x_user_llm_key, x_user_llm_provider
                )
                if result:
                    return result
                if base_symbol in MARKET_PULSE_CACHE:
                    return MARKET_PULSE_CACHE[base_symbol]
            except Exception as e:
                logger.error(f"Deep analysis failed: {e}")
                if base_symbol in MARKET_PULSE_CACHE:
                    return MARKET_PULSE_CACHE[base_symbol]

        # 3. On-demand analysis
        logger.info(f"Cache miss for {base_symbol}, triggering immediate analysis...")

        try:
            result = await perform_on_demand_analysis(
                base_symbol, sources, get_analysis_semaphore()
            )
            if result:
                return result

            logger.warning(f"On-demand analysis failed for {base_symbol}")

        except Exception as e:
            logger.error(f"Error during on-demand analysis for {base_symbol}: {e}")

        return create_pending_pulse_response(base_symbol)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Market pulse failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Market pulse failed")
