"""
Agent V4 — Chat Agent

一般對話 Agent: 處理問候、閒聊、系統說明，是所有未知請求的 fallback。
使用 LangChain create_agent 實現完整的 ReAct 循環。
Supports multi-language responses.
"""
import logging

from ..base_react_agent import BaseReActAgent
from ..prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)


class ChatAgent(BaseReActAgent):
    """對話 Agent - 使用 ReAct 循環，可調用簡單工具。"""

    @property
    def name(self) -> str:
        return "chat"

    def _get_system_prompt(self, language: str) -> str:
        """獲取系統提示詞。"""
        try:
            return PromptRegistry.get("chat_agent", "system", language)
        except Exception:
            if language == "zh-TW":
                return """你是一個有幫助的助手。

根據用戶的問題和可用工具的描述，自動決定是否需要調用工具。
如果問題簡單，直接回答；如果需要查詢資訊，調用相應工具。"""
            else:
                return """You are a helpful assistant.

Based on the user's question and available tool descriptions, automatically decide whether to call tools.
For simple questions, answer directly; for information queries, call appropriate tools."""
