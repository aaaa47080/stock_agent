"""
Economic Agent - 經濟數據專業分析師

負責處理市場指數、經濟指標、板塊表現等宏觀經濟查詢。
"""
from langchain_core.messages import HumanMessage, SystemMessage


class EconomicAgent:
    """經濟數據專業分析師"""

    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tools = tool_registry

    def process(self, query: str, context: dict = None) -> str:
        """處理經濟數據相關查詢"""
        system_prompt = """你是一位專業的經濟數據分析師。
你的職責是協助用戶查詢和分析市場指數、經濟指標、板塊表現等宏觀經濟資訊。

可用工具：
- get_market_indices: 獲取美股主要指數（S&P 500、道瓊、那斯達克、VIX）
- get_vix_index: 獲取 VIX 恐慌指數詳細資訊
- get_sp500_performance: 獲取 S&P 500 詳細表現
- get_sector_performance: 獲取美股 11 大板塊表現
- get_economic_calendar: 獲取經濟事件行事曆

請根據用戶問題選擇適當的工具，並提供專業、準確的回答。
回答時請使用繁體中文。

VIX 指數解讀指南：
- VIX < 15: 市場平穩，投資者情緒樂觀
- VIX 15-25: 正常波動範圍
- VIX > 25: 市場恐慌，需關注風險
- VIX > 40: 極度恐慌，可能出現拋售"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]

        return self.llm.invoke(messages)
