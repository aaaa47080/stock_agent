import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from api.deps import get_current_user
from api.middleware.rate_limit import limiter
from api.models import QueryRequest
from api.response_metadata import build_response_metadata
from api.user_llm import resolve_user_llm_credentials
from api.utils import logger, run_sync
from core.agents.analysis_policy import AnalysisPolicyResolver
from core.database import (
    check_session_ownership,
    create_session,
    delete_session,
    get_chat_history,
    get_sessions,
    save_chat_message,
    save_codebook_feedback,
    toggle_session_pin,
)
from core.database import (
    clear_chat_history as db_clear_history,
)
from utils.user_client_factory import create_user_llm_client

router = APIRouter()

ANALYSIS_TIMEOUT_SECONDS = 180
analysis_policy_resolver = AnalysisPolicyResolver()


# --- Session Management Endpoints ---


@router.get("/api/chat/sessions")
async def get_user_sessions(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """獲取用戶對話列表"""
    user_id = current_user["user_id"]

    sessions = await run_sync(
        lambda: get_sessions(user_id=user_id, limit=limit, offset=offset)
    )
    return {"success": True, "sessions": sessions}


@router.delete("/api/chat/sessions/{session_id}")
@limiter.limit("20/minute")
async def delete_user_session(
    request: Request, session_id: str, current_user: dict = Depends(get_current_user)
):
    """刪除特定對話"""
    user_id = current_user["user_id"]
    owns = await run_sync(check_session_ownership, session_id, user_id)
    if not owns:
        raise HTTPException(
            status_code=403, detail="Forbidden: session does not belong to you"
        )
    await run_sync(delete_session, session_id)
    return {"status": "success", "message": f"Session {session_id} deleted"}


@router.put("/api/chat/sessions/{session_id}/pin")
@limiter.limit("30/minute")
async def pin_user_session(
    request: Request,
    session_id: str,
    is_pinned: bool = Query(..., description="Set to true to pin, false to unpin"),
    current_user: dict = Depends(get_current_user),
):
    """切換對話置頂狀態"""
    user_id = current_user["user_id"]
    owns = await run_sync(check_session_ownership, session_id, user_id)
    if not owns:
        raise HTTPException(
            status_code=403, detail="Forbidden: session does not belong to you"
        )
    await run_sync(lambda: toggle_session_pin(session_id, is_pinned))
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
    user_id = current_user["user_id"]
    owns = await run_sync(check_session_ownership, session_id, user_id)
    if not owns:
        raise HTTPException(
            status_code=403, detail="Forbidden: session does not belong to you"
        )
    LIMIT = 20
    history = await run_sync(
        lambda: get_chat_history(
            session_id=session_id, limit=LIMIT + 1, before_timestamp=before_timestamp
        )
    )
    has_more = len(history) > LIMIT
    if has_more:
        history = history[1:]
    return {"success": True, "history": history, "has_more": has_more}


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
async def analyze_crypto(
    request: Request, body: QueryRequest, current_user: dict = Depends(get_current_user)
):
    """
    處理分析請求，以串流 (SSE) 方式回傳結果。

    V4 整合：使用 V4 ManagerAgent 處理所有請求。
    - 一般請求：invoke graph → SSE 串流最終回應
    - HITL 模式：
        第一次觸發 interrupt() → SSE 回傳 {type: "hitl_question"}
        前端帶 resume_answer 重送 → Command(resume=...) 繼續 graph
    若 V4 啟動失敗則回傳 503。
    """
    credentials = await resolve_user_llm_credentials(current_user, body.user_provider)
    if not credentials:
        raise HTTPException(
            status_code=400,
            detail="缺少可用的 LLM API Key。請在系統設定中輸入您的 API Key。",
        )

    try:
        user_client = create_user_llm_client(
            provider=credentials["provider"],
            api_key=credentials["api_key"],
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
        config = {
            "configurable": {"thread_id": body.session_id},
            "recursion_limit": MANAGER_GRAPH_RECURSION_LIMIT,
        }

        graph_input: Command
        if body.resume_answer is not None:
            logger.info(f"[V4] HITL resume: session={body.session_id}")
            graph_input = Command(resume=body.resume_answer)
        else:
            _, db_history_raw = await asyncio.gather(
                run_sync(
                    lambda: save_chat_message(
                        "user",
                        body.message,
                        session_id=body.session_id,
                        user_id=current_user.get("user_id"),
                    )
                ),
                run_sync(
                    lambda: get_chat_history(session_id=body.session_id, limit=20)
                ),
            )

            history_text = ""
            try:
                db_history = db_history_raw
                lines = []
                for msg in db_history:
                    role = "助手" if msg.get("role") == "assistant" else "用戶"
                    content = (msg.get("content") or "").strip()
                    if content and content != body.message:
                        lines.append(f"{role}: {content}")
                history_text = "\n".join(lines[-18:])
            except Exception as e:
                logger.warning(f"[V4] 載入對話歷史失敗: {e}")

            graph_input = Command(
                goto="understand_intent",
                update={
                    "session_id": body.session_id,
                    "query": body.message,
                    "history": history_text,
                    "analysis_mode": effective_mode,
                    "task_results": {},
                    "language": body.language,
                    "execution_mode": "vending",
                },
            )

        async def event_generator_v4():
            try:
                progress_queue = asyncio.Queue()

                def on_progress(event):
                    asyncio.get_running_loop().call_soon_threadsafe(
                        progress_queue.put_nowait, event
                    )

                manager.progress_callback = on_progress

                invoke_task = asyncio.create_task(
                    asyncio.wait_for(
                        manager.graph.ainvoke(graph_input, config),
                        timeout=ANALYSIS_TIMEOUT_SECONDS,
                    )
                )

                try:
                    while not invoke_task.done():
                        queue_task = asyncio.create_task(progress_queue.get())
                        done, pending = await asyncio.wait(
                            [invoke_task, queue_task],
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        if queue_task in done:
                            event = queue_task.result()
                            yield f"data: {json.dumps({'type': 'progress', 'data': event})}\n\n"
                        else:
                            queue_task.cancel()

                    while not progress_queue.empty():
                        event = progress_queue.get_nowait()
                        yield f"data: {json.dumps({'type': 'progress', 'data': event})}\n\n"

                    result = await invoke_task

                    interrupt_events = result.get("__interrupt__", [])
                    if interrupt_events:
                        iv = interrupt_events[0].value
                        yield f"data: {json.dumps({'type': 'hitl_question', 'data': iv})}\n\n"
                        yield f"data: {json.dumps({'done': True, 'waiting': True})}\n\n"
                        return

                    response = result.get("final_response") or "（無回應）"
                    response_metadata = build_response_metadata(result, effective_mode)

                    chunk_size = 50
                    for i in range(0, len(response), chunk_size):
                        yield f"data: {json.dumps({'content': response[i : i + chunk_size]})}\n\n"
                        await asyncio.sleep(0.005)

                    await run_sync(
                        lambda: save_chat_message(
                            "assistant",
                            response,
                            session_id=body.session_id,
                            user_id=current_user.get("user_id"),
                        )
                    )

                    yield f"data: {json.dumps({'type': 'response_metadata', 'data': response_metadata})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"

                except asyncio.CancelledError:
                    logger.warning(
                        f"[V4] Client disconnected, cancelling task for session {body.session_id}"
                    )
                    if not invoke_task.done():
                        invoke_task.cancel()
                        try:
                            await invoke_task
                        except asyncio.CancelledError:
                            logger.debug("Task cancelled for session=%s", body.session_id)
                    raise
                except asyncio.TimeoutError:
                    logger.error(
                        f"[V4] 分析超時: session={body.session_id}, timeout={ANALYSIS_TIMEOUT_SECONDS}s"
                    )
                    yield f"data: {json.dumps({'error': f'分析超時（超過 {ANALYSIS_TIMEOUT_SECONDS} 秒），請縮小問題範圍後重試。', 'done': True})}\n\n"
                except Exception as e:
                    logger.error(f"[V4] 分析過程發生錯誤: {e}", exc_info=True)
                    yield f"data: {json.dumps({'error': 'Internal server error. Please try again.', 'done': True})}\n\n"
                finally:
                    manager.progress_callback = None
                    if not invoke_task.done():
                        logger.info(
                            f"[V4] Generator exiting, ensuring task cancelled for session {body.session_id}"
                        )
                        invoke_task.cancel()

            except Exception as e:
                logger.error(f"[V4] Event generator error: {e}", exc_info=True)
                yield f"data: {json.dumps({'error': 'Internal server error. Please try again.', 'done': True})}\n\n"

        return StreamingResponse(event_generator_v4(), media_type="text/event-stream")

    except Exception as bootstrap_err:
        logger.error(f"[V4] Manager 啟動失敗: {bootstrap_err}", exc_info=True)
        raise HTTPException(status_code=503, detail="分析服務暫時無法使用，請稍後再試")


@router.post("/api/chat/clear")
@limiter.limit("5/minute")
async def clear_chat_history_endpoint(
    request: Request,
    session_id: str = "default",
    current_user: dict = Depends(get_current_user),
):
    """清除對話歷史"""
    user_id = current_user.get("user_id")
    owns = await run_sync(check_session_ownership, session_id, user_id)
    if not owns:
        raise HTTPException(status_code=403, detail="無權限清除此對話")
    await run_sync(db_clear_history, session_id)

    return {"status": "success", "message": "Chat history cleared"}


# === 會話管理 API ===


@router.post("/api/chat/new-session")
@limiter.limit("10/minute")
async def create_new_session(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """創建新對話會話並整合舊會話記憶"""
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未授權")

    from core.agents.bootstrap import get_manager_instances, invalidate_manager_cache

    old_managers = get_manager_instances(user_id)

    for old_manager in old_managers:
        if (
            old_manager
            and hasattr(old_manager, "_message_count")
            and old_manager._message_count > 0
        ):
            logger.info(
                f"[API] Consolidating old session for user {user_id}: {old_manager.session_id}"
            )
            if hasattr(old_manager, "consolidate_session_memory"):
                await old_manager.consolidate_session_memory()

    invalidate_manager_cache(user_id)

    new_session_id = str(uuid.uuid4())
    await run_sync(
        lambda: create_session(
            new_session_id, title="New Chat Session", user_id=user_id
        )
    )

    return {
        "session_id": new_session_id,
        "title": "New Chat Session",
        "message": "已整合舊會話記憶並創建新會話",
    }


# === 閒置整合 API ===


@router.post("/api/chat/idle-consolidate")
@limiter.limit("5/minute")
async def trigger_idle_consolidation(
    request: Request, current_user: dict = Depends(get_current_user)
):
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

    target_managers = [
        manager for manager in managers if manager.check_idle_consolidation()
    ]
    if not target_managers:
        return {"status": "skipped", "message": "無需整合"}

    try:
        for manager in target_managers:
            await manager._background_memory_consolidation()
        return {
            "status": "success",
            "message": f"閒置整合完成（{len(target_managers)} 個 session）",
        }
    except Exception as e:
        logger.error(f"閒置整合失敗: {e}")
        return {
            "status": "error",
            "message": "Internal server error. Please try again.",
        }


# === Codebook Feedback API ===


class FeedbackRequest(BaseModel):
    """分析品質回饋請求"""
    codebook_entry_id: str
    score: int  # 1 = helpful, 0 = not helpful


@router.post("/api/chat/feedback")
@limiter.limit("20/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    current_user: dict = Depends(get_current_user),
):
    """儲存分析品質回饋"""
    if body.score not in (0, 1):
        raise HTTPException(
            status_code=400, detail="Score must be 0 or 1"
        )
    user_id = current_user.get("user_id")
    await run_sync(save_codebook_feedback, body.codebook_entry_id, user_id, body.score)
    return {"success": True}
