"""
Agent V4 — Tech Agent

技術分析 Agent：使用 LangChain create_agent 實現 ReAct 循環。
LLM 自動決定調用哪些技術分析工具。
"""

import logging

from ..base_react_agent import BaseReActAgent
from ..prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)


class TechAgent(BaseReActAgent):
    """技術分析 Agent - 使用 ReAct 循環自動調用分析工具。"""

    @property
    def name(self) -> str:
        return "technical"

    def _get_system_prompt(self, language: str) -> str:
        """獲取技術分析專用的系統提示詞。"""
        try:
            return PromptRegistry.get("tech_agent", "system", language)
        except Exception:
            if language == "zh-TW":
                return """你是一個專業的技術分析師。

根據用戶的問題和可用工具的描述，自動決定：
1. 是否需要調用工具
2. 調用哪個工具
3. 傳入什麼參數（如 symbol、interval）

提供專業的技術分析報告。"""
            else:
                return """You are a professional technical analyst.

Based on the user's question and available tool descriptions, automatically decide:
1. Whether to call tools
2. Which tools to call
3. What parameters to pass (e.g., symbol, interval)

Provide professional technical analysis reports."""
