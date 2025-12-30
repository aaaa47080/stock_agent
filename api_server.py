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
    from core.database import add_to_watchlist, remove_from_watchlist, get_watchlist
    from data.market_data import get_klines
except ImportError as e:
    logger.critical(f"無法導入核心模組: {e}")
    sys.exit(1)

load_dotenv()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 嘗試載入快取
    load_screener_cache()
    # Startup: 啟動背景篩選器更新任務
    asyncio.create_task(update_screener_task())
    yield
    # Shutdown logic can go here if needed

app = FastAPI(title="Crypto Trading System API", version="1.1.0", lifespan=lifespan)

# --- 全域快取 (Screener) ---
# 用於儲存市場掃描結果，避免每次請求都重新運算
cached_screener_result = {
    "timestamp": None,
    "data": None
}
SCREENER_CACHE_FILE = "analysis_results/screener_cache.json"

def save_screener_cache(data: Dict[str, Any]):
    """Save screener data to a JSON file."""
    try:
        os.makedirs(os.path.dirname(SCREENER_CACHE_FILE), exist_ok=True)
        with open(SCREENER_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Screener cache saved to {SCREENER_CACHE_FILE}")
    except Exception as e:
        logger.error(f"Failed to save screener cache: {e}")

def load_screener_cache():
    """Load screener data from the JSON file."""
    try:
        if os.path.exists(SCREENER_CACHE_FILE):
            with open(SCREENER_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cached_screener_result["timestamp"] = data.get("timestamp")
            cached_screener_result["data"] = data.get("data")
            logger.info(f"Loaded screener cache from {SCREENER_CACHE_FILE} (Timestamp: {data.get('timestamp')})")
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

class PredictionRequest(BaseModel):
    user_id: str
    username: str
    symbol: str
    direction: str # "UP" or "DOWN"

# --- 背景任務 ---

# 使用 Lock 確保不會有重疊的分析任務同時執行
screener_lock = asyncio.Lock()

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

        # 這裡我們假設 fetcher 有一個批量獲取價格的方法，或者我們循環調用
        # 為了效率，我們直接調用 ticker/24hr endpoint (一次請求獲取所有)
        # 注意：get_top_symbols 內部調用了 ticker/24hr 但只返回 symbol list
        # 我們直接用 fetcher 的內部方法 _make_request 比較快，但為了封裝性，我們擴展 fetcher 或直接在這裡做
        # 簡單起見，我們假設數量不多 (10-30個)，可以用個別請求或批量
        
        # 優化：Binance ticker/price?symbol=... 只能一個，或者 ticker/price (全部)
        # 獲取全部 ticker 對服務器負擔小，因為是一次請求
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
                    # 嘗試匹配 (Binance symbol 通常是 BTCUSDT)
                    # 我們的 item["Symbol"] 可能是 BTC/USDT 或 BTCUSDT
                    s = item["Symbol"].replace("/", "").replace("-", "")
                    # 如果是 OKX 來的數據可能是 BTC-USDT，轉為 BTCUSDT 嘗試匹配
                    # 注意：如果 fetcher 是 OKX，這裡邏輯要變。目前假設主要用 Binance 做即時報價
                    
                    if s in price_map:
                        item["Close"] = price_map[s]['price']
                        item["price_change_24h"] = price_map[s]['change']
                        updated = True
        
        if updated:
            # Re-sort top_performers to maintain order based on new price changes
            if data.get("top_performers"):
                data["top_performers"].sort(key=lambda x: float(x.get("price_change_24h", 0)), reverse=True)

            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cached_screener_result["data"]["last_updated"] = timestamp_str
            # 不需要更新 cached_screener_result["timestamp"]，那個留給完整分析的時間
            # 或者我們更新它讓前端知道數據變了
            cached_screener_result["timestamp"] = timestamp_str
            
            # 這裡不存檔，避免頻繁 I/O
            # save_screener_cache(cached_screener_result) 
            
    except Exception as e:
        # 靜默失敗，不要刷屏 log，因為這是高頻任務
        pass

async def run_screener_analysis():
    """執行實際的分析工作並更新快取 (重型任務)"""
    if screener_lock.locked():
        return
        
    async with screener_lock:
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
            
        except Exception as e:
            logger.error(f"❌ [分析任務] 執行失敗: {e}")

async def update_screener_task():
    """
    背景任務：
    1. 每秒執行快速價格更新 (Fast Update)
    2. 每 60 秒執行完整分析 (Heavy Analysis) - 降低頻率以避免 API 封禁
    """
    counter = 0
    while True:
        # 每秒都嘗試更新價格
        asyncio.create_task(update_screener_prices_fast())
        
        # 每 60 秒執行一次完整分析 (或如果剛啟動)
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

async def iterate_in_threadpool(generator):
    """
    將同步生成器包裝在執行緒池中運行，實現真正的異步串流。
    解決長時間分析任務阻塞主執行緒的問題。
    """
    loop = asyncio.get_running_loop()
    iterator = iter(generator)
    while True:
        try:
            # 在默認執行緒池中執行 next(iterator)
            item = await loop.run_in_executor(None, next, iterator)
            yield item
        except StopIteration:
            break
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
                bot.process_message(request.message, request.interval, request.limit, request.manual_selection)
            ):
                # 包裝成 JSON 格式發送給前端
                yield f"data: {json.dumps({'content': part})}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"分析過程發生未預期錯誤: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'Internal Server Error'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
    """回傳市場篩選數據 (優先使用快取)"""
    # 如果有指定 symbols，則**不**使用全域快取，而是直接執行分析
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
             
             rename_map = {
                "Current Price": "Close", 
                "24h Change %": "price_change_24h",
                "7d Change %": "price_change_7d",
                "Signals": "signals"
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

    # 檢查是否有快取數據
    if cached_screener_result["data"] is not None:
        logger.info(f"使用快取篩選數據 (更新時間: {cached_screener_result['timestamp']})")
        return cached_screener_result["data"]
    
    logger.info(f"無快取數據，執行即時市場篩選: {request.exchange}")
    try:
        # 如果剛啟動還沒有快取，則執行一次即時分析 (廣泛掃描)
        
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
        
        # --- 清理數據 ---
        rename_map = {
            "Current Price": "Close", 
            "24h Change %": "price_change_24h",
            "7d Change %": "price_change_7d",
            "Signals": "signals"
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
        
        # 順便更新快取
        cached_screener_result["timestamp"] = timestamp_str
        cached_screener_result["data"] = result_data

        # 持久化快取
        save_screener_cache(cached_screener_result)

        return result_data
    except Exception as e:
        logger.error(f"篩選器錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- 自選清單 API ---

@app.get("/api/watchlist/{user_id}")
async def get_user_watchlist(user_id: str):
    """獲取用戶的自選清單"""
    # TODO: 增加真實的身份驗證 (目前僅依賴路徑參數)
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
        # get_klines 涉及網絡請求，放入執行緒池
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

        # 轉換為 TradingView Lightweight Charts 格式
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

# --- 市場脈動 (Smart Attribution) API ---

@app.get("/api/market-pulse/{symbol}")
async def get_market_pulse_api(symbol: str, sources: Optional[str] = None):
    """
    獲取市場脈動分析：解釋價格波動原因 (Smart Attribution)。
    """
    try:
        from analysis.market_pulse import get_market_pulse
        
        loop = asyncio.get_running_loop()
        # 清理 symbol
        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        
        # 處理新聞來源參數
        enabled_sources = sources.split(',') if sources else None
        
        # 放入執行緒池執行
        result = await loop.run_in_executor(None, lambda: get_market_pulse(base_symbol, enabled_sources=enabled_sources))
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"市場脈動分析失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- AI 辯論視覺化 (Visualized Debate) API ---

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

# --- Pi Network 社交跟單 API ---

@app.post("/api/social/predict")
async def submit_prediction(request: PredictionRequest):
    """
    提交價格預測 (社交互動)。
    """
    try:
        from core.database import submit_prediction
        from core.tools import get_crypto_price_tool
        
        # 1. 獲取當前價格作為進場價
        # 為了簡化，這裡我們假設工具能返回價格，或者我們直接用 fetcher
        from data.data_fetcher import get_data_fetcher
        clean_symbol = request.symbol.upper().replace("USDT", "").replace("-", "")
        fetcher = get_data_fetcher("okx") # 默認
        klines = fetcher.get_historical_klines(f"{clean_symbol}-USDT", "1m", limit=1)
        
        if klines is None or klines.empty:
            raise HTTPException(status_code=400, detail="無法獲取當前價格")
            
        current_price = float(klines.iloc[-1]['Close'])
        
        # 2. 寫入資料庫
        submit_prediction(
            request.user_id, 
            request.username, 
            clean_symbol, 
            request.direction, 
            current_price
        )
        
        return {"success": True, "message": "預測已提交！", "entry_price": current_price}
        
    except Exception as e:
        logger.error(f"預測提交失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/social/leaderboard")
async def get_leaderboard_api():
    """
    獲取預測排行榜。
    """
    try:
        from core.database import get_leaderboard
        leaderboard = get_leaderboard(limit=10)
        return {"leaderboard": leaderboard}
    except Exception as e:
        logger.error(f"獲取排行榜失敗: {e}", exc_info=True)
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
    logger.info(f"🏠 本地網址: http://localhost:8000")
    logger.info("📱 請在 Pi Browser 中使用 HTTPS 網址訪問 (如透過 ngrok)")
    uvicorn.run(app, host="0.0.0.0", port=8111)