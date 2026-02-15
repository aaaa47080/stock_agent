"""Technical Analysis Agent"""
from typing import List
from .base import ProfessionalAgent
from .task import Task


TECHNICAL_ANALYST_PROMPT = """你是一位專業的技術分析師，擅長使用各種技術指標分析加密貨幣市場。

你的職責：
1. 分析價格走勢和技術形態
2. 識別支撐位和阻力位
3. 評估市場動量和趨勢強度
4. 提供基於技術面的交易建議

分析風格：{personality}

注意事項：
- 總是基於數據做出判斷
- 承認不確定性，不要過度自信
- 如果用戶有疑問，願意解釋你的分析邏輯
- 如果用戶提出合理的質疑，願意修正你的觀點
"""


class TechnicalAgent(ProfessionalAgent):
    """技術分析 Agent"""

    def __init__(self, llm_client=None):
        super().__init__(
            expertise="technical_analysis",
            system_prompt=TECHNICAL_ANALYST_PROMPT,
            personality="analytical"
        )
        self.llm_client = llm_client
        self.available_tools = []

    def select_tools(self, task: Task) -> List:
        """根據任務自主選擇工具"""
        tools = []

        # 基礎技術指標
        rsi_tool = self._get_tool("rsi")
        macd_tool = self._get_tool("macd")
        if rsi_tool:
            tools.append(rsi_tool)
        if macd_tool:
            tools.append(macd_tool)

        # 根據分析深度添加更多工具
        if task.analysis_depth == "deep":
            bb_tool = self._get_tool("bollinger_bands")
            sr_tool = self._get_tool("support_resistance")
            if bb_tool:
                tools.append(bb_tool)
            if sr_tool:
                tools.append(sr_tool)

        # 如果需要回測
        if task.needs_backtest:
            backtest_tool = self._get_tool("backtest")
            if backtest_tool:
                tools.append(backtest_tool)

        return tools

    def should_participate(self, task: Task) -> tuple:
        """技術分析師幾乎總是參與，但簡單價格查詢可能跳過"""
        if task.type.value == "simple_price":
            return False, "簡單價格查詢不需要技術分析"
        return True, "技術分析是投資決策的基礎"
