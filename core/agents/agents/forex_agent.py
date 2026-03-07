"""
Forex Agent - 外匯專業分析師

負責處理貨幣對匯率、央行利率等外匯相關查詢。
"""
from langchain_core.messages import HumanMessage, SystemMessage


class ForexAgent:
    """外匯專業分析師"""

    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tools = tool_registry

    @property
    def name(self) -> str:
        return "forex"

    def process(self, query: str, context: dict = None) -> str:
        """處理外匯相關查詢"""
        system_prompt = """你是一位專業的外匯分析師。
你的職責是協助用戶查詢和分析各國貨幣匯率、央行利率等外匯市場資訊。

可用工具：
- get_forex_rate: 查詢特定貨幣對匯率（如 USD/TWD、EUR/USD）
- get_all_forex_rates: 獲取所有主要貨幣對匯率一覽
- get_usd_twd_rate: 快速查詢美元/台幣匯率
- get_central_bank_rates: 獲取主要央行利率

請根據用戶問題選擇適當的工具，並提供專業、準確的回答。
回答時請使用繁體中文。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]

        return self.llm.invoke(messages)
