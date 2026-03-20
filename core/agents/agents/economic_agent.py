"""
Agent V4 — Economic Agent

經濟數據分析 Agent：使用 LangChain create_agent 實現 ReAct 循環。
LLM 自動決定調用哪些工具、參數是什麼。
"""

import logging

from ..base_react_agent import BaseReActAgent
from ..prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)


class EconomicAgent(BaseReActAgent):
    """經濟數據分析 Agent - 使用 ReAct 循環自動調用工具。"""

    @property
    def name(self) -> str:
        return "economic"

    def _get_system_prompt(self, language: str) -> str:
        """獲取經濟分析專用的系統提示詞。"""
        try:
            return PromptRegistry.get("economic_agent", "system", language)
        except Exception:
            if language == "zh-TW":
                return """你是一個專業的經濟數據分析師。

根據用戶的問題和可用工具的描述，自動決定：
1. 是否需要調用工具
2. 調用哪個工具
3. 傳入什麼參數

可處理：市場指數、VIX恐慌指數、經濟指標、板塊表現等。

VIX 指數解讀：
- VIX < 15: 市場平穩
- VIX 15-25: 正常波動
- VIX > 25: 市場恐慌
- VIX > 40: 極度恐慌"""
            else:
                return """You are a professional economic data analyst.

Based on the user's question and available tool descriptions, automatically decide:
1. Whether to call tools
2. Which tools to call
3. What parameters to pass

Can handle: market indices, VIX index, economic indicators, sector performance, etc.

VIX Index Interpretation:
- VIX < 15: Calm market
- VIX 15-25: Normal volatility
- VIX > 25: Market fear
- VIX > 40: Extreme panic"""
