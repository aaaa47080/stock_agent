"""
Agent V4 — TW Stock Agent

台股分析 Agent：使用 LangChain create_agent 實現 ReAct 循環。
LLM 自動決定調用哪些工具、參數是什麼。
"""

import re

from core.tools.tw_symbol_resolver import TWSymbolResolver

from ..base_react_agent import BaseReActAgent
from ..prompt_registry import PromptRegistry


class TWStockAgent(BaseReActAgent):
    """台股分析 Agent - 使用 ReAct 循環自動調用工具。"""

    def __init__(
        self, llm_client, tool_registry, user_tier: str = "free", user_id=None
    ):
        super().__init__(
            llm_client, tool_registry, user_tier=user_tier, user_id=user_id
        )
        # Keep resolver for backwards compatibility with tests/legacy helpers.
        self.resolver = TWSymbolResolver()

    @property
    def name(self) -> str:
        return "tw_stock"

    def _get_system_prompt(self, language: str) -> str:
        """獲取台股分析專用的系統提示詞。"""
        try:
            return PromptRegistry.get("tw_stock_agent", "system", language)
        except Exception:
            if language == "zh-TW":
                return """你是一個專業的台股分析師。

根據用戶的問題和可用工具的描述，自動決定：
1. 是否需要調用工具
2. 調用哪個工具
3. 傳入什麼參數（如股票代號 ticker）

可處理：價格查詢、技術分析、基本面、籌碼分析、新聞等。"""
            else:
                return """You are a professional Taiwan stock analyst.

Based on the user's question and available tool descriptions, automatically decide:
1. Whether to call tools
2. Which tools to call
3. What parameters to pass (e.g., ticker symbol)

Can handle: price queries, technical analysis, fundamentals, institutional analysis, news, etc."""

    def _extract_ticker(self, description: str) -> str:
        """
        Backward-compatible ticker extractor for unit tests and legacy callers.
        Main runtime routing remains handled by manager + tools.
        """
        if not description:
            return ""

        # Fast path: pure numeric ticker in query.
        match = re.search(r"\b(\d{4,6})\b", description)
        if match:
            resolved = self.resolver.resolve(match.group(1))
            return resolved or ""

        # Fallback: try short tokens and finally the full phrase.
        words = re.split(r"[\s,，。！？、「」【】]+", description)
        for word in words:
            if 2 <= len(word) <= 12:
                resolved = self.resolver.resolve(word)
                if resolved:
                    return resolved

        resolved = self.resolver.resolve(description[:20])
        return resolved or ""
