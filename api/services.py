import asyncio
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

from core.database import get_cache, set_cache
from core.config import (
    SUPPORTED_EXCHANGES, MARKET_PULSE_TARGETS, 
    MARKET_PULSE_UPDATE_INTERVAL, FUNDING_RATE_UPDATE_INTERVAL
)
from analysis.crypto_screener import screen_top_cryptos
from analysis.market_pulse import get_market_pulse
from trading.okx_api_connector import OKXAPIConnector
from data.data_fetcher import get_data_fetcher

from api.globals import (
    logger, 
    cached_screener_result, 
    MARKET_PULSE_CACHE, 
    FUNDING_RATE_CACHE, 
    screener_lock, 
    funding_rate_lock
)

# --- Market Pulse Cache Functions ---
def save_market_pulse_cache():
    """Save Market Pulse data to DB."""
    try:
        set_cache("MARKET_PULSE", MARKET_PULSE_CACHE)
        logger.info(f"Market Pulse cache saved to DB")
    except Exception as e:
        logger.error(f"Failed to save Market Pulse cache: {e}")

def load_market_pulse_cache():
    """Load Market Pulse data from DB."""
    try:
        data = get_cache("MARKET_PULSE")
        if data:
            # We modify the global dictionary in place
            MARKET_PULSE_CACHE.clear()
            MARKET_PULSE_CACHE.update(data)
            logger.info(f"Loaded Market Pulse cache from DB ({len(MARKET_PULSE_CACHE)} symbols)")
    except Exception as e:
        logger.error(f"Failed to load Market Pulse cache: {e}")

# --- Funding Rate Cache Functions ---
def save_funding_rate_cache():
    """Save Funding Rate data to DB."""
    try:
        set_cache("FUNDING_RATE", FUNDING_RATE_CACHE)
        logger.info(f"Funding Rate cache saved ({len(FUNDING_RATE_CACHE.get('data', {}))} symbols)")
    except Exception as e:
        logger.error(f"Failed to save Funding Rate cache: {e}")

def load_funding_rate_cache():
    """Load Funding Rate data from DB."""
    try:
        data = get_cache("FUNDING_RATE")
        if data:
            FUNDING_RATE_CACHE["timestamp"] = data.get("timestamp")
            FUNDING_RATE_CACHE["data"] = data.get("data")
            logger.info(f"Loaded Funding Rate cache from DB ({len(FUNDING_RATE_CACHE.get('data', {}))} symbols)")
    except Exception as e:
        logger.error(f"Failed to load Funding Rate cache: {e}")

# --- Screener Cache Functions ---
def save_screener_cache(data: Dict[str, Any]):
    """Save screener data to DB."""
    try:
        set_cache("SCREENER", data)
        logger.info(f"Screener cache saved to DB")
    except Exception as e:
        logger.error(f"Failed to save screener cache: {e}")

def load_screener_cache():
    """Load screener data from DB."""
    try:
        data = get_cache("SCREENER")
        if data:
            cached_screener_result["timestamp"] = data.get("timestamp")
            cached_screener_result["data"] = data.get("data")
            logger.info(f"Loaded screener cache from DB (Timestamp: {data.get('timestamp')})")
    except Exception as e:
        logger.error(f"Failed to load screener cache: {e}")

# --- Background Tasks ---

async def update_funding_rates():
    """Update all funding rates from OKX."""
    async with funding_rate_lock:
        try:
            logger.info("Updating funding rates...")
            loop = asyncio.get_running_loop()
            okx = OKXAPIConnector()

            # 在執行緒池中執行（因為是同步 API 調用）
            funding_rates = await loop.run_in_executor(None, okx.get_all_funding_rates)

            if "error" not in funding_rates:
                FUNDING_RATE_CACHE["timestamp"] = datetime.now().isoformat()
                FUNDING_RATE_CACHE["data"] = funding_rates
                save_funding_rate_cache()
                logger.info(f"Funding rates updated: {len(funding_rates)} symbols")
            else:
                logger.error(f"Failed to update funding rates: {funding_rates.get('error')}")
        except Exception as e:
            logger.error(f"Funding rate update error: {e}")

