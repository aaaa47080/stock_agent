import json
import asyncio
import os
import uuid
from typing import Optional
from functools import partial
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from core.tools import _find_available_exchange
from core.graph import app as graph_app
from api.models import QueryRequest, BacktestRequest
from api.utils import iterate_in_threadpool, logger
from analysis.simple_backtester import run_simple_backtest
import api.globals as globals
import core.config as core_config
from utils.user_client_factory import create_user_llm_client

# Import DB functions
from core.database import (
    save_chat_message, 
    get_chat_history, 
    clear_chat_history as db_clear_history,
    get_sessions,
    create_session,
    delete_session
)

# New function import for pin
from core.database import toggle_session_pin
from fastapi import Depends
from api.deps import get_current_user

router = APIRouter()

# --- Session Management Endpoints ---

@router.get("/api/chat/sessions")
async def get_user_sessions(user_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """獲取用戶對話列表（根據 user_id 過濾）"""
    # Fix: Default to current user if not provided
    if user_id is None:
        user_id = current_user["user_id"]

    # Fix: Allow "local_user" in TEST_MODE even if it doesn't match current_user (test-user-001)
    is_test_mode_local = core_config.TEST_MODE and user_id == "local_user"
    
    if current_user["user_id"] != user_id and not is_test_mode_local:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    loop = asyncio.get_running_loop()
    sessions = await loop.run_in_executor(None, partial(get_sessions, user_id=user_id))
    return {"sessions": sessions}

@router.post("/api/chat/sessions")
async def create_new_session(user_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """創建新對話（綁定 user_id）"""
    # Fix: Default to current user if not provided
    if user_id is None:
        user_id = current_user["user_id"]

    # Fix: Allow "local_user" in TEST_MODE
    is_test_mode_local = core_config.TEST_MODE and user_id == "local_user"

    if current_user["user_id"] != user_id and not is_test_mode_local:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    new_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(create_session, new_id, title="New Chat", user_id=user_id))
    return {"session_id": new_id, "title": "New Chat"}

@router.delete("/api/chat/sessions/{session_id}", dependencies=[Depends(get_current_user)])
async def delete_user_session(session_id: str):
    """刪除特定對話"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, delete_session, session_id)
    return {"status": "success", "message": f"Session {session_id} deleted"}

@router.put("/api/chat/sessions/{session_id}/pin", dependencies=[Depends(get_current_user)])
async def pin_user_session(session_id: str, is_pinned: bool = Query(..., description="Set to true to pin, false to unpin")):
    """切換對話置頂狀態"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(toggle_session_pin, session_id, is_pinned))
    return {"status": "success", "session_id": session_id, "is_pinned": is_pinned}

@router.get("/api/chat/history")
async def get_history(session_id: str = "default", current_user: dict = Depends(get_current_user)):
    """獲取特定會話的歷史"""
    # 這裡可以進一步驗證 session 是否屬於 usage
    loop = asyncio.get_running_loop()
    # TODO: Pass user_id to db function to ensure ownership
    history = await loop.run_in_executor(None, partial(get_chat_history, session_id=session_id, limit=50))
    return {"history": history}

# --- Analysis Endpoint ---

@router.post("/api/analyze")
async def analyze_crypto(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """
    處理分析請求，並以串流 (Streaming) 方式回傳結果。
    使用執行緒池避免阻塞事件循環。
    ⭐ 新版：使用用戶提供的 API key
    """
    if not globals.bot:
        logger.warning("分析服務尚未就緒 - CryptoAnalysisBot 未初始化")
        # 檢查是否是因為缺少配置導致的初始化失敗
        try:
            from interfaces.chat_interface import CryptoAnalysisBot
            # 嘗試重新初始化
            globals.bot = CryptoAnalysisBot()
            logger.info("CryptoAnalysisBot 重新初始化成功")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"CryptoAnalysisBot 初始化失敗: {error_details}")
            raise HTTPException(status_code=503, detail=f"分析服務尚未就緒: {str(e)}\n\nTraceback:\n{error_details}")

    # ⭐ 驗證用戶是否提供了 API key
    if not request.user_api_key or not request.user_provider:
        raise HTTPException(
            status_code=400,
            detail="缺少 API Key。請在系統設定中輸入您的 LLM API Key。"
        )

    # ⭐ 使用用戶提供的 key 創建 LLM 客戶端
    try:
        user_client = create_user_llm_client(
            provider=request.user_provider,
            api_key=request.user_api_key
        )
        # logger.info(f"✅ 使用用戶的 {request.user_provider} client")
    except Exception as e:
        logger.error(f"❌ 創建用戶 LLM client 失敗: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"API Key 無效: {str(e)}"
        )

    logger.info(f"收到分析請求 (Session: {request.session_id}): {request.message[:50]}...")

    # 1. 保存用戶訊息 (指定 Session ID)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(save_chat_message, "user", request.message, session_id=request.session_id))

    async def event_generator():
        full_response = ""
        try:
            # ⭐ 使用 iterate_in_threadpool 將同步生成器轉為異步
            async for part in iterate_in_threadpool(
                globals.bot.process_message(
                    request.message,
                    request.interval,
                    request.limit,
                    request.manual_selection,
                    request.auto_execute,
                    request.market_type,
                    user_llm_client=user_client,  # ⭐ 傳入用戶的 client
                    user_provider=request.user_provider,  # ⭐ 傳入 provider 類型
                    user_api_key=request.user_api_key, # ⭐ 傳入原始 Key 字串 (用於 Agent 重建)
                    user_model=request.user_model  # ⭐ 傳入用戶選擇的模型
                )
            ):
                full_response += part
                # 包裝成 JSON 格式發送給前端
                yield f"data: {json.dumps({'content': part})}\n\n"
            
            # 2. 保存 AI 完整回應 (指定 Session ID)
            # 注意: 這裡不能直接存取外層 loop，因為我們在 generator 內部。但在 Python 3.7+ 的 async generator 中應該沒問題，
            # 或者我們可以獲取新的 loop。安全起見獲取 loop。
            inner_loop = asyncio.get_running_loop()
            await inner_loop.run_in_executor(None, partial(save_chat_message, "assistant", full_response, session_id=request.session_id))

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"分析過程發生未預期錯誤: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'Internal Server Error'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/api/chat/clear")
async def clear_chat_history_endpoint(session_id: str = "default", current_user: dict = Depends(get_current_user)):
    """清除對話歷史"""
    if globals.bot:
        globals.bot.clear_history()
    
    # 清除 DB 歷史
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, db_clear_history, session_id)
    
    return {"status": "success", "message": "Chat history cleared"}

@router.get("/api/debate/{symbol}", dependencies=[Depends(get_current_user)])
async def get_debate_analysis(symbol: str):
    """
    獲取 AI 辯論詳情 (用於前端視覺化顯示)。
    執行完整的 ReAct Agent 流程，但只回傳辯論相關的結構化數據。
    """
    try:
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

@router.post("/api/backtest", dependencies=[Depends(get_current_user)])
async def run_backtest_api(request: BacktestRequest):
    """
    執行快速回測 (One-Click Backtest)。
    驗證特定技術指標策略在過去的表現。
    """
    try:
        loop = asyncio.get_running_loop()
        
        # 簡單標準化 symbol (假設 OKX 或 Binance 格式)
        clean_symbol = request.symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        # 預設加上 -USDT 給 OKX data fetcher (如果它需要)
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