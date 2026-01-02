import os
import sys
import json
import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import uvicorn
from dotenv import load_dotenv

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("API")

# 將專案根目錄加入 Python 路徑
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 嘗試導入，若失敗則記錄錯誤
try:
    from interfaces.chat_interface import CryptoAnalysisBot
    from analysis.crypto_screener import screen_top_cryptos
    from core.config import (
        SUPPORTED_EXCHANGES, DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT,
        SCREENER_TARGET_SYMBOLS, SCREENER_UPDATE_INTERVAL_MINUTES
    )
    from core.database import add_to_watchlist, remove_from_watchlist, get_watchlist, get_cache, set_cache
    from data.market_data import get_klines
    from trading.okx_api_connector import OKXAPIConnector
except ImportError as e:
    logger.critical(f"無法導入核心模組: {e}")
    sys.exit(1)

load_dotenv()

# 初始化 OKX 連接器
try:
    okx_connector = OKXAPIConnector()
    logger.info("OKX Connector 初始化成功")
except Exception as e:
    logger.error(f"OKX Connector 初始化失敗: {e}")
    okx_connector = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 嘗試載入快取
    load_screener_cache()
    load_market_pulse_cache()
    load_funding_rate_cache()

    # Startup: 啟動背景篩選器更新任務
    asyncio.create_task(update_screener_task())
    # Startup: 啟動 Market Pulse 定期更新任務
    asyncio.create_task(update_market_pulse_task())
    # Startup: 啟動 Funding Rate 定期更新任務
    asyncio.create_task(funding_rate_update_task())
    yield
    # Shutdown logic can go here if needed

app = FastAPI(title="Crypto Trading System API", version="1.1.0", lifespan=lifespan)

# --- 全域快取 (Screener) ---
# 用於儲存市場掃描結果，避免每次請求都重新運算
cached_screener_result = {
    "timestamp": None,
    "data": None
}

# --- 全域快取 (Market Pulse) ---
# 用於儲存市場脈動 AI 分析結果
MARKET_PULSE_CACHE = {}
# 固定監控的幣種列表
MARKET_PULSE_TARGETS = ["BTC", "ETH", "SOL", "PI"]
# 更新頻率 (秒)
MARKET_PULSE_UPDATE_INTERVAL = 3600  # 1小時

# --- 全域快取 (Funding Rate) ---
FUNDING_RATE_CACHE = {
    "timestamp": None,
    "data": {}
}
FUNDING_RATE_UPDATE_INTERVAL = 300  # 5分鐘更新一次

# Locks for concurrency control
screener_lock = asyncio.Lock()
funding_rate_lock = asyncio.Lock()
symbol_locks = {} # {symbol: asyncio.Lock()}

def get_symbol_lock(symbol: str) -> asyncio.Lock:
    if symbol not in symbol_locks:
        symbol_locks[symbol] = asyncio.Lock()
    return symbol_locks[symbol]

def save_market_pulse_cache():
    """Save Market Pulse data to DB."""
    try:
        set_cache("MARKET_PULSE", MARKET_PULSE_CACHE)
        logger.info(f"Market Pulse cache saved to DB")
    except Exception as e:
        logger.error(f"Failed to save Market Pulse cache: {e}")

def load_market_pulse_cache():
    """Load Market Pulse data from DB."""
    global MARKET_PULSE_CACHE
    try:
        data = get_cache("MARKET_PULSE")
        if data:
            MARKET_PULSE_CACHE = data
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
    global FUNDING_RATE_CACHE
    try:
        data = get_cache("FUNDING_RATE")
        if data:
            FUNDING_RATE_CACHE = data
            logger.info(f"Loaded Funding Rate cache from DB ({len(FUNDING_RATE_CACHE.get('data', {}))} symbols)")
    except Exception as e:
        logger.error(f"Failed to load Funding Rate cache: {e}")

async def update_funding_rates():
    """Update all funding rates from OKX."""
    from trading.okx_api_connector import OKXAPIConnector

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
    from analysis.market_pulse import get_market_pulse
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

