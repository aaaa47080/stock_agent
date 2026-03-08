"""
Agent V4 — Crypto Agent

加密貨幣分析 Agent：使用 LangChain create_agent 實現 ReAct 循環。
LLM 自動決定調用哪些工具、參數是什麼。
Supports multi-language responses.
"""
import logging

from ..base_react_agent import BaseReActAgent
from ..prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)


class CryptoAgent(BaseReActAgent):
    """加密貨幣分析 Agent - 使用 ReAct 循環自動調用工具。"""

    @property
    def name(self) -> str:
        return "crypto"

    def _get_system_prompt(self, language: str) -> str:
        """獲取加密貨幣分析專用的系統提示詞。"""
        try:
            return PromptRegistry.get("crypto_agent", "system", language)
        except Exception:
            if language == "zh-TW":
                return """你是一個專業的加密貨幣分析師。

根據用戶的問題和可用工具的描述，自動決定：
1. 是否需要調用工具
2. 調用哪個工具
3. 傳入什麼參數

如果一個工具失敗，嘗試其他方式完成任務。"""
            else:
                return """You are a professional cryptocurrency analyst.

Based on the user's question and available tool descriptions, automatically decide:
1. Whether to call tools
2. Which tools to call
3. What parameters to pass

If one tool fails, try alternative approaches to complete the task."""
