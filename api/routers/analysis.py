import json
import asyncio
import uuid
from typing import Optional
from functools import partial
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.models import QueryRequest, BacktestRequest
from api.response_metadata import build_response_metadata
from api.utils import logger
from analysis.simple_backtester import run_simple_backtest
import core.config as core_config
from utils.user_client_factory import create_user_llm_client
from api.middleware.rate_limit import limiter
from core.agents.analysis_policy import AnalysisPolicyResolver

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

ANALYSIS_TIMEOUT_SECONDS = 180
analysis_policy_resolver = AnalysisPolicyResolver()

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
async def get_history(
    session_id: str = "default",
    before_timestamp: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """獲取對話歷史（支援動態載入）。

    - 初始載入：不傳 before_timestamp，回傳最新 20 條
    - 向上捲動載入：傳入 before_timestamp（最舊可見訊息的時間），回傳更早的 20 條
    - has_more=True 表示還有更舊的訊息可載入
    """
    LIMIT = 20
    loop = asyncio.get_running_loop()
    # 多取一條用來偵測是否還有更多
    history = await loop.run_in_executor(
        None, partial(get_chat_history, session_id=session_id,
                      limit=LIMIT + 1, before_timestamp=before_timestamp)
    )
    has_more = len(history) > LIMIT
    if has_more:
        history = history[1:]  # 移除最舊那條（作為 has_more 探針）
    return {"history": history, "has_more": has_more}

# --- Analysis Endpoint ---

@router.get("/api/analyze/modes")
async def get_analysis_modes(current_user: dict = Depends(get_current_user)):
    mode_policy = analysis_policy_resolver.get_mode_access_policy(
        current_user.get("membership_tier", "free")
    )
    return {
        "current_tier": current_user.get("membership_tier", "free"),
        "allowed_modes": list(mode_policy.allowed_modes),
        "default_mode": mode_policy.default_mode,
    }

@router.post("/api/analyze")
@limiter.limit("10/minute")
async def analyze_crypto(request: Request, body: QueryRequest, current_user: dict = Depends(get_current_user)):
    """
    處理分析請求，以串流 (SSE) 方式回傳結果。

    V4 整合：使用 V4 ManagerAgent 處理所有請求。
    - 一般請求：invoke graph → SSE 串流最終回應
    - HITL 模式：
        第一次觸發 interrupt() → SSE 回傳 {type: "hitl_question"}
        前端帶 resume_answer 重送 → Command(resume=...) 繼續 graph
    若 V4 啟動失敗則回傳 503。
    """
    # ⭐ 驗證用戶是否提供了 API key
    if not body.user_api_key or not body.user_provider:
        raise HTTPException(
            status_code=400,
            detail="缺少 API Key。請在系統設定中輸入您的 LLM API Key。"
        )

    # ⭐ 使用用戶提供的 key 創建 LLM 客戶端
    try:
        user_client = create_user_llm_client(
            provider=body.user_provider,
            api_key=body.user_api_key,
            model=body.user_model,
        )
    except Exception as e:
        logger.error(f"❌ 創建用戶 LLM client 失敗: {e}")
        raise HTTPException(status_code=400, detail="API Key 無效，請檢查您的設定")

    logger.info(f"收到分析請求 (Session: {body.session_id}): {body.message[:50]}...")

    requested_mode = body.analysis_mode
    effective_mode = analysis_policy_resolver.ensure_allowed_mode(
        current_user.get("membership_tier", "free"),
        requested_mode,
    )
    if effective_mode != requested_mode:
        raise HTTPException(
            status_code=403,
            detail=f"analysis_mode '{requested_mode}' is not allowed for tier '{current_user.get('membership_tier', 'free')}'",
        )

    try:
        from langgraph.types import Command

        # 使用 ManagerAgent
        from core.agents.bootstrap import bootstrap
        from core.agents.manager import MANAGER_GRAPH_RECURSION_LIMIT
        logger.info("✅ ManagerAgent initialized")
        manager = bootstrap(
            user_client,
            web_mode=True,
            language=body.language,
            user_tier=current_user.get("membership_tier", "free"),
            user_id=current_user.get("user_id"),
            session_id=body.session_id,
        )
        config  = {
            "configurable": {"thread_id": body.session_id},
            "recursion_limit": MANAGER_GRAPH_RECURSION_LIMIT,
        }

        # resume_answer → 繼續被 interrupt 暫停的 graph
        graph_input: Command  # Type annotation for mypy
        if body.resume_answer is not None:
            logger.info(f"[V4] HITL resume: session={body.session_id}")
            graph_input = Command(resume=body.resume_answer)
        else:
            # 新請求：儲存到 DB + 載入對話歷史（平行執行，節省一個 DB round trip）
            loop = asyncio.get_running_loop()
            _, db_history_raw = await asyncio.gather(
                loop.run_in_executor(
                    None, partial(save_chat_message, "user", body.message,
                                  session_id=body.session_id, user_id=current_user.get("user_id"))
                ),
                loop.run_in_executor(
                    None, partial(get_chat_history, session_id=body.session_id, limit=20)
                )
            )

            # 載入 DB 歷史，格式化為純文字供 agent 使用
            history_text = ""
            try:
                db_history = db_history_raw
                lines = []
                for msg in db_history:
                    role    = "助手" if msg.get("role") == "assistant" else "用戶"
                    content = (msg.get("content") or "").strip()
                    # 排除剛存入的當前訊息（最後一條 user 訊息）
                    if content and content != body.message:
                        lines.append(f"{role}: {content}")
                history_text = "\n".join(lines[-18:])  # 最近 18 條
            except Exception as e:
                logger.warning(f"[V4] 載入對話歷史失敗: {e}")

            # Force graph to restart from appropriate node with new input
            # This ensures we don't get stuck in a previous interrupted state
            graph_input = Command(
                goto="understand_intent",
                update={
                    "session_id": body.session_id,
                    "query": body.message,
                    "history": history_text,
                    "analysis_mode": effective_mode,
                    "task_results": {},
                    "language": body.language,
                    "execution_mode": "vending",  # default, will be updated by intent understanding
                }
            )

        async def event_generator_v4():
            try:
                loop = asyncio.get_running_loop()
                progress_queue = asyncio.Queue()

                def on_progress(event):
                    loop.call_soon_threadsafe(progress_queue.put_nowait, event)

                manager.progress_callback = on_progress

                # Put a hard cap on analysis runtime so the frontend never waits forever.
                invoke_task = asyncio.create_task(
                    asyncio.wait_for(
                        manager.graph.ainvoke(graph_input, config),
                        timeout=ANALYSIS_TIMEOUT_SECONDS,
                    )
                )

                try:
                    while not invoke_task.done():
                        # Wait for either new progress event or task completion
                        queue_task = asyncio.create_task(progress_queue.get())
                        done, pending = await asyncio.wait(
                            [invoke_task, queue_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        if queue_task in done:
                            event = queue_task.result()
                            # Send progress event
                            yield f"data: {json.dumps({'type': 'progress', 'data': event})}\n\n"
                        else:
                            queue_task.cancel()

                    # Flush remaining events
                    while not progress_queue.empty():
                        event = progress_queue.get_nowait()
                        yield f"data: {json.dumps({'type': 'progress', 'data': event})}\n\n"

                    # Get result (awaiting the task captures any exception raised during ainvoke)
                    result = await invoke_task

                    # 偵測 interrupt（HITL 問題）→ 回傳給前端
                    interrupt_events = result.get("__interrupt__", [])
                    if interrupt_events:
                        iv = interrupt_events[0].value
                        yield f"data: {json.dumps({'type': 'hitl_question', 'data': iv})}\n\n"
                        yield f"data: {json.dumps({'done': True, 'waiting': True})}\n\n"
                        return

                    # 正常回應
                    response = result.get("final_response") or "（無回應）"
                    response_metadata = build_response_metadata(result, effective_mode)

                    chunk_size = 50
                    for i in range(0, len(response), chunk_size):
                        yield f"data: {json.dumps({'content': response[i:i+chunk_size]})}\n\n"
                        await asyncio.sleep(0.005)

                    inner_loop = asyncio.get_running_loop()
                    await inner_loop.run_in_executor(
                        None, partial(save_chat_message, "assistant", response,
                                      session_id=body.session_id, user_id=current_user.get("user_id"))
                    )

                    yield f"data: {json.dumps({'type': 'response_metadata', 'data': response_metadata})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"

                except asyncio.CancelledError:
                    logger.warning(f"[V4] Client disconnected, cancelling task for session {body.session_id}")
                    if not invoke_task.done():
                        invoke_task.cancel()
                        try:
                            await invoke_task
                        except asyncio.CancelledError:
                            pass
                    raise
                except asyncio.TimeoutError:
                    logger.error(
                        f"[V4] 分析超時: session={body.session_id}, timeout={ANALYSIS_TIMEOUT_SECONDS}s"
                    )
                    yield f"data: {json.dumps({'error': f'分析超時（超過 {ANALYSIS_TIMEOUT_SECONDS} 秒），請縮小問題範圍後重試。', 'done': True})}\n\n"
                except Exception as e:
                    logger.error(f"[V4] 分析過程發生錯誤: {e}", exc_info=True)
                    # SSE 錯誤處理：確保客戶端收到錯誤並結束流
                    yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
                finally:
                    manager.progress_callback = None
                    if not invoke_task.done():
                        logger.info(f"[V4] Generator exiting, ensuring task cancelled for session {body.session_id}")
                        invoke_task.cancel()
                        # We don't await here to avoid delaying the generator exit, 
                        # but the task will be cancelled in the background.

            except Exception as e:
                # Catch-all for the outer try block logic (e.g. queue setup errors)
                logger.error(f"[V4] Event generator error: {e}", exc_info=True)
                # SSE 錯誤處理：確保客戶端收到錯誤並結束流
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

        return StreamingResponse(event_generator_v4(), media_type="text/event-stream")

    except Exception as bootstrap_err:
        logger.error(f"[V4] Manager 啟動失敗: {bootstrap_err}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"分析服務暫時無法使用: {str(bootstrap_err)}")

@router.post("/api/chat/clear")
async def clear_chat_history_endpoint(session_id: str = "default", current_user: dict = Depends(get_current_user)):
    """清除對話歷史"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, db_clear_history, session_id)

    return {"status": "success", "message": "Chat history cleared"}


# === 會話管理 API ===


@router.post("/api/chat/new-session")
async def create_new_session(current_user: dict = Depends(get_current_user)):
    """創建新對話會話並整合舊會話記憶"""
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未授權")

    from core.agents.bootstrap import get_manager_instances, invalidate_manager_cache
    old_managers = get_manager_instances(user_id)

    # 整合舊會話記憶（在刪除 cache 前）
    for old_manager in old_managers:
        if old_manager and hasattr(old_manager, '_message_count') and old_manager._message_count > 0:
            logger.info(f"[API] Consolidating old session for user {user_id}: {old_manager.session_id}")
            if hasattr(old_manager, 'consolidate_session_memory'):
                await old_manager.consolidate_session_memory()

    # ✅ 清除 Manager 緩存，下次請求重建（新 session 需要乾淨的 message_count）
    invalidate_manager_cache(user_id)

    # 創建新會話
    new_session_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(create_session, new_session_id, title="New Chat Session", user_id=user_id)
    )

    return {
        "session_id": new_session_id,
        "title": "New Chat Session",
        "message": "已整合舊會話記憶並創建新會話"
    }


# === 閒置整合 API ===


@router.post("/api/chat/idle-consolidate")
async def trigger_idle_consolidation(current_user: dict = Depends(get_current_user)):
    """
    手動觸發閒置整合（當用戶閒置一段時間後調用）

    Returns:
        成功: {"status": "success", "message": "閒置整合完成"}
        跳過: {"status": "skipped", "message": "無需整合"}
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未授權")

    from core.agents.bootstrap import get_manager_instances
    managers = get_manager_instances(user_id)

    if not managers:
        return {"status": "skipped", "message": "無 Manager 實例"}

    target_managers = [manager for manager in managers if manager.check_idle_consolidation()]
    if not target_managers:
        return {"status": "skipped", "message": "無需整合"}

    try:
        for manager in target_managers:
            await manager._background_memory_consolidation()
        return {"status": "success", "message": f"閒置整合完成（{len(target_managers)} 個 session）"}
    except Exception as e:
        logger.error(f"閒置整合失敗: {e}")
        return {"status": "error", "message": str(e)}

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
        raise HTTPException(status_code=500, detail="回測執行失敗，請稍後再試")
