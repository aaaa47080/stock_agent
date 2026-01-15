"""
Langfuse 整合模組 V3 - 官方推薦方式
基於官方文檔: https://langfuse.com/docs/integrations/langchain/tracing

Langfuse 3.x 使用環境變數自動配置，CallbackHandler 會自動讀取：
  - LANGFUSE_PUBLIC_KEY
  - LANGFUSE_SECRET_KEY
  - LANGFUSE_HOST
"""

from typing import Dict, Any, Optional
from langfuse.langchain import CallbackHandler
from monitoring.langfuse_config import LANGFUSE_CONFIG, flush_langfuse

def create_langfuse_handler() -> Optional[CallbackHandler]:
    """
    創建 Langfuse CallbackHandler (V3 官方方式)

    V3 版本會自動從環境變數讀取配置，不需要手動傳入參數

    Returns:
        CallbackHandler 實例或 None
    """
    if not LANGFUSE_CONFIG['enabled']:
        return None

    try:
        # V3 方式: 不傳入任何參數，使用環境變數配置
        handler = CallbackHandler()
        return handler
    except Exception as e:
        print(f"⚠️ 創建 Langfuse Handler 失敗: {e}")
        return None

def get_langfuse_config(
    user_id: str,
    session_id: str,
    tags: list = None,
    metadata: Dict[str, Any] = None
) -> tuple[Dict[str, Any], Optional[CallbackHandler]]:
    """
    獲取包含 Langfuse callback 的 LangGraph 配置 (V3 推薦方式)

    Args:
        user_id: 用戶 ID
        session_id: 會話 ID
        tags: 標籤列表
        metadata: 額外的元數據

    Returns:
        (配置字典, handler實例)
    """
    if not LANGFUSE_CONFIG['enabled']:
        return {}, None

    handler = create_langfuse_handler()
    if not handler:
        return {}, None

    # V3 方式: 通過 metadata 傳遞 user_id, session_id, tags
    langfuse_metadata = {
        **(metadata or {})
    }

    if user_id:
        langfuse_metadata["langfuse_user_id"] = user_id
    if session_id:
        langfuse_metadata["langfuse_session_id"] = session_id
    if tags:
        langfuse_metadata["langfuse_tags"] = tags

    config = {
        "callbacks": [handler],
        "metadata": langfuse_metadata
    }

    return config, handler

def update_trace_io(
    handler: CallbackHandler,
    user_query: str,
    final_answer: str,
    additional_metadata: Dict[str, Any] = None
) -> None:
    """
    更新 trace 級別的 input/output

    注意: Langfuse 3.x 的 CallbackHandler 會自動記錄 LangGraph 的執行過程，
    此函數主要用於記錄追蹤 ID 以便在 UI 中查看。
    """
    if not handler:
        return

    try:
        trace_id = getattr(handler, 'trace_id', None) or getattr(handler, 'last_trace_id', None)
        if trace_id:
            print(f"✅ [Langfuse] Trace ID: {trace_id[:12]}... → 可在 {LANGFUSE_CONFIG['host']} 查看")
    except Exception as e:
        print(f"⚠️ [Langfuse] 無法獲取 trace_id: {e}")

# 導出 flush 函數
__all__ = ['create_langfuse_handler', 'get_langfuse_config', 'update_trace_io', 'flush_langfuse']
