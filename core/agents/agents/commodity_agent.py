"""
Commodity Agent - 大宗商品專業分析師

負責處理黃金、白銀、石油、天然氣、銅等大宗商品的查詢。
"""
from langchain_core.messages import HumanMessage, SystemMessage


class CommodityAgent:
    """大宗商品專業分析師"""

    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tools = tool_registry

    def process(self, query: str, context: dict = None) -> str:
        """處理大宗商品相關查詢"""
        system_prompt = """你是一位專業的大宗商品分析師。
你的職責是協助用戶查詢和分析黃金、白銀、石油、天然氣、銅等大宗商品。

可用工具：
- get_commodity_price: 查詢商品 ETF 價格（黃金、白銀、石油等）
- get_commodity_futures_price: 查詢商品期貨價格
- get_all_commodities_prices: 獲取所有主要商品價格一覽表
- get_gold_silver_ratio: 獲取金銀比（市場情緒指標）
- get_oil_price_analysis: 獲取原油價格綜合分析（WTI vs 布蘭特）

請根據用戶問題選擇適當的工具，並提供專業、準確的回答。
回答時請使用繁體中文。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]

        return self.llm.invoke(messages)
