import asyncio
import json
from typing import Optional, Set
from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect

from core.config import SUPPORTED_EXCHANGES
from data.market_data import get_klines
from trading.okx_api_connector import OKXAPIConnector
from api.models import KlineRequest, ScreenerRequest, RefreshPulseRequest
from api.utils import logger
from api.globals import (
    cached_screener_result,
    FUNDING_RATE_CACHE,
    MARKET_PULSE_CACHE,
    screener_lock,
    get_symbol_lock,
    ANALYSIS_STATUS
)
from api.services import (
    save_market_pulse_cache,
    update_funding_rates,
    refresh_all_market_pulse_data
)
from analysis.crypto_screener import screen_top_cryptos
from analysis.market_pulse import get_market_pulse
import numpy as np
from datetime import datetime

from api.routers.admin import verify_admin_key
from fastapi import Depends

router = APIRouter()

# In-memory cache for static symbol lists
SYMBOL_CACHE = {
    "okx": {"data": None, "timestamp": 0}
}

@router.get("/api/market/symbols")
async def get_market_symbols(exchange: str = "okx"):
    """Get all available symbols for a given exchange (Cached for 60 minutes)."""
    # Check cache
    now = datetime.now().timestamp()
    if exchange in SYMBOL_CACHE:
         cache = SYMBOL_CACHE[exchange]
         if cache["data"] and (now - cache["timestamp"]) < 3600:
             return {"symbols": cache["data"]}

    logger.info(f"Requesting symbol list for exchange: {exchange}")
    try:
        loop = asyncio.get_running_loop()
        from data.data_fetcher import get_data_fetcher
        
        def fetch_task():
            fetcher = get_data_fetcher(exchange)
            return fetcher.get_all_symbols()

        symbols = await loop.run_in_executor(None, fetch_task)
        
        # Update cache
        SYMBOL_CACHE[exchange] = {
            "data": symbols,
            "timestamp": now
        }
        
        logger.info(f"Successfully fetched {len(symbols)} symbols from {exchange}")
        return {"symbols": symbols}
    except Exception as e:
        logger.error(f"Failed to fetch symbols from {exchange}: {e}")
        # Return stale cache if available when error occurs
        if exchange in SYMBOL_CACHE and SYMBOL_CACHE[exchange]["data"]:
             logger.warning("Returning stale cache due to error.")
             return {"symbols": SYMBOL_CACHE[exchange]["data"]}
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/screener")
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
    if not request.refresh and cached_screener_result["data"] is not None:
        return cached_screener_result["data"]
    
    # 3. 若快取為空或強制刷新，檢查是否背景任務正在運行
    if screener_lock.locked():
        # 如果是強制刷新，我們還是得等
        logger.info(f"Cache miss/refresh (locked), waiting for background analysis... (Request refresh: {request.refresh})")
        async with screener_lock:
             # 等待鎖釋放後，再次檢查快取
             # 如果是強制刷新，且剛跑完的數據很新 (e.g. < 5秒)，或許可以用？ 
             # 但簡單起見，如果鎖釋放了，通常代表有新數據，直接返回即可
             if cached_screener_result["data"] is not None:
                 return cached_screener_result["data"]

    # 4. 若等待後仍無數據，或未鎖定，則執行同步更新 (Double-check Locking)
    # 使用鎖防止多個請求同時觸發
    async with screener_lock:
        # Double check: 如果是並發請求，前一個可能已經更新了
        if not request.refresh and cached_screener_result["data"] is not None:
            return cached_screener_result["data"]
            
        logger.info(f"無快取且無背景任務，執行即時市場篩選: {request.exchange}")
        try:
            loop = asyncio.get_running_loop()
            summary_df, top_performers, oversold, overbought = await loop.run_in_executor(
                None, 
                lambda: screen_top_cryptos(
                    exchange=request.exchange, 
                    limit=50, # [Optimization] Consistent 50 limit for fallback
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
            
            # [Optimization] RAM Only - No DB write
            logger.info("Manual screener refresh complete (RAM updated).")
            return result_data
        except Exception as e:
            logger.error(f"篩選器錯誤: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/klines")
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
            kline_data = {
                "time": int(row['timestamp'].timestamp()) if hasattr(row['timestamp'], 'timestamp') else int(row['timestamp'] / 1000),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close'])
            }
            if 'volume' in row.index and row['volume'] is not None:
                kline_data["volume"] = float(row['volume'])
            klines.append(kline_data)

        from datetime import datetime
        return {
            "symbol": request.symbol,
            "interval": request.interval,
            "klines": klines,
            "updated_at": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取 K 線數據失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/funding-rates")
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

@router.get("/api/funding-rate/{symbol}")
async def get_single_funding_rate(symbol: str):
    """獲取單個幣種的資金費率"""
    try:
        base_symbol = symbol.upper().replace("USDT", "").replace("-SWAP", "").replace("-", "")

        # 先檢查快取
        if FUNDING_RATE_CACHE.get("data") and base_symbol in FUNDING_RATE_CACHE["data"]:
            return FUNDING_RATE_CACHE["data"][base_symbol]

        # 快取中沒有，直接查詢
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

@router.get("/api/funding-rate-history/{symbol}")
async def get_funding_rate_history(symbol: str):
    """獲取資金費率歷史數據"""
    try:
        # Normalize symbol (e.g. BTC -> BTC-USDT-SWAP)
        base = symbol.upper().replace("-USDT", "").replace("-SWAP", "").replace("USDT", "")
        instId = f"{base}-USDT-SWAP"
        
        logger.info(f"[History] Fetching for symbol: {symbol} -> instId: {instId}")

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

@router.get("/api/market-pulse/{symbol}")
async def get_market_pulse_api(
    symbol: str,
    sources: Optional[str] = None,
    refresh: bool = False,
    deep_analysis: bool = False,
    x_user_llm_key: Optional[str] = Header(None),
    x_user_llm_provider: Optional[str] = Header(None)
):
    """
    獲取市場脈動分析

    分層設計：
    - 預設模式：讀取公共快取（後台已分析好的數據）
    - 深度分析模式：deep_analysis=true + 私人金鑰 → 即時使用用戶 API Key 分析
    """
    try:
        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")

        # 1. 優先讀取公共快取（除非用戶明確要求深度分析）
        if not deep_analysis and base_symbol in MARKET_PULSE_CACHE:
            cached_data = MARKET_PULSE_CACHE[base_symbol].copy()  # 返回副本，避免修改原始快取
            cached_data["source_mode"] = "public_cache"  # 標記數據來源
            return cached_data

        # 2. 深度分析模式：用戶選擇使用私人金鑰即時分析
        if deep_analysis and x_user_llm_key and x_user_llm_provider:
            try:
                from utils.llm_client import create_llm_client_from_config
                from analysis.market_pulse import MarketPulseAnalyzer

                logger.info(f"🔬 Deep Analysis Mode: Using User Key for {base_symbol}")
                user_client, _ = create_llm_client_from_config({
                    "provider": x_user_llm_provider,
                    "api_key": x_user_llm_key
                })

                analyzer = MarketPulseAnalyzer(client=user_client)
                loop = asyncio.get_running_loop()
                enabled_sources = sources.split(',') if sources else None

                result = await loop.run_in_executor(None, lambda: analyzer.analyze_movement(base_symbol, enabled_sources=enabled_sources))

                # 深度分析結果也更新到公共快取，讓其他人也受益
                if result and "error" not in result:
                    result["source_mode"] = "deep_analysis"  # 標記為深度分析
                    result["analyzed_by"] = x_user_llm_provider  # 記錄分析來源
                    MARKET_PULSE_CACHE[base_symbol] = result
                    await loop.run_in_executor(None, save_market_pulse_cache)
                return result
            except Exception as e:
                logger.error(f"Deep analysis failed: {e}")
                # 深度分析失敗時，回退到快取
                if base_symbol in MARKET_PULSE_CACHE:
                    return MARKET_PULSE_CACHE[base_symbol]

        # 3. 快取未命中：立即執行按需分析 (On-Demand Analysis)
        logger.info(f"Cache miss for {base_symbol}, triggering immediate analysis...")
        
        try:
            from analysis.market_pulse import get_market_pulse
            
            # 使用預設來源
            enabled_sources = sources.split(',') if sources else None
            loop = asyncio.get_running_loop()
            
            # 立即執行分析
            result = await loop.run_in_executor(None, lambda: get_market_pulse(base_symbol, enabled_sources=enabled_sources))
            
            if result and "error" not in result:
                # 成功後寫入快取，造福後續請求
                result["source_mode"] = "on_demand"
                MARKET_PULSE_CACHE[base_symbol] = result
                # 異步保存到檔案，不阻塞
                asyncio.create_task(asyncio.to_thread(save_market_pulse_cache))
                return result
            else:
                # 分析失敗的 fallback
                logger.warning(f"On-demand analysis failed for {base_symbol}: {result.get('error')}")
                # 繼續向下執行，返回 pending 狀態
                
        except Exception as e:
            logger.error(f"Error during on-demand analysis for {base_symbol}: {e}")

        return {
            "symbol": base_symbol,
            "status": "pending",
            "source_mode": "awaiting_update",
            "message": "分析中，請稍候再試",
            "current_price": 0,
            "change_24h": 0,
            "change_1h": 0,
            "report": {
                "summary": "系統正在為此幣種生成初始報告，請稍後刷新頁面。",
                "key_points": [],
                "highlights": [],
                "risks": []
            }
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"市場脈動分析失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/market-pulse/refresh-all", dependencies=[Depends(verify_admin_key)])
async def api_refresh_all_market_pulse(request: RefreshPulseRequest):
    """Trigger a global refresh of specified Market Pulse targets immediately."""
    try:
        timestamp = await refresh_all_market_pulse_data(request.symbols)
        return {"status": "success", "timestamp": timestamp}
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/market-pulse/progress")
async def get_market_pulse_progress():
    """Get the current status of background analysis task."""
    return ANALYSIS_STATUS


# ========================================
# WebSocket 即時 K 線數據
# ========================================

# 管理所有連接的 WebSocket 客戶端
class KlineConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: dict = {}  # websocket -> {symbol, interval}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 客戶端連接，當前連接數: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"WebSocket 客戶端斷開，當前連接數: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, symbol: str, interval: str):
        self.subscriptions[websocket] = {"symbol": symbol, "interval": interval}
        logger.info(f"客戶端訂閱: {symbol} {interval}")

    def unsubscribe(self, websocket: WebSocket):
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    async def broadcast_kline(self, symbol: str, interval: str, kline: dict):
        """向訂閱特定幣種/週期的客戶端廣播 K 線數據"""
        for ws, sub in list(self.subscriptions.items()):
            if sub["symbol"].upper() == symbol.upper() and sub["interval"] == interval:
                try:
                    await ws.send_json({
                        "type": "kline",
                        "symbol": symbol,
                        "interval": interval,
                        "data": kline
                    })
                except Exception as e:
                    logger.error(f"廣播失敗: {e}")

kline_manager = KlineConnectionManager()

# OKX WebSocket 管理器
okx_ws_started = False

async def start_okx_websocket():
    """啟動 OKX WebSocket 連接"""
    global okx_ws_started
    if okx_ws_started:
        return

    try:
        from data.okx_websocket import okx_ws_manager
        okx_ws_started = True
        await okx_ws_manager.start()
    except ImportError as e:
        logger.error(f"無法導入 OKX WebSocket 模組: {e}")
    except Exception as e:
        logger.error(f"啟動 OKX WebSocket 失敗: {e}")

@router.websocket("/ws/klines")
async def websocket_klines(websocket: WebSocket):
    """
    WebSocket 端點，用於即時 K 線數據推送

    客戶端訂閱格式:
    {"action": "subscribe", "symbol": "BTC", "interval": "1m"}
    {"action": "unsubscribe"}
    """
    await kline_manager.connect(websocket)

    try:
        from data.okx_websocket import okx_ws_manager

        # 確保 OKX WebSocket 已啟動
        asyncio.create_task(start_okx_websocket())

        current_subscription = None

        async def on_kline_update(symbol: str, interval: str, kline: dict):
            """收到 OKX K 線更新時的回調"""
            try:
                await websocket.send_json({
                    "type": "kline",
                    "symbol": symbol,
                    "interval": interval,
                    "data": kline
                })
            except Exception:
                pass

        while True:
            try:
                # 接收客戶端消息
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "subscribe":
                    symbol = message.get("symbol", "BTC").upper()
                    interval = message.get("interval", "1m")

                    # 取消之前的訂閱
                    if current_subscription:
                        old_symbol, old_interval = current_subscription
                        await okx_ws_manager.unsubscribe(old_symbol, old_interval, on_kline_update)

                    # 新訂閱
                    kline_manager.subscribe(websocket, symbol, interval)
                    await okx_ws_manager.subscribe(symbol, interval, on_kline_update)
                    current_subscription = (symbol, interval)

                    await websocket.send_json({
                        "type": "subscribed",
                        "symbol": symbol,
                        "interval": interval
                    })

                elif action == "unsubscribe":
                    if current_subscription:
                        old_symbol, old_interval = current_subscription
                        await okx_ws_manager.unsubscribe(old_symbol, old_interval, on_kline_update)
                        current_subscription = None

                    kline_manager.unsubscribe(websocket)
                    await websocket.send_json({"type": "unsubscribed"})

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info("WebSocket 客戶端主動斷開")
    except Exception as e:
        logger.error(f"WebSocket 錯誤: {e}")
    finally:
        # 清理訂閱
        if current_subscription:
            try:
                from data.okx_websocket import okx_ws_manager
                old_symbol, old_interval = current_subscription
                await okx_ws_manager.unsubscribe(old_symbol, old_interval)
            except:
                pass
        kline_manager.disconnect(websocket)


# ========================================
# WebSocket 即時 Ticker 數據 (Market Watch)
# ========================================

class TickerConnectionManager:
    """管理 Ticker WebSocket 連接"""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscribed_symbols: dict = {}  # websocket -> set of symbols

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscribed_symbols[websocket] = set()
        logger.info(f"Ticker WebSocket 客戶端連接，當前連接數: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if websocket in self.subscribed_symbols:
            del self.subscribed_symbols[websocket]
        logger.info(f"Ticker WebSocket 客戶端斷開，當前連接數: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, symbols: list):
        if websocket not in self.subscribed_symbols:
            self.subscribed_symbols[websocket] = set()
        self.subscribed_symbols[websocket].update(symbols)

    def unsubscribe(self, websocket: WebSocket, symbols: list = None):
        if websocket in self.subscribed_symbols:
            if symbols:
                self.subscribed_symbols[websocket] -= set(symbols)
            else:
                self.subscribed_symbols[websocket].clear()

ticker_manager = TickerConnectionManager()

# OKX Ticker WebSocket 狀態
okx_ticker_ws_started = False

async def start_okx_ticker_websocket():
    """啟動 OKX Ticker WebSocket 連接"""
    global okx_ticker_ws_started
    if okx_ticker_ws_started:
        logger.info("OKX Ticker WebSocket 已在運行中")
        return

    try:
        from data.okx_websocket import okx_ticker_ws_manager
        logger.info("正在啟動 OKX Ticker WebSocket...")
        okx_ticker_ws_started = True
        await okx_ticker_ws_manager.start()
        logger.info("OKX Ticker WebSocket 啟動任務已創建")
    except ImportError as e:
        logger.error(f"無法導入 OKX Ticker WebSocket 模組: {e}")
        okx_ticker_ws_started = False
    except Exception as e:
        logger.error(f"啟動 OKX Ticker WebSocket 失敗: {e}")
        okx_ticker_ws_started = False

@router.websocket("/ws/tickers")
async def websocket_tickers(websocket: WebSocket):
    """
    WebSocket 端點，用於即時 Ticker 數據推送 (Market Watch)

    客戶端訂閱格式:
    {"action": "subscribe", "symbols": ["BTC", "ETH", "SOL"]}
    {"action": "unsubscribe", "symbols": ["BTC"]}
    {"action": "unsubscribe_all"}
    """
    await ticker_manager.connect(websocket)

    try:
        from data.okx_websocket import okx_ticker_ws_manager

        # 確保 OKX Ticker WebSocket 已啟動
        asyncio.create_task(start_okx_ticker_websocket())

        current_callbacks = {}  # symbol -> callback

        async def create_ticker_callback(symbol: str):
            """為特定 symbol 創建回調函數"""
            async def on_ticker_update(sym: str, ticker: dict):
                try:
                    await websocket.send_json({
                        "type": "ticker",
                        "symbol": symbol,
                        "data": ticker
                    })
                except Exception:
                    pass
            return on_ticker_update

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "subscribe":
                    symbols = message.get("symbols", [])
                    if isinstance(symbols, str):
                        symbols = [symbols]

                    logger.info(f"收到 Ticker 訂閱請求: {symbols}")

                    # 訂閱每個 symbol
                    for symbol in symbols:
                        symbol = symbol.upper()
                        if symbol not in current_callbacks:
                            callback = await create_ticker_callback(symbol)
                            current_callbacks[symbol] = callback
                            await okx_ticker_ws_manager.subscribe(symbol, callback)
                            logger.info(f"已訂閱 Ticker: {symbol}")

                    ticker_manager.subscribe(websocket, symbols)
                    await websocket.send_json({
                        "type": "subscribed",
                        "symbols": symbols
                    })

                elif action == "unsubscribe":
                    symbols = message.get("symbols", [])
                    if isinstance(symbols, str):
                        symbols = [symbols]

                    for symbol in symbols:
                        symbol = symbol.upper()
                        if symbol in current_callbacks:
                            await okx_ticker_ws_manager.unsubscribe(symbol, current_callbacks[symbol])
                            del current_callbacks[symbol]

                    ticker_manager.unsubscribe(websocket, symbols)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "symbols": symbols
                    })

                elif action == "unsubscribe_all":
                    for symbol, callback in list(current_callbacks.items()):
                        await okx_ticker_ws_manager.unsubscribe(symbol, callback)
                    current_callbacks.clear()
                    ticker_manager.unsubscribe(websocket)
                    await websocket.send_json({"type": "unsubscribed_all"})

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info("Ticker WebSocket 客戶端主動斷開")
    except Exception as e:
        logger.error(f"Ticker WebSocket 錯誤: {e}")
    finally:
        # 清理訂閱
        try:
            from data.okx_websocket import okx_ticker_ws_manager
            for symbol, callback in current_callbacks.items():
                await okx_ticker_ws_manager.unsubscribe(symbol, callback)
        except:
            pass
        ticker_manager.disconnect(websocket)
