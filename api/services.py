import asyncio
import concurrent.futures
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 專用背景任務 executor，避免佔用 user request 的 default thread pool
_background_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="bg-task")

# 防止 screener 快速更新重疊執行
_price_update_running = False

from core.database import get_cache, set_cache
from core.config import (
    SUPPORTED_EXCHANGES, MARKET_PULSE_TARGETS, 
    MARKET_PULSE_UPDATE_INTERVAL, FUNDING_RATE_UPDATE_INTERVAL,
    SCREENER_UPDATE_INTERVAL_MINUTES
)
from analysis.market_pulse import get_market_pulse
from trading.okx_api_connector import OKXAPIConnector
from data.data_fetcher import get_data_fetcher

from api.globals import (
    logger, 
    cached_screener_result, 
    MARKET_PULSE_CACHE, 
    FUNDING_RATE_CACHE, 
    screener_lock, 
    funding_rate_lock,
    ANALYSIS_STATUS
)

# --- Market Pulse Cache Functions ---
def save_market_pulse_cache(silent=True):
    """Save Market Pulse data to DB."""
    try:
        set_cache("MARKET_PULSE", MARKET_PULSE_CACHE)
        if not silent:
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

# --- Funding Rate Cache Persistence ---
def save_funding_rate_cache(silent=True):
    """Save Funding Rate data to DB (Persistence)."""
    try:
        set_cache("FUNDING_RATES", FUNDING_RATE_CACHE.get("data", {}))
        if not silent:
            logger.info(f"Funding Rate cache saved to DB")
    except Exception as e:
        logger.error(f"Failed to save Funding Rate cache: {e}")

def load_funding_rate_cache():
    """Load Funding Rate data from DB (Persistence)."""
    try:
        data = get_cache("FUNDING_RATES")
        if data:
            FUNDING_RATE_CACHE["data"] = data
            FUNDING_RATE_CACHE["timestamp"] = datetime.now().isoformat() # Mark as loaded now, even if old
            logger.info(f"Loaded Funding Rate cache from DB ({len(data)} symbols)")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to load Funding Rate cache: {e}")
        return False

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
                
                # [Optimization] Persist to DB so it survives restart
                save_funding_rate_cache()
                
                logger.info(f"Funding rates updated & saved: {len(funding_rates)} symbols")
            else:
                logger.error(f"Failed to update funding rates: {funding_rates.get('error')}")
        except Exception as e:
            logger.error(f"Funding rate update error: {e}")

async def funding_rate_update_task():
    """Background task to update funding rates periodically."""
    # [Optimization] Try to load from DB immediately on startup
    if load_funding_rate_cache():
        initial_delay = 5 # If loaded, wait a bit before refreshing
    else:
        initial_delay = 1 # If empty, start refresh almost immediately

    await asyncio.sleep(initial_delay)

    # 初始更新
    await update_funding_rates()

    # 定期更新
    while True:
        await asyncio.sleep(FUNDING_RATE_UPDATE_INTERVAL)
        await update_funding_rates()

async def update_single_market_pulse(symbol: str, fixed_sources: List[str], semaphore: asyncio.Semaphore = None):
    """Helper to update a single symbol for Market Pulse with Timeout protection."""
    loop = asyncio.get_running_loop()
    
    async def _do_update():
        try:
            logger.info(f"[Background] Updating Market Pulse for {symbol}...")
            # 為同步函數執行加上超時保護 (180秒)
            # 注意: run_in_executor 本身不能直接 cancel，但在這裡 wrap 一層 wait_for 可以讓 asyncio 繼續往下走
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    _background_executor,
                    lambda: get_market_pulse(symbol, enabled_sources=fixed_sources)
                ),
                timeout=180.0
            )
            
            if result and "error" not in result:
                MARKET_PULSE_CACHE[symbol] = result
                logger.info(f"[Background] Successfully updated {symbol}")
            else:
                logger.warning(f"[Background] Failed to update {symbol}: {result.get('error', 'Unknown error')}")
        except asyncio.TimeoutError:
            logger.error(f"[Background] ⏱️ Timeout updating {symbol} - skipping after 180s")
        except asyncio.CancelledError:
            logger.warning(f"[Background] 🛑 Task for {symbol} was cancelled.")
            raise  # Re-raise to let the gathered task know it was cancelled
        except Exception as e:
            logger.error(f"[Background] Error updating {symbol}: {e}")

    if semaphore:
        async with semaphore:
            await _do_update()
    else:
        await _do_update()


