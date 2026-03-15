"""
Market API Helper Functions
"""
import asyncio
import numpy as np
from datetime import datetime

from api.utils import logger
from api.symbols import (
    normalize_base_symbol,
    sanitize_base_symbols,
    sanitize_pair_symbols,
)
from api.globals import (
    cached_screener_result,
    FUNDING_RATE_CACHE,
    MARKET_PULSE_CACHE,
)
from analysis.crypto_screener_light import screen_top_cryptos_light as screen_top_cryptos
from analysis.market_pulse import get_market_pulse

# In-memory cache for static symbol lists
SYMBOL_CACHE = {
    "okx": {"data": None, "timestamp": 0}
}


async def run_sync(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


def normalize_funding_symbol(symbol: str) -> str:
    """Normalize funding rate symbol by removing suffixes."""
    return normalize_base_symbol(symbol)


def filter_funding_data_by_symbols(data: dict, symbol_list: list) -> dict:
    """Filter funding rate data for specific symbols."""
    filtered_data = {}
    for sym in symbol_list:
        normalized_sym = normalize_funding_symbol(sym)
        if normalized_sym in data:
            filtered_data[normalized_sym] = data[normalized_sym]
    return filtered_data


def parse_symbols_param(symbols: str) -> list:
    """Parse comma-separated symbols parameter."""
    return sanitize_base_symbols(symbols.split(','))


def compute_top_bottom_rates(rates: list, limit: int) -> tuple:
    """Compute top bullish and bearish rates from sorted list."""
    top_bullish = rates[:limit]
    top_bearish = rates[-limit:][::-1]
    return top_bullish, top_bearish


def sort_funding_rates(data: dict) -> list:
    """Sort funding rates by rate value (descending)."""
    return sorted(
        [(sym, info.get("fundingRate", 0)) for sym, info in data.items()],
        key=lambda x: x[1],
        reverse=True
    )


def format_funding_rates_response(
    timestamp: str,
    total_count: int,
    top_bullish: list,
    top_bearish: list,
    filtered_data: dict = None,
    filtered_count: int = None
) -> dict:
    """Format funding rates API response."""
    response = {
        "timestamp": timestamp,
        "total_count": total_count,
        "top_bullish": [{"symbol": s, "fundingRate": r} for s, r in top_bullish],
        "top_bearish": [{"symbol": s, "fundingRate": r} for s, r in top_bearish]
    }

    if filtered_data is not None:
        response["data"] = filtered_data
        response["filtered_count"] = filtered_count
    else:
        response["data"] = {
            sym: FUNDING_RATE_CACHE.get("data", {}).get(sym)
            for sym, _ in top_bullish + top_bearish
        }

    return response


def normalize_market_symbol(symbol: str) -> str:
    """Normalize market pulse symbol by removing suffixes."""
    return normalize_base_symbol(symbol)


def try_get_cached_pulse(symbol: str, deep_analysis: bool) -> dict:
    """Try to get market pulse from cache (returns None if miss)."""
    if not deep_analysis and symbol in MARKET_PULSE_CACHE:
        cached_data = MARKET_PULSE_CACHE[symbol].copy()
        cached_data["source_mode"] = "public_cache"
        return cached_data
    return None


async def perform_deep_analysis(symbol: str, sources: str, llm_key: str, llm_provider: str) -> dict:
    """Perform deep analysis using user's LLM key."""
    from utils.llm_client import create_llm_client_from_config
    from analysis.market_pulse import MarketPulseAnalyzer
    from api.services import save_market_pulse_cache

    logger.info(f"Deep Analysis Mode: Using User Key for {symbol}")
    user_client, _ = create_llm_client_from_config({
        "provider": llm_provider,
        "api_key": llm_key
    })

    analyzer = MarketPulseAnalyzer(client=user_client)
    enabled_sources = sources.split(',') if sources else None

    result = await run_sync(
        lambda: analyzer.analyze_movement(symbol, enabled_sources=enabled_sources)
    )

    if result and "error" not in result:
        result["source_mode"] = "deep_analysis"
        result["analyzed_by"] = llm_provider
        MARKET_PULSE_CACHE[symbol] = result
        await run_sync(save_market_pulse_cache)

    return result


async def perform_on_demand_analysis(symbol: str, sources: str, semaphore: asyncio.Semaphore) -> dict:
    """Perform on-demand market pulse analysis."""
    enabled_sources = sources.split(',') if sources else None
    from api.services import save_market_pulse_cache

    async with semaphore:
        result = await run_sync(
            lambda: get_market_pulse(symbol, enabled_sources=enabled_sources)
        )

    if result and "error" not in result:
        result["source_mode"] = "on_demand"
        MARKET_PULSE_CACHE[symbol] = result
        asyncio.create_task(asyncio.to_thread(save_market_pulse_cache))
        return result

    return None


def create_pending_pulse_response(symbol: str) -> dict:
    """Create a pending response for market pulse analysis."""
    return {
        "symbol": symbol,
        "status": "pending",
        "source_mode": "awaiting_update",
        "message": "Analysis in progress, please try again",
        "current_price": 0,
        "change_24h": 0,
        "change_1h": 0,
        "report": {
            "summary": "System is generating initial report for this symbol.",
            "key_points": [],
            "highlights": [],
            "risks": []
        }
    }


def replace_nan_in_dataframe(df):
    """Replace NaN values with None in dataframe."""
    if df.empty:
        return df
    return df.replace({np.nan: None})


def format_screener_response(df_gainers, df_losers, df_volume) -> dict:
    """Format screener results as API response."""
    top_performers = replace_nan_in_dataframe(df_gainers)
    top_losers = replace_nan_in_dataframe(df_losers)
    top_volume = replace_nan_in_dataframe(df_volume)

    return {
        "top_gainers": top_performers.to_dict(orient="records"),
        "top_losers": top_losers.to_dict(orient="records"),
        "top_volume": top_volume.to_dict(orient="records"),
        "last_updated": datetime.now().isoformat()
    }


def try_get_cached_screener(refresh: bool):
    """Try to get cached screener result."""
    if not refresh and cached_screener_result["data"] is not None:
        return cached_screener_result["data"]
    return None


async def run_custom_screener(request, market_pulse_cache, trigger_analysis_func):
    """Run custom screener for specific symbols."""
    sanitized_symbols = sanitize_pair_symbols(request.symbols or [])
    if not sanitized_symbols:
        logger.warning("Custom screener request contains no valid symbols; falling back to default screener.")
        return await run_default_screener(request.exchange, market_pulse_cache)

    logger.info(f"Running custom screener: {request.exchange}, Symbols: {len(sanitized_symbols)}")

    asyncio.get_running_loop().create_task(trigger_analysis_func(sanitized_symbols))

    summary_df, top_performers, oversold, overbought = await run_sync(
        lambda: screen_top_cryptos(
            exchange=request.exchange,
            limit=len(sanitized_symbols),
            interval="1d",
            target_symbols=sanitized_symbols,
            market_pulse_data=market_pulse_cache
        )
    )

    return {
        "top_gainers": replace_nan_in_dataframe(top_performers).to_dict(orient="records"),
        "top_losers": replace_nan_in_dataframe(oversold).to_dict(orient="records"),
        "top_volume": replace_nan_in_dataframe(summary_df).to_dict(orient="records"),
        "last_updated": datetime.now().isoformat()
    }


async def run_default_screener(exchange: str, market_pulse_cache):
    """Run default screener for top 10 cryptocurrencies."""
    df_volume, df_gainers, df_losers, _ = await run_sync(
        lambda: screen_top_cryptos(
            exchange=exchange,
            limit=10,
            interval="1d",
            target_symbols=None,
            market_pulse_data=market_pulse_cache
        )
    )

    result_data = format_screener_response(df_gainers, df_losers, df_volume)

    timestamp_str = datetime.now().isoformat()
    cached_screener_result["timestamp"] = timestamp_str
    cached_screener_result["data"] = result_data

    logger.info("Manual screener refresh complete (RAM updated).")
    return result_data
