"""
技術分析 Agent

職責：獲取和分析加密貨幣技術指標
"""
from typing import Tuple, Dict

from langchain_core.messages import HumanMessage

from ..base import SubAgent
from ..models import Task, AgentResult


class TechAgent(SubAgent):
    """
    技術分析 Agent

    職責：
    - 獲取技術指標（RSI, MACD, 均線等）
    - 獲取價格數據
    - 分析技術面走勢
    - 提供技術分析建議
    """

    SHOULD_PARTICIPATE_PROMPT = """判斷以下任務是否需要技術分析功能。

任務：{query}
類型：{task_type}

如果任務涉及以下內容，應該參與：
- 技術分析（如「技術面」、「指標」）
- 價格查詢
- 走勢分析
- 買賣建議
- 深度分析

只回答 YES 或 NO，然後簡短說明理由。"""

    ANALYSIS_PROMPT = """作為技術分析師，請分析以下數據。

幣種：{symbol}

技術指標：
{indicators}

價格數據（最近）：
{price_data}

請用繁體中文提供：
1. 技術面綜合評估（看漲/看跌/中性）
2. 關鍵指標解讀（RSI、MACD 等）
3. 支撐位和阻力位（如果可以判斷）
4. 短期走勢預測
5. 交易建議（買入/賣出/持有）

保持專業但易懂，避免過於技術性的術語。"""

    @property
    def name(self) -> str:
        return "TechAgent"

    @property
    def expertise(self) -> str:
        return "technical"

    @property
    def description(self) -> str:
        return "技術分析 Agent，提供 RSI、MACD、均線等技術指標分析"

    @property
    def responsibilities(self) -> str:
        return """
        1. 使用工具獲取技術指標
        2. 使用工具獲取價格數據
        3. 分析技術面走勢
        4. 提供專業的技術分析報告
        如果數據不足，可以請求使用者補充時間範圍或特定指標。
        """

    def should_participate(self, task: Task) -> Tuple[bool, str]:
        """判斷是否參與此任務"""
        prompt = self.SHOULD_PARTICIPATE_PROMPT.format(
            query=task.query,
            task_type=task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type)
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.upper()
            should_join = "YES" in content
            reason = response.content.split("\n")[0] if "\n" in response.content else response.content
            return (should_join, reason)

        except Exception as e:
            return (True, f"預設參與（判斷錯誤：{e}）")

    def execute(self, task: Task) -> AgentResult:
        """
        執行技術分析任務

        流程：
        1. 確定要分析的幣種
        2. 獲取技術指標
        3. 獲取價格數據
        4. 生成分析報告
        """
        self._observations = []

        # Step 1: 確定幣種
        symbols = task.symbols if task.symbols else self._extract_symbols(task.query)

        if not symbols:
            response = self.ask_user("你想分析哪個加密貨幣的技術面？")
            symbols = self._extract_symbols(response)
            if not symbols:
                symbols = ["BTC"]

        symbol = symbols[0]

        # Step 2: 獲取技術指標
        indicators = {}
        ta_result = self._use_tool("technical_analysis", {"symbol": symbol, "interval": "1d"})

        if ta_result.success and ta_result.data:
            indicators = ta_result.data
            self._add_observation(f"技術指標獲取成功")
        else:
            self._add_observation(f"技術指標獲取失敗: {ta_result.error}")

        # Step 3: 獲取價格數據
        price_data = {}
        price_result = self._use_tool("price_data", {"symbol": symbol})

        if price_result.success and price_result.data:
            price_data = price_result.data
            self._add_observation(f"價格數據獲取成功")
        else:
            self._add_observation(f"價格數據獲取失敗: {price_result.error}")

        # Step 4: 生成分析報告
        if not indicators and not price_data:
            return AgentResult(
                success=False,
                message=f"抱歉，無法獲取 {symbol} 的技術分析數據。請稍後再試。",
                agent_name=self.name,
                observations=self._observations
            )

        analysis = self._generate_analysis(symbol, indicators, price_data)

        return AgentResult(
            success=True,
            message=analysis,
            data={"indicators": indicators, "price_data": price_data},
            agent_name=self.name,
            observations=self._observations
        )

    def _extract_symbols(self, query: str) -> list:
        """從查詢中提取幣種符號"""
        symbols = []
        crypto_map = {
            'BTC': ['btc', 'bitcoin', '比特幣'],
            'ETH': ['eth', 'ethereum', '以太坊'],
            'SOL': ['sol', 'solana'],
            'PI': ['pi', 'pi network', 'pi幣'],
            'DOGE': ['doge', 'dogecoin'],
            'XRP': ['xrp', 'ripple'],
            'BNB': ['bnb', 'binance'],
        }

        query_lower = query.lower()
        for symbol, keywords in crypto_map.items():
            if any(kw in query_lower for kw in keywords):
                symbols.append(symbol)

        return symbols

    def _generate_analysis(self, symbol: str, indicators: dict, price_data: dict) -> str:
        """生成技術分析報告"""
        # 格式化指標數據
        ind_text = "無數據"
        if indicators:
            if isinstance(indicators, dict):
                ind_text = "\n".join([
                    f"- {k}: {v}"
                    for k, v in indicators.items()
                    if v is not None
                ])
            else:
                ind_text = str(indicators)[:500]

        # 格式化價格數據
        price_text = "無數據"
        if price_data:
            if isinstance(price_data, list) and len(price_data) > 0:
                latest = price_data[-1] if price_data else {}
                price_text = f"最新價格數據: {latest}"
            elif isinstance(price_data, dict):
                price_text = str(price_data)[:500]
            else:
                price_text = str(price_data)[:500]

        prompt = self.ANALYSIS_PROMPT.format(
            symbol=symbol,
            indicators=ind_text,
            price_data=price_text
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return f"📊 **{symbol} 技術分析**\n\n{response.content}"
        except Exception as e:
            # Fallback：返回原始數據
            return f"""📊 **{symbol} 技術分析**

**技術指標：**
{ind_text}

**價格數據：**
{price_text}

（詳細分析生成失敗：{e}）"""