async def funding_rate_update_task():
    """Background task to update funding rates periodically."""
    await asyncio.sleep(5)  # 延遲啟動

    # 初始更新
    await update_funding_rates()

    # 定期更新
    while True:
        await asyncio.sleep(FUNDING_RATE_UPDATE_INTERVAL)
        await update_funding_rates()

async def update_single_market_pulse(symbol: str, fixed_sources: List[str]):
    """Helper to update a single symbol for Market Pulse."""
    loop = asyncio.get_running_loop()
    try:
        logger.info(f"[Background] Updating Market Pulse for {symbol}...")
        result = await loop.run_in_executor(
            None, 
            lambda: get_market_pulse(symbol, enabled_sources=fixed_sources)
        )
        
        if result and "error" not in result:
            MARKET_PULSE_CACHE[symbol] = result
            logger.info(f"[Background] Successfully updated {symbol}")
        else:
            logger.warning(f"[Background] Failed to update {symbol}: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"[Background] Error updating {symbol}: {e}")

async def refresh_all_market_pulse_data(target_symbols: List[str] = None):
    """
    Refreshes Market Pulse data for specified symbols concurrently.
    Ensures all symbols share the EXACT SAME timestamp for consistency.
    """
    # Use provided symbols or fallback to defaults
    raw_symbols = target_symbols if target_symbols and len(target_symbols) > 0 else MARKET_PULSE_TARGETS
    
    # Normalize symbols: UPPER -> remove USDT/BUSD/- -> unique
    # This matches the key format used in get_market_pulse_api
    symbols_to_update = set()
    for s in raw_symbols:
        norm = s.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        if norm:
            symbols_to_update.add(norm)
    symbols_to_update = list(symbols_to_update)
    
    FIXED_SOURCES = ['google', 'cryptopanic', 'newsapi', 'cryptocompare']
    logger.info(f"🔄 Starting global Market Pulse refresh for: {symbols_to_update}")
    
    # 1. Run updates concurrently
    tasks = [update_single_market_pulse(sym, FIXED_SOURCES) for sym in symbols_to_update]
    await asyncio.gather(*tasks)
    
    # 2. Unify Timestamps
    # Even with concurrent execution, LLM processing times vary.
    # We overwrite the timestamp to ensure the UI shows them as one cohesive "snapshot".
    batch_timestamp = datetime.now().isoformat()
    for sym in symbols_to_update:
        if sym in MARKET_PULSE_CACHE:
            MARKET_PULSE_CACHE[sym]["timestamp"] = batch_timestamp
            
    # 3. Save Cache
    save_market_pulse_cache()
    logger.info("✅ Global Market Pulse refresh complete.")
    return batch_timestamp

async def update_market_pulse_task():
    """Background task to update Market Pulse analysis periodically."""
    
    # 1. Initial Fast Update
    logger.info("🚀 Starting initial Market Pulse analysis...")
    await refresh_all_market_pulse_data()

    # 2. Periodic Update Loop
    while True:
        await asyncio.sleep(MARKET_PULSE_UPDATE_INTERVAL)
        try:
            logger.info("Starting scheduled Market Pulse update cycle...")
            await refresh_all_market_pulse_data()
        except Exception as e:
            logger.error(f"Market Pulse task error: {e}")

async def update_screener_prices_fast():
    """
    快速更新任務：只更新 cached_screener_result 中的價格資訊。
    不重新計算指標或排名，僅抓取當前最新價格 (Ticker)。
    """
    if cached_screener_result["data"] is None:
        return

    try:
        # 使用 Binance 因為 API 響應快 (或根據配置)
        fetcher = get_data_fetcher("binance") 
        
        # 收集所有需要更新的 Symbol
        symbols = set()
        data = cached_screener_result["data"]
        
        for list_name in ["top_performers", "oversold", "overbought"]:
            if data.get(list_name):
                for item in data[list_name]:
                    symbols.add(item["Symbol"])
        
        if not symbols:
            return

        loop = asyncio.get_running_loop()
        all_tickers = await loop.run_in_executor(None, lambda: fetcher._make_request(fetcher.spot_base_url, "/ticker/24hr"))
        
        if not all_tickers:
            return

        # 建立價格查找表 {symbol: {price, change_percent}}
        price_map = {}
        for t in all_tickers:
            price_map[t['symbol']] = {
                'price': float(t['lastPrice']),
                'change': float(t['priceChangePercent'])
            }

        # 更新快取中的數據
        updated = False
        for list_name in ["top_performers", "oversold", "overbought"]:
            if data.get(list_name):
                for item in data[list_name]:
                    s = item["Symbol"].replace("/", "").replace("-", "")
                    if s in price_map:
                        item["Close"] = price_map[s]['price']
                        item["price_change_24h"] = price_map[s]['change']
                        updated = True
        
        if updated:
            if data.get("top_performers"):
                data["top_performers"].sort(key=lambda x: float(x.get("price_change_24h", 0)), reverse=True)

            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cached_screener_result["data"]["last_updated"] = timestamp_str
            cached_screener_result["timestamp"] = timestamp_str
            
    except Exception as e:
        pass

async def run_screener_analysis():
    """執行實際的分析工作並更新快取 (重型任務)"""
    # 如果已經鎖定，表示正在運行，無需重複
    if screener_lock.locked():
        logger.info("Screener analysis already in progress, skipping...")
        return
        
    async with screener_lock:
        logger.info("Starting heavy screener analysis...")
        try:
            exchange = SUPPORTED_EXCHANGES[0]
            loop = asyncio.get_running_loop()
            
            # 執行重型分析任務
            summary_df, top_performers, oversold, overbought = await loop.run_in_executor(
                None,
                lambda: screen_top_cryptos(
                    exchange=exchange,
                    limit=10, 
                    interval="1d",
                    target_symbols=None
                )
            )

            rename_map = {
                "Current Price": "Close", 
                "24h Change %": "price_change_24h",
                "7d Change %": "price_change_7d",
                "Signals": "signals"
            }
            
            top_performers = top_performers.rename(columns=rename_map).replace({np.nan: None})
            oversold = oversold.rename(columns=rename_map).replace({np.nan: None})
            overbought = overbought.rename(columns=rename_map).replace({np.nan: None})
            
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cached_screener_result["timestamp"] = timestamp_str
            cached_screener_result["data"] = {
                "top_performers": top_performers.to_dict(orient="records"),
                "oversold": oversold.to_dict(orient="records"),
                "overbought": overbought.to_dict(orient="records"),
                "last_updated": timestamp_str
            }
            
            save_screener_cache(cached_screener_result)
            logger.info("Heavy screener analysis complete.")
            
        except Exception as e:
            logger.error(f"❌ [分析任務] 執行失敗: {e}")

async def update_screener_task():
    """
    背景任務：
    1. 每秒執行快速價格更新 (Fast Update)
    2. 每 60 秒執行完整分析 (Heavy Analysis) - 降低頻率以避免 API 封禁
    """
    logger.info("🚀 Starting initial Screener analysis...")
    # Immediately run analysis on startup
    await run_screener_analysis()
    
    counter = 1
    while True:
        # 每秒都嘗試更新價格
        asyncio.create_task(update_screener_prices_fast())
        
        # 每 60 秒執行一次完整分析
        if counter % 60 == 0:
            asyncio.create_task(run_screener_analysis())
        
        counter += 1
        await asyncio.sleep(1)