class RefreshPulseRequest(BaseModel):
    symbols: Optional[List[str]] = None

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

@app.post("/api/market-pulse/refresh-all")
async def api_refresh_all_market_pulse(request: RefreshPulseRequest):
    """Trigger a global refresh of specified Market Pulse targets immediately."""
    try:
        timestamp = await refresh_all_market_pulse_data(request.symbols)
        return {"status": "success", "timestamp": timestamp}
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

# --- 安全性強化: CORS ---
# 允許跨域請求，方便前端開發與部署
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://app.minepi.com", # Pi Browser 環境
    "*", # 開發階段允許所有，生產環境請限制
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Bot
try:
    bot = CryptoAnalysisBot()
    logger.info("CryptoAnalysisBot 初始化成功")
except Exception as e:
    logger.error(f"CryptoAnalysisBot 初始化失敗: {e}")
    bot = None

# 定義請求模型
class QueryRequest(BaseModel):
    message: str
    interval: str = DEFAULT_INTERVAL
    limit: int = DEFAULT_KLINES_LIMIT
    manual_selection: Optional[List[str]] = None
    auto_execute: bool = False
    market_type: str = "spot"

class ScreenerRequest(BaseModel):
    exchange: str = SUPPORTED_EXCHANGES[0]
    symbols: Optional[List[str]] = None

class WatchlistRequest(BaseModel):
    user_id: str
    symbol: str

class KlineRequest(BaseModel):
    symbol: str
    exchange: str = SUPPORTED_EXCHANGES[0]
    interval: str = "1d"
    limit: int = 100

class BacktestRequest(BaseModel):
    symbol: str
    signal_type: str = "RSI" # RSI, MACD, MA_CROSS
    interval: str = "1h"


class APIKeySettings(BaseModel):
    api_key: str
    secret_key: str
    passphrase: str

def update_env_file(keys: Dict[str, str]):
    """Helper function to update or append keys to the .env file"""
    env_path = os.path.join(project_root, ".env")
    
    # Read existing lines
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []

    # Prepare new content
    new_lines = []
    updated_keys = set()
    
    for line in lines:
        key_match = False
        for k, v in keys.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated_keys.add(k)
                key_match = True
                break
        if not key_match:
            new_lines.append(line)
    
    # Append new keys that weren't in the file
    if len(new_lines) > 0 and not new_lines[-1].endswith('\n'):
        new_lines.append('\n')
        
    for k, v in keys.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    # Write back
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

