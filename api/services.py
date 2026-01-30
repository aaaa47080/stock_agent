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

# [Optimization] Removed DB Cache functions for Screener/Funding (In-Memory Only)

# --- Background Tasks ---

async def update_funding_rates():
    """Update all funding rates from OKX (In-Memory Only)."""
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
                # [Optimization] No DB write
                logger.info(f"Funding rates updated in RAM: {len(funding_rates)} symbols")
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
                    None, 
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

async def refresh_all_market_pulse_data(target_symbols: List[str] = None):
    """
    Refreshes Market Pulse data with Smart Resume and Fixed Window logic.
    - Fixed Windows: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
    - Resume: Skips symbols already analyzed in the current window.
    - Consistency: All data in a window shares the same timestamp.
    """
    # 1. 計算當前 4 小時窗口的起始時間
    now = datetime.now()
    window_hour = (now.hour // 4) * 4
    window_start = now.replace(hour=window_hour, minute=0, second=0, microsecond=0)
    window_start_iso = window_start.isoformat()
    
    logger.info(f"🎯 Current Update Window: {window_start_iso}")

    # 2. 決定要分析的幣種清單
    final_symbols = set()
    for s in MARKET_PULSE_TARGETS:
         final_symbols.add(s.upper())
         
    if not target_symbols:
        try:
            logger.info("Fetching ALL volume tickers from OKX...")
            okx = OKXAPIConnector()
            loop = asyncio.get_running_loop()
            tickers_result = await loop.run_in_executor(None, lambda: okx.get_tickers("SPOT"))
            
            if tickers_result.get("code") == "0":
                tickers = tickers_result.get("data", [])
                usdt_tickers = [t for t in tickers if t["instId"].endswith("-USDT")]
                
                # [Optimization] Tiered Analysis Strategy
                # Sort by 24h Volume (descending) and take only TOP 50
                usdt_tickers.sort(key=lambda x: float(x.get("volCcy24h", 0)), reverse=True)
                
                TOP_N = 50
                top_tickers = usdt_tickers[:TOP_N]
                
                for t in top_tickers:
                    base_currency = t["instId"].split("-")[0]
                    final_symbols.add(base_currency)
                    
                logger.info(f"Filtered to TOP {len(top_tickers)} high-volume tokens (Tier 1) for auto-analysis.")
            else:
                logger.warning(f"Failed to fetch tickers: {tickers_result.get('msg')}")
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
    else:
        for s in target_symbols:
            final_symbols.add(s.upper())

    # 標準化並過濾已完成的幣種
    symbols_to_process = []
    skipped_count = 0
    
    # 診斷：確認當前記憶體中的快取狀態
    current_cache_size = len(MARKET_PULSE_CACHE)
    logger.info(f"📦 [數據診斷] 快取中現有 {current_cache_size} 個幣種數據")
    
    for s in final_symbols:
        # 統一標準化：只取第一段並大寫 (例如 BTC-USDT -> BTC)
        norm = s.split("-")[0].split("/")[0].upper()
        if not norm: continue
        
        existing = MARKET_PULSE_CACHE.get(norm)
        if existing and "timestamp" in existing:
            try:
                cache_time = datetime.fromisoformat(existing["timestamp"])
                if cache_time >= window_start:
                    skipped_count += 1
                    continue
            except:
                pass
        
        symbols_to_process.append(norm)
    
    if skipped_count > 0:
        logger.info(f"⏭️ [Resume] 偵測到當前窗口 ({window_hour}:00) 已有 {skipped_count} 個幣種，將自動跳過。")
    else:
        logger.info(f"ℹ️ [New Run] 當前窗口 ({window_hour}:00) 尚無完成記錄，開始全量分析。")

    if not symbols_to_process:
        return window_start_iso

    # Init Progress
    ANALYSIS_STATUS["is_running"] = True
    ANALYSIS_STATUS["total"] = len(symbols_to_process) + skipped_count 
    ANALYSIS_STATUS["completed"] = skipped_count
    ANALYSIS_STATUS["start_time"] = now.isoformat()
    
    FIXED_SOURCES = ['google', 'cryptopanic', 'newsapi', 'cryptocompare']
    sem = asyncio.Semaphore(2)  # 減少並發數，避免 OKX API SSL 連接問題
    
    # [Optimization] Batch saving variables
    unsaved_changes = 0
    BATCH_SIZE = 10  # Reduced DB write frequency by 90%
    save_lock = asyncio.Lock()

    async def _safe_save_cache():
        """Helper to save cache securely using lock"""
        async with save_lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, set_cache, "MARKET_PULSE", MARKET_PULSE_CACHE)
            logger.info(f"💾 [Batch Save] Saved Market Pulse cache to DB")

    async def _tracked_update(sym):
        nonlocal unsaved_changes
        try:
            await update_single_market_pulse(sym, FIXED_SOURCES, semaphore=sem)
            
            # Update success behavior: Mark timestamp but DON'T save immediately
            if sym in MARKET_PULSE_CACHE:
                MARKET_PULSE_CACHE[sym]["timestamp"] = window_start_iso
                
                # Check if we should trigger a batch save
                should_save = False
                async with save_lock: # Reuse lock for counter safety if needed, or just be loose about it
                     unsaved_changes += 1
                     if unsaved_changes >= BATCH_SIZE:
                         should_save = True
                         unsaved_changes = 0 # Reset counter
                
                if should_save:
                    await _safe_save_cache()

        finally:
            ANALYSIS_STATUS["completed"] += 1

    tasks = [_tracked_update(sym) for sym in symbols_to_process]
    await asyncio.gather(*tasks)
    
    # Final save to capture any remaining unsaved changes
    if unsaved_changes > 0:
        logger.info(f"💾 [Final Save] Saving remaining {unsaved_changes} updates...")
        await _safe_save_cache()

    ANALYSIS_STATUS["is_running"] = False
    return window_start_iso