# ============================================================================
# Market Pulse Helper Functions - Reduce complexity of refresh_all_market_pulse_data
# ============================================================================

def _calculate_market_pulse_window() -> tuple:
    """Calculate the current 4-hour update window."""
    now = datetime.now()
    window_hour = (now.hour // 4) * 4
    window_start = now.replace(hour=window_hour, minute=0, second=0, microsecond=0)
    return window_start, window_start.isoformat()


def _add_screener_symbols(symbols_set: set) -> int:
    """Add symbols from current screener results to the set. Returns count added."""
    screener_data = cached_screener_result.get("data", {})
    if not screener_data:
        return 0

    added_count = 0
    for category in ["top_volume", "top_gainers", "top_losers"]:
        for item in screener_data.get(category, []):
            if item.get("Symbol"):
                symbols_set.add(item["Symbol"].upper())
                added_count += 1

    return added_count


def _build_market_pulse_targets(target_symbols: List[str] = None) -> set:
    """Build the set of symbols to analyze based on priorities."""
    final_symbols = set()

    # Priority 1: Always analyze config targets (BTC, ETH, etc.)
    for s in MARKET_PULSE_TARGETS:
        final_symbols.add(s.upper())

    if target_symbols:
        # Priority 0: Explicit request (highest priority)
        for s in target_symbols:
            final_symbols.add(s.upper())
        logger.info(f"🎯 Targeted analysis request for {len(target_symbols)} symbols: {target_symbols}")
    else:
        # Priority 2: Add popular symbols from screener
        added_count = _add_screener_symbols(final_symbols)
        if added_count > 0:
            logger.info(f"🎯 Added {added_count} symbols from current Screener results.")
        else:
            logger.info("⚠️ No screener data found. Analyzing minimal config targets only.")

    return final_symbols


def _is_symbol_fresh_in_window(symbol_data: dict, window_start: datetime) -> bool:
    """Check if a symbol's data is fresh for the current window."""
    if not symbol_data or "timestamp" not in symbol_data:
        return False

    try:
        cache_time = datetime.fromisoformat(symbol_data["timestamp"])
        return cache_time >= window_start
    except Exception:
        return False


def _filter_fresh_symbols(symbols: set, window_start: datetime) -> tuple:
    """Filter out symbols that are already fresh in the current window.
    Returns (symbols_to_process, skipped_count)
    """
    symbols_to_process = []
    skipped_count = 0

    logger.info(f"📦 [Cache] Current cache has {len(MARKET_PULSE_CACHE)} symbols")

    for s in symbols:
        # Normalize: only take first part and uppercase (e.g., BTC-USDT -> BTC)
        norm = s.split("-")[0].split("/")[0].upper()
        if not norm:
            continue

        existing = MARKET_PULSE_CACHE.get(norm)
        if _is_symbol_fresh_in_window(existing, window_start):
            skipped_count += 1
            continue

        symbols_to_process.append(norm)

    return symbols_to_process, skipped_count


async def refresh_all_market_pulse_data(target_symbols: List[str] = None):
    """
    Refreshes Market Pulse data with Smart Resume and Fixed Window logic.
    - Fixed Windows: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
    - Resume: Skips symbols already analyzed in the current window.
    - Consistency: All data in a window shares the same timestamp.
    """
    now = datetime.now()
    window_start, window_start_iso = _calculate_market_pulse_window()
    logger.info(f"🎯 Current Update Window: {window_start_iso}")

    # Build target symbols list
    final_symbols = _build_market_pulse_targets(target_symbols)

    # Filter out fresh symbols
    symbols_to_process, skipped_count = _filter_fresh_symbols(final_symbols, window_start)

    window_hour = (now.hour // 4) * 4
    if skipped_count > 0:
        logger.info(f"⏭️ [Resume] {skipped_count} symbols already fresh in window {window_hour}:00")
    else:
        logger.info(f"ℹ️ [New Run] Starting full analysis for window {window_hour}:00")

    if not symbols_to_process:
        return window_start_iso

    # Init progress tracking
    ANALYSIS_STATUS["is_running"] = True
    ANALYSIS_STATUS["total"] = len(symbols_to_process) + skipped_count
    ANALYSIS_STATUS["completed"] = skipped_count
    ANALYSIS_STATUS["start_time"] = now.isoformat()

    FIXED_SOURCES = ['google', 'cryptopanic', 'newsapi', 'cryptocompare']
    sem = asyncio.Semaphore(2)

    # Batch saving optimization
    unsaved_changes = 0
    BATCH_SIZE = 10
    save_lock = asyncio.Lock()

    async def _safe_save_cache():
        """Helper to save cache securely using lock"""
        async with save_lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, set_cache, "MARKET_PULSE", MARKET_PULSE_CACHE)
            logger.info(f"💾 [Batch Save] Saved Market Pulse cache")

    async def _tracked_update(sym):
        nonlocal unsaved_changes
        try:
            await update_single_market_pulse(sym, FIXED_SOURCES, semaphore=sem)

            if sym in MARKET_PULSE_CACHE:
                MARKET_PULSE_CACHE[sym]["timestamp"] = window_start_iso

                should_save = False
                async with save_lock:
                    unsaved_changes += 1
                    if unsaved_changes >= BATCH_SIZE:
                        should_save = True
                        unsaved_changes = 0

                if should_save:
                    await _safe_save_cache()

        finally:
            ANALYSIS_STATUS["completed"] += 1

    # Execute all analysis tasks
    tasks = [_tracked_update(sym) for sym in symbols_to_process]
    await asyncio.gather(*tasks)

    ANALYSIS_STATUS["is_running"] = False
    logger.info(f"✅ Market Pulse Analysis completed for {len(tasks)} symbols")

    # Final save
    save_market_pulse_cache(silent=False)
    return window_start_iso

async def trigger_on_demand_analysis(symbols: List[str]):
    """
    Trigger immediate background analysis for specific symbols if they are stale.
    Designed for "Analyze what user is interested in" feature.
    """
    if not symbols: return
    
    # 1. Check validity (skip if recently updated)
    now = datetime.now()
    # Align to current 4-hour window
    window_hour = (now.hour // 4) * 4
    window_start = now.replace(hour=window_hour, minute=0, second=0, microsecond=0)
    
    to_update = []
    for s in symbols:
        norm = s.upper().split('-')[0]
        # logic: if cache exists AND timestamp is >= window_start, it's fresh enough
        existing = MARKET_PULSE_CACHE.get(norm)
        is_fresh = False
        if existing and "timestamp" in existing:
            try:
                ts = datetime.fromisoformat(existing["timestamp"])
                if ts >= window_start:
                    is_fresh = True
            except Exception as e:
                logger.debug(f"Failed to parse timestamp for {s}: {e}")
            
        if not is_fresh:
            to_update.append(norm)
            
    if not to_update:
        # logger.info("✨ Requested symbols are already fresh.")
        return

    logger.info(f"🚀 Triggering On-Demand Analysis for: {to_update}")
    
    # 2. Launch background updates
    # We use a semaphore to prevent overwhelming the API, but separate from the main loop
    sem = asyncio.Semaphore(4) 
    FIXED_SOURCES = ['google', 'cryptopanic', 'newsapi', 'cryptocompare']
    
    async def _runner(sym):
        try:
            # Re-use update_single_market_pulse
            await update_single_market_pulse(sym, FIXED_SOURCES, semaphore=sem)
            
            # Simple in-memory update mark (save is handled by background loop occasionally, or next startup)
            # But for good UX, let's update cache timestamp
            if sym in MARKET_PULSE_CACHE:
                MARKET_PULSE_CACHE[sym]["timestamp"] = window_start.isoformat()
        except Exception as e:
            logger.error(f"On-demand analysis failed for {sym}: {e}")

    # Fire and forget (create task)
    for sym in to_update:
        asyncio.create_task(_runner(sym))


# ============================================================================
# Market Pulse Task Helper Functions
# ============================================================================

def _get_cache_timestamps(cache):
    """Extract valid timestamps from market pulse cache."""
    timestamps = []
    for sym, data in cache.items():
        if data and "timestamp" in data:
            try:
                timestamps.append(datetime.fromisoformat(data["timestamp"]))
            except ValueError:
                pass
    return timestamps


def _analyze_cache_freshness(timestamps, now):
    """Analyze cache freshness and return action recommendation.
    Returns (action_type, initial_sleep_time, metadata)
    action_type: 'skip', 'delayed', 'immediate', 'full'
    """
    if not timestamps:
        return 'immediate', 0, {'reason': 'no_valid_timestamps'}

    newest_ts = max(timestamps)
    oldest_ts = min(timestamps)
    newest_age = (now - newest_ts).total_seconds()
    oldest_age = (now - oldest_ts).total_seconds()

    logger.info(
        f"📊 Cache age: newest={newest_age/60:.1f}min, oldest={oldest_age/60:.1f}min "
        f"(threshold={MARKET_PULSE_UPDATE_INTERVAL/60:.0f}min)"
    )

    # All cache is fresh
    if oldest_age < MARKET_PULSE_UPDATE_INTERVAL:
        remaining_time = MARKET_PULSE_UPDATE_INTERVAL - oldest_age
        return 'skip', remaining_time, {'newest_age': newest_age, 'oldest_age': oldest_age}

    # Cache is slightly stale but usable
    if oldest_age < MARKET_PULSE_UPDATE_INTERVAL * 3:
        return 'delayed', 60, {'oldest_age_hours': oldest_age/3600}

    # Cache is too old
    return 'immediate', MARKET_PULSE_UPDATE_INTERVAL, {'oldest_age_hours': oldest_age/3600}


async def _handle_cache_state_at_startup():
    """Handle market pulse cache state at startup and return initial sleep time."""
    now = datetime.now()
    cache_count = len(MARKET_PULSE_CACHE)
    logger.info(f"📦 Current cache has {cache_count} symbols")

    # Empty cache
    if cache_count == 0:
        logger.info("📭 Cache is empty. Triggering initial full refresh...")
        await refresh_all_market_pulse_data()
        return MARKET_PULSE_UPDATE_INTERVAL

    # Analyze cache freshness
    timestamps = _get_cache_timestamps(MARKET_PULSE_CACHE)
    action, sleep_time, metadata = _analyze_cache_freshness(timestamps, now)

    if action == 'skip':
        logger.info(f"✅ All cache is fresh! Sleeping for {sleep_time/60:.1f} minutes.")
        return sleep_time

    if action == 'delayed':
        logger.info(
            f"⚠️ Cache is stale ({metadata['oldest_age_hours']:.1f}h) but usable. "
            f"Starting background update in {sleep_time} seconds."
        )
        return sleep_time

    # Immediate action
    if 'oldest_age_hours' in metadata:
        logger.info(
            f"⏰ Cache is too old ({metadata['oldest_age_hours']:.1f}h). "
            "Triggering immediate refresh..."
        )
    else:
        logger.info("⚠️ No valid timestamps in cache. Triggering refresh...")

    await refresh_all_market_pulse_data()
    return sleep_time


async def update_market_pulse_task():
    """
    背景任務：定期更新市場脈動分析。

    ✅ 智能排程策略：
    1. 啟動時優先信任現有快取
    2. 只有在快取確實過期（超過 4 小時）時才觸發更新
    3. 定期週期性更新
    """
    logger.info("🚀 [Background] Initializing Market Pulse task...")

    initial_sleep_time = 0

    try:
        # Handle startup cache state
        initial_sleep_time = await _handle_cache_state_at_startup()
    except Exception as e:
        logger.error(f"⚠️ Error during startup check: {e}. Falling back to immediate full update.")
        try:
            await refresh_all_market_pulse_data()
            initial_sleep_time = MARKET_PULSE_UPDATE_INTERVAL
        except Exception as ex:
            logger.error(f"❌ Fallback update failed: {ex}")
            initial_sleep_time = 300

    # Enter periodic update loop
    while True:
        if initial_sleep_time > 0:
            logger.info(f"💤 Sleeping for {initial_sleep_time}s...")
            await asyncio.sleep(initial_sleep_time)

        try:
            logger.info("🔄 [Background] Starting scheduled Market Pulse update cycle...")
            await refresh_all_market_pulse_data()
            logger.info("✅ [Background] Scheduled update cycle complete.")
        except Exception as e:
            logger.error(f"❌ [Background] Market Pulse update cycle error: {e}")
        
        # [Optimization] Align next update to the next 4-hour wall clock mark
        # Instead of sleeping fixed 4 hours, we sleep until 00:00, 04:00, 08:00...
        now = datetime.now()
        current_block = now.hour // 4
        next_block_hour = (current_block + 1) * 4
        
        # Handle day rollover (e.g. 24 -> 00 of next day)
        if next_block_hour >= 24:
            next_target = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_target = now.replace(hour=next_block_hour, minute=0, second=0, microsecond=0)
            
        # Add a small buffer (e.g., 60 seconds) to ensure data providers have closed their candles
        next_target += timedelta(seconds=60)
        
        seconds_until_next = (next_target - datetime.now()).total_seconds()
        
        # Safety check: if calculation is weird, fallback to 5 minutes
        if seconds_until_next < 0:
             seconds_until_next = 300
             
        initial_sleep_time = seconds_until_next
        logger.info(f"📅 Next scheduled update aligned to: {next_target} (in {initial_sleep_time/60:.1f} minutes)")


# ============================================================================
# Screener Helper Functions - Reduce complexity of update_screener_prices_fast
# ============================================================================

def _collect_screener_symbols() -> set:
    """Collect all symbols from cached screener data."""
    if cached_screener_result["data"] is None:
        return set()

    symbols = set()
    data = cached_screener_result["data"]

    for list_name in ["top_performers", "oversold", "overbought"]:
        if data.get(list_name):
            for item in data[list_name]:
                symbols.add(item["Symbol"])

    return symbols


async def _fetch_okx_tickers():
    """Fetch current tickers from OKX exchange."""
    fetcher = get_data_fetcher("okx")
    loop = asyncio.get_running_loop()

    # 使用專用背景 executor，不擠佔 user request 的 default thread pool
    tickers_result = await loop.run_in_executor(
        _background_executor,
        lambda: fetcher._make_request(
            fetcher.market_base_url,
            "/market/tickers",
            params={"instType": "SPOT"}
        )
    )

    if tickers_result and tickers_result.get("code") == "0":
        return tickers_result.get("data", [])
    return []


def _build_price_map_from_tickers(tickers):
    """Build price lookup map from OKX ticker data."""
    price_map = {}
    for t in tickers:
        inst_id = t['instId']  # e.g., BTC-USDT
        symbol_key = inst_id.replace("-", "")  # BTCUSDT
        open_24h = float(t['open24h'])
        last = float(t['last'])

        price_map[symbol_key] = {
            'price': last,
            'change': ((last - open_24h) / open_24h * 100) if open_24h != 0 else 0
        }

    return price_map


def _update_screener_prices_from_map(price_map):
    """Update screener cached prices from price map."""
    data = cached_screener_result["data"]
    if not data:
        return False

    updated = False
    for list_name in ["top_performers", "oversold", "overbought"]:
        if data.get(list_name):
            for item in data[list_name]:
                s = item["Symbol"].replace("/", "").replace("-", "")
                if s in price_map:
                    item["Close"] = price_map[s]['price']
                    item["price_change_24h"] = price_map[s]['change']
                    updated = True

    if updated and data.get("top_performers"):
        # Re-sort by price change
        data["top_performers"].sort(
            key=lambda x: float(x.get("price_change_24h", 0)),
            reverse=True
        )

        # Update timestamp
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cached_screener_result["data"]["last_updated"] = timestamp_str
        cached_screener_result["timestamp"] = timestamp_str

    return updated


async def update_screener_prices_fast():
    """
    快速更新任務：只更新 cached_screener_result 中的價格資訊。
    不重新計算指標或排名，僅抓取當前最新價格 (Ticker)。
    有防重疊機制：若上一次更新仍在執行，直接跳過。
    """
    global _price_update_running
    if _price_update_running:
        return  # 上一次還沒完，跳過此輪
    _price_update_running = True
    try:
        # Collect symbols to update
        symbols = _collect_screener_symbols()
        if not symbols:
            return

        # Fetch current tickers
        tickers = await _fetch_okx_tickers()
        if not tickers:
            return

        # Build price map and update cache
        price_map = _build_price_map_from_tickers(tickers)
        _update_screener_prices_from_map(price_map)

    except Exception as e:
        logger.debug(f"Screener price update failed: {e}")
    finally:
        _price_update_running = False

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

            # Use lightweight screener for background task
            from analysis.crypto_screener_light import screen_top_cryptos_light

            # 使用專用背景 executor，不擠佔 user request 的 default thread pool
            df_volume, df_gainers, df_losers, _ = await loop.run_in_executor(
                _background_executor,
                lambda: screen_top_cryptos_light(
                    exchange=exchange,
                    limit=10,
                    interval="1d",
                    target_symbols=None
                )
            )

            # Handle potential None/NaN
            top_volume = df_volume.replace({np.nan: None}) if not df_volume.empty else df_volume
            top_gainers = df_gainers.replace({np.nan: None}) if not df_gainers.empty else df_gainers
            top_losers = df_losers.replace({np.nan: None}) if not df_losers.empty else df_losers
            
            # 只有當有數據時才更新快取，避免因網路錯誤導致快取被清空
            if not top_volume.empty or not top_gainers.empty:
                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cached_screener_result["timestamp"] = timestamp_str
                cached_screener_result["data"] = {
                    "top_volume": top_volume.to_dict(orient="records"),
                    "top_gainers": top_gainers.to_dict(orient="records"),
                    "top_losers": top_losers.to_dict(orient="records"),
                    "last_updated": timestamp_str
                }
                
                # [Optimization] RAM Only - No DB write
                logger.info(f"Background screener analysis complete (RAM updated). (Volume: {len(top_volume)}, Gainers: {len(top_gainers)}, Losers: {len(top_losers)})")
            else:
                logger.warning("Background screener analysis returned empty results. Skipping cache update.")
                
            # 解除鎖定由 async with 處理
            
        except Exception as e:
            logger.error(f"❌ [分析任務] 執行失敗: {e}")

async def _screener_ticker_callback(symbol: str, parsed: dict):
    """
    OKX WebSocket ticker push callback。
    每當 OKX 推送新 ticker 時直接更新 screener 快取，達到真正即時。
    """
    data = cached_screener_result.get("data")
    if not data:
        return

    last = parsed.get("last", 0)
    change = parsed.get("change24h", 0)
    # 正規化：BTC-USDT / BTC / BTCUSDT 都統一比較
    symbol_key = symbol.upper().replace("/", "").replace("-", "")

    all_list_names = ["top_volume", "top_gainers", "top_losers",
                      "top_performers", "oversold", "overbought"]
    for list_name in all_list_names:
        for item in data.get(list_name) or []:
            item_key = item.get("Symbol", "").upper().replace("/", "").replace("-", "")
            if item_key == symbol_key:
                item["Close"] = last
                item["price_change_24h"] = change

    cached_screener_result["data"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def _subscribe_screener_symbols_to_ws():
    """
    將 screener 快取內的幣種訂閱到 OKX Ticker WebSocket，
    取代 REST polling，讓價格由 OKX 主動推送。
    """
    from data.okx_websocket import okx_ticker_ws_manager

    data = cached_screener_result.get("data")
    if not data:
        return

    symbols = set()
    all_list_names = ["top_volume", "top_gainers", "top_losers",
                      "top_performers", "oversold", "overbought"]
    for list_name in all_list_names:
        for item in data.get(list_name) or []:
            sym = item.get("Symbol", "")
            if sym:
                # 轉為 BTCUSDT 格式再訂閱，_get_okx_inst_id 會自行轉換
                symbols.add(sym.upper().replace("/", "").replace("-", ""))

    if not symbols:
        return

    await okx_ticker_ws_manager.unsubscribe_all()
    await okx_ticker_ws_manager.subscribe_many(list(symbols), _screener_ticker_callback)
    logger.info(f"[Screener WS] 已訂閱 {len(symbols)} 個即時 ticker：{symbols}")


async def update_screener_task():
    """
    背景任務：
    1. 啟動時執行完整分析，並將結果幣種訂閱到 OKX Ticker WebSocket
    2. WebSocket push → 即時更新快取（取代 REST polling）
    3. 每 N 分鐘重新執行完整分析並更新訂閱清單（應對漲跌幅排名變動）
    """
    from data.okx_websocket import okx_ticker_ws_manager

    logger.info("🚀 Starting Screener: initial analysis + WebSocket price feed...")

    # 啟動 Ticker WebSocket（連線到 OKX public endpoint）
    await okx_ticker_ws_manager.start()

    # 初始完整分析
    await run_screener_analysis()

    # 訂閱分析結果幣種到 WebSocket，之後由 push 更新價格
    await _subscribe_screener_symbols_to_ws()

    update_interval_sec = SCREENER_UPDATE_INTERVAL_MINUTES * 60
    logger.info(f"Screener heavy analysis interval: {SCREENER_UPDATE_INTERVAL_MINUTES} min. Price feed: OKX WebSocket (real-time).")

    # 定期重新分析（更新排名 / 訂閱清單），價格由 WS 持續推送
    while True:
        await asyncio.sleep(update_interval_sec)
        await run_screener_analysis()
        await _subscribe_screener_symbols_to_ws()
