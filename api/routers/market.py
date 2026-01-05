import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Header

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
    save_screener_cache,
    save_market_pulse_cache,
    update_funding_rates,
    refresh_all_market_pulse_data
)
from analysis.crypto_screener import screen_top_cryptos
from analysis.market_pulse import get_market_pulse
import numpy as np
from datetime import datetime

router = APIRouter()

@router.get("/api/market/symbols")
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
                    save_market_pulse_cache()
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

@router.post("/api/market-pulse/refresh-all")
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