async def update_market_pulse_task():
    """
    背景任務：定期更新市場脈動分析。

    ✅ 智能排程策略：
    1. 啟動時優先信任現有快取
    2. 只有在快取確實過期（超過 4 小時）時才觸發更新
    3. 定期週期性更新
    """
    logger.info("🚀 [Background] Initializing Market Pulse task...")

    loop = asyncio.get_running_loop()
    initial_sleep_time = 0

    try:
        # --- 步驟 1: 檢查現有快取狀態（優先信任快取）---
        now = datetime.now()
        cache_count = len(MARKET_PULSE_CACHE)
        logger.info(f"📦 Current cache has {cache_count} symbols")

        # 如果快取有數據，檢查最新的時間戳
        if cache_count > 0:
            timestamps = []
            for sym, data in MARKET_PULSE_CACHE.items():
                if data and "timestamp" in data:
                    try:
                        ts = datetime.fromisoformat(data["timestamp"])
                        timestamps.append(ts)
                    except ValueError:
                        pass

            if timestamps:
                newest_ts = max(timestamps)
                oldest_ts = min(timestamps)
                newest_age = (now - newest_ts).total_seconds()
                oldest_age = (now - oldest_ts).total_seconds()

                logger.info(f"📊 Cache age: newest={newest_age/60:.1f}min, oldest={oldest_age/60:.1f}min (threshold={MARKET_PULSE_UPDATE_INTERVAL/60:.0f}min)")

                # 如果最老的數據都還沒過期，就不需要更新
                if oldest_age < MARKET_PULSE_UPDATE_INTERVAL:
                    remaining_time = MARKET_PULSE_UPDATE_INTERVAL - oldest_age
                    logger.info(f"✅ All cache is fresh! Sleeping for {remaining_time/60:.1f} minutes until next update.")
                    initial_sleep_time = remaining_time
                elif oldest_age < MARKET_PULSE_UPDATE_INTERVAL * 3:
                    # [優化] 如果數據只是「稍微過期」(例如過期幾小時)，不要在啟動時阻塞做全量更新
                    # 先讓 API 可以讀取這些舊數據，然後在背景稍後(1分鐘後)再開始更新
                    logger.info(f"⚠️ Cache is stale ({oldest_age/3600:.1f}h) but usable for startup. Skipping immediate blocking refresh.")
                    initial_sleep_time = 60 # 1分鐘後再開始背景更新
                else:
                    # 有嚴重過期數據 (>12小時)，觸發更新
                    logger.info(f"⏰ Cache is too old ({oldest_age/3600:.1f}h). Triggering immediate refresh...")
                    await refresh_all_market_pulse_data()
                    initial_sleep_time = MARKET_PULSE_UPDATE_INTERVAL
            else:
                # 沒有有效時間戳，觸發更新
                logger.info("⚠️ No valid timestamps in cache. Triggering refresh...")
                await refresh_all_market_pulse_data()
                initial_sleep_time = MARKET_PULSE_UPDATE_INTERVAL
        else:
            # 快取為空，觸發全量更新
            logger.info("📭 Cache is empty. Triggering initial full refresh...")
            await refresh_all_market_pulse_data()
            initial_sleep_time = MARKET_PULSE_UPDATE_INTERVAL

    except Exception as e:
        logger.error(f"⚠️ Error during startup check: {e}. Falling back to immediate full update.")
        try:
            await refresh_all_market_pulse_data()
            initial_sleep_time = MARKET_PULSE_UPDATE_INTERVAL
        except Exception as ex:
            logger.error(f"❌ Fallback update failed: {ex}")
            initial_sleep_time = 300

    # 2. 進入週期性更新迴圈
    while True:
        # 等待下一次更新時間
        if initial_sleep_time > 0:
            logger.info(f"💤 Sleeping for {initial_sleep_time}s...")
            await asyncio.sleep(initial_sleep_time)
        
        try:
            logger.info("🔄 [Background] Starting scheduled Market Pulse update cycle...")
            # 週期性任務執行全量更新 (傳入 None 會自動抓所有)
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
            next_target = now.replace(hour=0, minute=0, second=0, microsecond=0) + getattr(datetime, 'timedelta')(days=1)
        else:
            next_target = now.replace(hour=next_block_hour, minute=0, second=0, microsecond=0)
            
        # Add a small buffer (e.g., 60 seconds) to ensure data providers have closed their candles
        next_target += getattr(datetime, 'timedelta')(seconds=60)
        
        seconds_until_next = (next_target - datetime.now()).total_seconds()
        
        # Safety check: if calculation is weird, fallback to 5 minutes
        if seconds_until_next < 0:
             seconds_until_next = 300
             
        initial_sleep_time = seconds_until_next
        logger.info(f"📅 Next scheduled update aligned to: {next_target} (in {initial_sleep_time/60:.1f} minutes)")