@app.post("/api/settings/keys")
async def update_api_keys(settings: APIKeySettings):
    """接收前端傳來的 API Keys，寫入 .env 並熱重載連接器"""
    global okx_connector
    
    try:
        # 1. Update .env file for persistence
        update_env_file({
            "OKX_API_KEY": settings.api_key,
            "OKX_API_SECRET": settings.secret_key,
            "OKX_PASSPHRASE": settings.passphrase
        })
        
        # 2. Update environment variables for current process
        os.environ["OKX_API_KEY"] = settings.api_key
        os.environ["OKX_API_SECRET"] = settings.secret_key
        os.environ["OKX_PASSPHRASE"] = settings.passphrase
        
        # 3. Re-initialize the connector
        from trading.okx_api_connector import OKXAPIConnector
        okx_connector = OKXAPIConnector()
        
        # 4. Verify connection immediately
        if not okx_connector.test_connection():
            return {"success": False, "message": "Keys saved, but connection failed. Please check your inputs."}
            
        logger.info("API Keys updated and connector re-initialized successfully.")
        return {"success": True, "message": "API Keys 設定成功且連線正常！"}
        
    except Exception as e:
        logger.error(f"Failed to update API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 背景任務 ---

async def update_screener_prices_fast():
    """
    快速更新任務：只更新 cached_screener_result 中的價格資訊。
    不重新計算指標或排名，僅抓取當前最新價格 (Ticker)。
    """
    if cached_screener_result["data"] is None:
        return

    try:
        from data.data_fetcher import get_data_fetcher
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


# --- [正式版支付註解區塊] ---
# 當你要正式上線並收款時，請取消以下代碼的註解，並在 .env 設定 PI_API_KEY
# PI_API_KEY = os.getenv("PI_API_KEY", "你的_PI_API_KEY")
# PI_PLATFORM_API_URL = "https://api.minepi.com/v2"
# 
# class PaymentDTO(BaseModel):
#     paymentId: str
#     txid: Optional[str] = None
#
# @app.post("/api/payment/approve")
# async def approve_payment(data: PaymentDTO):
#     import requests
#     # 告訴 Pi 伺服器你準備好接受這筆訂單了
#     headers = {"Authorization": f"Key {PI_API_KEY}"}
#     resp = requests.post(f"{PI_PLATFORM_API_URL}/payments/{data.paymentId}/approve", headers=headers, json={})
#     return resp.json() if resp.status_code == 200 else {"error": "failed"}
#
# @app.post("/api/payment/complete")
# async def complete_payment(data: PaymentDTO):
#     import requests
#     # 當用戶簽名成功後，最後確認交易
#     headers = {"Authorization": f"Key {PI_API_KEY}"}
#     resp = requests.post(f"{PI_PLATFORM_API_URL}/payments/{data.paymentId}/complete", headers=headers, json={"txid": data.txid})
#     # 在這裡發放你的虛擬商品 (例如：開通 VIP 分析權限)
#     return resp.json() if resp.status_code == 200 else {"error": "failed"}


# --- 工具函數 ---

# 定義一個哨兵物件來標記迭代結束
_STOP_ITERATION_SENTINEL = object()

def _safe_next(iterator):
    """
    安全地獲取下一個項目的輔助函數。
    如果遇到 StopIteration，則返回哨兵物件，而不是拋出異常。
    這避免了 StopIteration 異常在 run_in_executor 的 Future 中傳遞的問題。
    """
    try:
        return next(iterator)
    except StopIteration:
        return _STOP_ITERATION_SENTINEL

async def iterate_in_threadpool(generator):
    """
    將同步生成器包裝在執行緒池中運行，實現真正的異步串流。
    解決長時間分析任務阻塞主執行緒的問題。
    """
    loop = asyncio.get_running_loop()
    iterator = iter(generator)
    while True:
        try:
            # 在默認執行緒池中執行 _safe_next(iterator)
            # 使用 _safe_next 避免 StopIteration 傳遞給 Future
            item = await loop.run_in_executor(None, _safe_next, iterator)
            
            if item is _STOP_ITERATION_SENTINEL:
                break
                
            yield item
        except Exception as e:
            logger.error(f"串流生成錯誤: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            break

# --- API 端點 ---

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "service": "Crypto Trading API"}

@app.post("/api/analyze")
async def analyze_crypto(request: QueryRequest):
    """
    處理分析請求，並以串流 (Streaming) 方式回傳結果。
    使用執行緒池避免阻塞事件循環。
    """
    if not bot:
        raise HTTPException(status_code=503, detail="分析服務尚未就緒")

    logger.info(f"收到分析請求: {request.message[:50]}... (Interval: {request.interval})")

    async def event_generator():
        try:
            # 使用 iterate_in_threadpool 將同步生成器轉為異步
            async for part in iterate_in_threadpool(
                bot.process_message(
                    request.message, 
                    request.interval, 
                    request.limit, 
                    request.manual_selection,
                    request.auto_execute,
                    request.market_type
                )
            ):
                # 包裝成 JSON 格式發送給前端
                yield f"data: {json.dumps({'content': part})}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"分析過程發生未預期錯誤: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'Internal Server Error'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat/clear")
async def clear_chat_history():
    """清除對話歷史"""
    if bot:
        bot.clear_history()
    return {"status": "success", "message": "Chat history cleared"}

@app.get("/api/config")
async def get_config():
    """回傳前端需要的配置資訊"""
    return {
        "supported_exchanges": SUPPORTED_EXCHANGES,
        "default_interval": DEFAULT_INTERVAL,
        "default_limit": DEFAULT_KLINES_LIMIT
    }

@app.get("/api/market/symbols")
async def get_market_symbols(exchange: str = "binance"):
    """Get all available symbols for a given exchange."""
    logger.info(f"Requesting symbol list for exchange: {exchange}")
    try:
        from data.data_fetcher import get_data_fetcher
        fetcher = get_data_fetcher(exchange)
        symbols = fetcher.get_all_symbols()
        logger.info(f"Successfully fetched {len(symbols)} symbols from {exchange}")
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"Failed to fetch symbols from {exchange}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/screener")
async def run_screener(request: ScreenerRequest):
    """回傳市場篩選數據 (優先使用快取，並支援等待背景任務)"""
    
    # 1. 自定義請求：直接執行
    if request.symbols and len(request.symbols) > 0:
        logger.info(f"執行自定義市場篩選: {request.exchange}, Symbols: {len(request.symbols)}")
        try:
             loop = asyncio.get_running_loop()
             summary_df, top_performers, oversold, overbought = await loop.run_in_executor(
                None, 
                lambda: screen_top_cryptos(
                    exchange=request.exchange, 
                    limit=len(request.symbols), 
                    interval="1d",
                    target_symbols=request.symbols
                )
            )
             # ... formatting ...
             rename_map = {
                "Current Price": "Close", 
                "24h Change %": "price_change_24h", 
                "7d Change %": "price_change_7d", "Signals": "signals"
            }
             top_performers = top_performers.rename(columns=rename_map).replace({np.nan: None})
             oversold = oversold.rename(columns=rename_map).replace({np.nan: None})
             overbought = overbought.rename(columns=rename_map).replace({np.nan: None})
             return {
                "top_performers": top_performers.to_dict(orient="records"),
                "oversold": oversold.to_dict(orient="records"),
                "overbought": overbought.to_dict(orient="records"),
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
             logger.error(f"自定義篩選失敗: {e}", exc_info=True)
             raise HTTPException(status_code=500, detail=str(e))

    # 2. 檢查快取
    if cached_screener_result["data"] is not None:
        return cached_screener_result["data"]
    
    # 3. 若快取為空，檢查是否背景任務正在運行
    if screener_lock.locked():
        logger.info("Cache empty, waiting for background analysis to complete...")
        async with screener_lock:
             # 等待鎖釋放後，再次檢查快取
             if cached_screener_result["data"] is not None:
                 return cached_screener_result["data"]

    # 4. 若等待後仍無數據（極少見），或未鎖定，則執行同步更新 (Double-check Locking)
    # 使用鎖防止多個請求同時觸發
    async with screener_lock:
        if cached_screener_result["data"] is not None:
            return cached_screener_result["data"]
            
        logger.info(f"無快取且無背景任務，執行即時市場篩選: {request.exchange}")
        try:
            loop = asyncio.get_running_loop()
            summary_df, top_performers, oversold, overbought = await loop.run_in_executor(
                None, 
                lambda: screen_top_cryptos(
                    exchange=request.exchange, 
                    limit=10, 
                    interval="1d",
                    target_symbols=None
                )
            )
            # ... formatting ...
            rename_map = {
                "Current Price": "Close", "24h Change %": "price_change_24h", 
                "7d Change %": "price_change_7d", "Signals": "signals"
            }
            top_performers = top_performers.rename(columns=rename_map).replace({np.nan: None})
            oversold = oversold.rename(columns=rename_map).replace({np.nan: None})
            overbought = overbought.rename(columns=rename_map).replace({np.nan: None})
            
            timestamp_str = datetime.now().isoformat()
            result_data = {
                "top_performers": top_performers.to_dict(orient="records"),
                "oversold": oversold.to_dict(orient="records"),
                "overbought": overbought.to_dict(orient="records"),
                "last_updated": timestamp_str
            }
            
            cached_screener_result["timestamp"] = timestamp_str
            cached_screener_result["data"] = result_data
            save_screener_cache(cached_screener_result)
            return result_data
        except Exception as e:
            logger.error(f"篩選器錯誤: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

# --- 自選清單 API ---

@app.get("/api/watchlist/{user_id}")
async def get_user_watchlist(user_id: str):
    """獲取用戶的自選清單"""
    try:
        symbols = get_watchlist(user_id)
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"獲取自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="無法獲取自選清單")

@app.post("/api/watchlist/add")
async def add_watchlist(request: WatchlistRequest):
    """新增幣種到自選清單"""
    try:
        add_to_watchlist(request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已加入自選清單"}
    except Exception as e:
        logger.error(f"新增自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="新增失敗")

@app.post("/api/watchlist/remove")
async def remove_watchlist(request: WatchlistRequest):
    """從自選清單移除幣種"""
    try:
        remove_from_watchlist(request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已從自選清單移除"}
    except Exception as e:
        logger.error(f"移除自選清單失敗: {e}")
        raise HTTPException(status_code=500, detail="移除失敗")

# --- K 線數據 API (給圖表使用) ---

@app.post("/api/klines")
async def get_klines_data(request: KlineRequest):
    """獲取 K 線數據供圖表顯示"""
    try:
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(
            None,
            lambda: get_klines(
                symbol=request.symbol,
                exchange=request.exchange,
                interval=request.interval,
                limit=request.limit
            )
        )

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"找不到 {request.symbol} 的數據")

        klines = []
        for _, row in df.iterrows():
            klines.append({
                "time": int(row['timestamp'].timestamp()) if hasattr(row['timestamp'], 'timestamp') else int(row['timestamp'] / 1000),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close'])
            })

        return {
            "symbol": request.symbol,
            "interval": request.interval,
            "klines": klines
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 K 線數據失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- 資金費率 (Funding Rate) API ---

@app.get("/api/funding-rates")
async def get_funding_rates(refresh: bool = False):
    """
    獲取所有幣種的資金費率。
    資金費率為正表示多頭付給空頭（市場看多），負值表示空頭付給多頭（市場看空）。
    """
    try:
        # 如果要求刷新或快取為空，則更新
        if refresh or not FUNDING_RATE_CACHE.get("data"):
            await update_funding_rates()

        data = FUNDING_RATE_CACHE.get("data", {})
        timestamp = FUNDING_RATE_CACHE.get("timestamp")

        # 計算極端值統計
        rates = [(sym, info.get("fundingRate", 0)) for sym, info in data.items()]
        sorted_by_rate = sorted(rates, key=lambda x: x[1], reverse=True)

        # 前5個最高（多頭擁擠）
        top_bullish = sorted_by_rate[:5]
        # 後5個最低（空頭擁擠）
        top_bearish = sorted_by_rate[-5:][::-1]

        return {
            "timestamp": timestamp,
            "total_count": len(data),
            "data": data,
            "top_bullish": [{"symbol": s, "fundingRate": r} for s, r in top_bullish],
            "top_bearish": [{"symbol": s, "fundingRate": r} for s, r in top_bearish]
        }
    except Exception as e:
        logger.error(f"獲取資金費率失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/funding-rate/{symbol}")
async def get_single_funding_rate(symbol: str):
    """獲取單個幣種的資金費率"""
    try:
        base_symbol = symbol.upper().replace("USDT", "").replace("-SWAP", "").replace("-", "")

        # 先檢查快取
        if FUNDING_RATE_CACHE.get("data") and base_symbol in FUNDING_RATE_CACHE["data"]:
            return FUNDING_RATE_CACHE["data"][base_symbol]

        # 快取中沒有，直接查詢
        from trading.okx_api_connector import OKXAPIConnector
        okx = OKXAPIConnector()
        instId = f"{base_symbol}-USDT-SWAP"
        result = okx.get_funding_rate(instId)

        if result.get("code") == "0" and result.get("data"):
            data = result["data"][0]
            return {
                "symbol": base_symbol,
                "instId": instId,
                "fundingRate": float(data.get("fundingRate", 0)) * 100,
                "nextFundingRate": float(data.get("nextFundingRate", 0)) * 100 if data.get("nextFundingRate") else None,
                "fundingTime": data.get("fundingTime"),
                "nextFundingTime": data.get("nextFundingTime")
            }
        return {"error": "Not found"}
    except Exception as e:
        logger.error(f"Error fetching single funding rate: {e}")
        return {"error": str(e)}

@app.get("/api/funding-rate-history/{symbol}")
async def get_funding_rate_history(symbol: str):
    """獲取資金費率歷史數據"""
    try:
        # Normalize symbol (e.g. BTC -> BTC-USDT-SWAP)
        base = symbol.upper().replace("-USDT", "").replace("-SWAP", "").replace("USDT", "")
        instId = f"{base}-USDT-SWAP"
        
        logger.info(f"[History] Fetching for symbol: {symbol} -> instId: {instId}")

        from trading.okx_api_connector import OKXAPIConnector
        okx = OKXAPIConnector()
        
        # Get the running event loop
        loop = asyncio.get_running_loop()
        
        # Use run_in_executor to avoid blocking event loop
        result = await loop.run_in_executor(None, okx.get_funding_rate_history, instId)
        
        if result.get("code") == "0" and result.get("data"):
            history = []
            for item in result["data"]:
                history.append({
                    "time": item["fundingTime"],
                    "rate": float(item["fundingRate"]) * 100, # Convert to percentage
                    "realRate": float(item["realizedRate"]) * 100 if "realizedRate" in item else float(item["fundingRate"]) * 100
                })
            # OKX returns newest first, reverse to show chronological order
            return {"data": history[::-1], "symbol": base}
        
        return {"error": "Failed to fetch history", "details": result}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return {"error": str(e)}

# --- 市場脈動 (Smart Attribution) API ---

@app.get("/api/market-pulse/{symbol}")
async def get_market_pulse_api(symbol: str, sources: Optional[str] = None, refresh: bool = False):
    """
    獲取市場脈動分析。
    使用 Symbol Lock 避免同一時間對同一幣種進行重複的即時分析。
    refresh=true 可強制刷新數據。
    """
    try:
        from analysis.market_pulse import get_market_pulse

        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")

        # 1. 優先檢查快取 (除非要求強制刷新)
        if not refresh and base_symbol in MARKET_PULSE_CACHE:
            return MARKET_PULSE_CACHE[base_symbol]

        # 2. 快取未命中，使用鎖進行同步控制
        lock = get_symbol_lock(base_symbol)
        
        async with lock:
            # Double check cache inside lock
            if base_symbol in MARKET_PULSE_CACHE:
                 return MARKET_PULSE_CACHE[base_symbol]

            logger.info(f"Cache miss for {base_symbol}, triggering immediate analysis...")
            
            loop = asyncio.get_running_loop()
            enabled_sources = sources.split(',') if sources else None
            
            result = await loop.run_in_executor(None, lambda: get_market_pulse(base_symbol, enabled_sources=enabled_sources))
            
            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])
                
            MARKET_PULSE_CACHE[base_symbol] = result
            save_market_pulse_cache()
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"市場脈動分析失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- AI 辯論視覺化 (Visualized Debate) API ---
# ... (保留原樣)
@app.get("/api/debate/{symbol}")
async def get_debate_analysis(symbol: str):
    """
    獲取 AI 辯論詳情 (用於前端視覺化顯示)。
    執行完整的 ReAct Agent 流程，但只回傳辯論相關的結構化數據。
    """
    try:
        from core.graph import app as graph_app
        from core.tools import _find_available_exchange

        # 1. 準備參數
        clean_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        exchange, normalized_symbol = _find_available_exchange(clean_symbol)
        
        if not exchange:
            raise HTTPException(status_code=404, detail=f"找不到交易對 {clean_symbol}")

        state_input = {
            "symbol": normalized_symbol,
            "exchange": exchange,
            "interval": "1d",
            "limit": 100,
            "market_type": "spot",
            "leverage": 1,
            "include_multi_timeframe": True,
            "short_term_interval": "1h",
            "medium_term_interval": "4h",
            "long_term_interval": "1d",
            "preloaded_data": None,
            "account_balance": None,
            "selected_analysts": ["technical", "sentiment", "fundamental", "news"],
            "perform_trading_decision": True
        }

        logger.info(f"開始執行 AI 辯論分析: {normalized_symbol}")

        # 2. 執行圖 (放入執行緒池)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: graph_app.invoke(state_input))
        
        # 3. 提取辯論數據
        # 注意: result 中的物件是 Pydantic Model，FastAPI 可以自動序列化，但為了保險起見，我們先轉 dict
        response_data = {
            "symbol": normalized_symbol,
            "bull_argument": result.get("bull_argument"),
            "bear_argument": result.get("bear_argument"),
            "neutral_argument": result.get("neutral_argument"),
            "debate_judgment": result.get("debate_judgment"),
            "final_decision": result.get("final_approval")
        }
        
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 辯論分析失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- 帳戶資產與持倉 API ---

@app.get("/api/account/assets")
async def get_account_assets():
    """獲取帳戶資產餘額"""
    if not okx_connector:
        raise HTTPException(status_code=503, detail="交易連接器尚未就緒")
    
    try:
        # 獲取帳戶餘額 (預設 USDT，也可以不傳參數獲取所有)
        # 這裡我們不傳 ccy 以獲取所有非零餘額
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: okx_connector.get_account_balance(ccy=None))
        
        if result.get("code") != "0":
             # 嘗試獲取更多錯誤細節
             msg = result.get("msg", "Unknown error")
             logger.error(f"獲取資產失敗: {msg}")
             raise HTTPException(status_code=500, detail=f"Exchange Error: {msg}")
             
        # 整理數據格式給前端
        data = result.get("data", [])
        if not data:
            return {"total_equity": 0, "details": []}
            
        account_data = data[0]
        total_equity = float(account_data.get("totalEq", 0))
        details = []
        
        for bal in account_data.get("details", []):
            if float(bal.get("eq", 0)) > 0: # 只顯示有餘額的幣種
                details.append({
                    "currency": bal.get("ccy"),
                    "balance": float(bal.get("eq")),
                    "available": float(bal.get("availBal")),
                    "frozen": float(bal.get("frozenBal")),
                    "usd_value": float(bal.get("eqUsd", 0))
                })
        
        # 按美元價值排序
        details.sort(key=lambda x: x["usd_value"], reverse=True)
        
        return {
            "total_equity": total_equity,
            "update_time": datetime.fromtimestamp(int(account_data.get("uTime", 0))/1000).isoformat(),
            "details": details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取帳戶資產失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/account/positions")
async def get_account_positions():
    """獲取當前持倉 (包含現貨與合約)"""
    if not okx_connector:
        raise HTTPException(status_code=503, detail="交易連接器尚未就緒")
        
    try:
        loop = asyncio.get_running_loop()
        # 獲取所有持倉
        result = await loop.run_in_executor(None, lambda: okx_connector.get_positions("ANY"))
        
        if result.get("code") != "0":
             msg = result.get("msg", "Unknown error")
             raise HTTPException(status_code=500, detail=f"Exchange Error: {msg}")
             
        data = result.get("data", [])
        positions = []
        
        for pos in data:
            # 區分持倉類型
            inst_type = pos.get("instType")
            side = pos.get("posSide") # long, short, net
            
            # 處理基礎數據
            positions.append({
                "symbol": pos.get("instId"),
                "type": inst_type,
                "side": side,
                "size": float(pos.get("pos")), # 持倉數量
                "avg_price": float(pos.get("avgPx") or 0), # 開倉均價
                "mark_price": float(pos.get("markPx") or 0), # 標記價格
                "pnl": float(pos.get("upl") or 0), # 未實現盈虧
                "pnl_ratio": float(pos.get("uplRatio") or 0) * 100, # 盈虧率 %
                "leverage": float(pos.get("lever") or 1),
                "margin": float(pos.get("margin") or 0),
                "liq_price": float(pos.get("liqPx") or 0) # 強平價格
            })
            
        return {"positions": positions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取持倉失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- 交易執行 API ---

class TradeExecutionRequest(BaseModel):
    symbol: str
    market_type: str # "spot" or "futures"
    side: str # "buy", "sell", "long", "short"
    amount: float # Investment/Margin amount in USDT
    leverage: int = 1
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

@app.post("/api/trade/execute")
async def execute_trade_api(request: TradeExecutionRequest):
    """
    手動確認後執行交易 (Human-in-the-loop)
    """
    try:
        from trading.trade_executor import TradeExecutor
        executor = TradeExecutor()
        
        loop = asyncio.get_running_loop()
        
        if request.market_type == "spot":
            result = await loop.run_in_executor(
                None, 
                lambda: executor.execute_spot(
                    symbol=request.symbol, 
                    side=request.side, 
                    amount_usdt=request.amount
                )
            )
        elif request.market_type == "futures":
            result = await loop.run_in_executor(
                None, 
                lambda: executor.execute_futures(
                    symbol=request.symbol, 
                    side=request.side, 
                    margin_amount=request.amount,
                    leverage=request.leverage,
                    stop_loss=request.stop_loss,
                    take_profit=request.take_profit
                )
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid market type")
            
        if result.get("status") == "failed":
            raise HTTPException(status_code=400, detail=result.get("error"))
            
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"交易執行失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- 回測 (One-Click Backtest) API ---

@app.post("/api/backtest")
async def run_backtest_api(request: BacktestRequest):
    """
    執行快速回測 (One-Click Backtest)。
    驗證特定技術指標策略在過去的表現。
    """
    try:
        from analysis.simple_backtester import run_simple_backtest
        from core.tools import _normalize_symbol
        
        loop = asyncio.get_running_loop()
        
        # 簡單標準化 symbol (假設 OKX 或 Binance 格式)
        # 這裡我們假設 simple_backtester 能處理，或者我們需要先標準化
        # 我們直接傳入用戶輸入的 symbol，讓 backtester 內部的 data_fetcher 去處理
        # 但為了保險，我們可以做一點基本的清理
        clean_symbol = request.symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        # 預設加上 -USDT 給 OKX data fetcher (如果它需要)
        # 根據 analysis/simple_backtester.py 邏輯，它調用 get_data_fetcher("okx")
        # OKX fetcher 通常預期 "BTC-USDT" 格式
        target_symbol = f"{clean_symbol}-USDT"
        
        logger.info(f"開始執行回測: {target_symbol} ({request.signal_type})")
        
        result = await loop.run_in_executor(
            None, 
            lambda: run_simple_backtest(
                symbol=target_symbol,
                signal_type=request.signal_type,
                interval=request.interval,
                limit=1000 # 固定回測過去 1000 根 K 線
            )
        )
        
        if "error" in result:
             raise HTTPException(status_code=400, detail=result["error"])
             
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"回測執行失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- 靜態檔案與頁面 ---

if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/")
async def read_index():
    """返回主頁面 index.html"""
    if os.path.exists("web/index.html"):
        return FileResponse("web/index.html")
    return {"message": "Welcome to Crypto API. Frontend not found."}

if __name__ == "__main__":
    logger.info("🚀 Pi Crypto Insight API Server 啟動中...")
    logger.info(f"🏠 本地網址: http://localhost:8111")
    logger.info("📱 請在 Pi Browser 中使用 HTTPS 網址訪問 (如透過 ngrok)")
    uvicorn.run(app, host="0.0.0.0", port=8111)