async def update_screener_prices_fast():
    """
    快速更新任務：只更新 cached_screener_result 中的價格資訊。
    不重新計算指標或排名，僅抓取當前最新價格 (Ticker)。
    """
    if cached_screener_result["data"] is None:
        return

    try:
        # 使用 OKX 獲取最新價格 (Ticker)
        fetcher = get_data_fetcher("okx") 
        
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
        # OKX get_tickers returns a different structure, but Binance format is used in price_map
        # We'll adapt it to use OKX's ticker structure
        tickers_result = await loop.run_in_executor(None, lambda: fetcher._make_request(fetcher.market_base_url, "/market/tickers", params={"instType": "SPOT"}))
        
        if not tickers_result or tickers_result.get("code") != "0":
            return
            
        all_tickers = tickers_result.get("data", [])

        # 建立價格查找表 {symbol: {price, change_percent}}
        price_map = {}
        for t in all_tickers:
            instId = t['instId'] # e.g. BTC-USDT
            symbol_key = instId.replace("-", "") # BTCUSDT
            price_map[symbol_key] = {
                'price': float(t['last']),
                'change': ((float(t['last']) - float(t['open24h'])) / float(t['open24h']) * 100) if float(t['open24h']) != 0 else 0
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
                    limit=50, # [Optimization] Analyze Top 50 to populate filter list
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
            
            # 只有當有數據時才更新快取，避免因網路錯誤導致快取被清空
            if not top_performers.empty:
                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cached_screener_result["timestamp"] = timestamp_str
                cached_screener_result["data"] = {
                    "top_performers": top_performers.to_dict(orient="records"),
                    "oversold": oversold.to_dict(orient="records"),
                    "overbought": overbought.to_dict(orient="records"),
                    "last_updated": timestamp_str
                }
                
                # [Optimization] RAM Only - No DB write
                logger.info(f"Heavy screener analysis complete (RAM updated). (Top: {len(top_performers)})")
            else:
                logger.warning("Heavy screener analysis returned empty results. Skipping cache update.")
                
            # 解除鎖定由 async with 處理
            
        except Exception as e:
            logger.error(f"❌ [分析任務] 執行失敗: {e}")

async def update_screener_task():
    """
    背景任務：
    1. 每秒執行快速價格更新 (Fast Update)
    2. 每 N 分鐘執行完整分析 (Heavy Analysis) - 降低頻率以避免 API 封禁
    """
    logger.info("🚀 Starting initial Screener analysis (In-Memory)...")
    # Immediately run analysis on startup
    await run_screener_analysis()
    
    # [Optimization] Use config variable (minutes -> seconds)
    update_interval_sec = SCREENER_UPDATE_INTERVAL_MINUTES * 60
    logger.info(f"Screener background task interval set to {SCREENER_UPDATE_INTERVAL_MINUTES} min ({update_interval_sec}s)")

    counter = 1
    while True:
        # 每秒都嘗試更新價格
        asyncio.create_task(update_screener_prices_fast())
        
        # 定期執行完整分析
        if counter % update_interval_sec == 0:
            asyncio.create_task(run_screener_analysis())
            counter = 0 # Reset counter to prevent overflow
        
        counter += 1
        await asyncio.sleep(1)
