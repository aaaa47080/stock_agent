"""
新聞搜集 Agent

職責：搜集、過濾、總結加密貨幣相關新聞
"""
from typing import Tuple, Dict

from langchain_core.messages import HumanMessage

from ..base import SubAgent
from ..models import Task, AgentResult


class NewsAgent(SubAgent):
    """
    新聞搜集 Agent

    職責：
    - 搜集多來源新聞（Google RSS、CryptoPanic 等）
    - 過濾和篩選相關新聞
    - 總結新聞要點
    - 分析新聞對市場的潛在影響
    """

    SHOULD_PARTICIPATE_PROMPT = """判斷以下任務是否需要新聞搜集功能。

任務：{query}
類型：{task_type}

如果任務涉及以下內容，應該參與：
- 新聞查詢（如「最新新聞」、「有什麼消息」）
- 市場動態
- 幣種相關資訊
- 深度分析（需要新聞作為背景）

只回答 YES 或 NO，然後簡短說明理由。"""

    SUMMARIZE_PROMPT = """請總結以下加密貨幣新聞，提取關鍵資訊。

幣種：{symbol}
新聞數量：{count} 條

新聞列表：
{news_list}

請用繁體中文提供：
1. 整體趨勢判斷（正面/負面/中性）
2. 3-5 個關鍵要點
3. 對市場的潛在影響

保持簡潔，重點突出。"""

    @property
    def name(self) -> str:
        return "NewsAgent"

    @property
    def expertise(self) -> str:
        return "news"

    @property
    def description(self) -> str:
        return "新聞搜集和分析 Agent，支援 Google News RSS、CryptoPanic 等多來源"

    @property
    def responsibilities(self) -> str:
        return """
        1. 使用可用工具搜集加密貨幣新聞
        2. 過濾和篩選相關新聞
        3. 總結新聞要點
        4. 分析新聞對市場的影響
        如果新聞來源不足或資訊不夠，可以請求使用者補充或嘗試其他來源。
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

            # 提取理由
            reason = response.content.split("\n")[0] if "\n" in response.content else response.content

            return (should_join, reason)

        except Exception as e:
            # 出錯時預設參與（新聞查詢很常見）
            return (True, f"預設參與（判斷錯誤：{e}）")

    def execute(self, task: Task) -> AgentResult:
        """
        執行新聞搜集任務

        流程：
        1. 確定要查詢的幣種
        2. 調用工具獲取新聞
        3. 如果新聞太少，嘗試其他來源
        4. 總結結果
        """
        self.state = self.state.THINKING if hasattr(self.state, 'THINKING') else None
        self._observations = []

        # Step 1: 確定幣種
        symbols = task.symbols if task.symbols else self._extract_symbols(task.query)

        if not symbols:
            # HITL: 詢問使用者
            response = self.ask_user("你想了解哪個加密貨幣的新聞？")
            symbols = self._extract_symbols(response)
            if not symbols:
                symbols = ["BTC"]  # 預設比特幣

        # Step 2: 搜集新聞
        all_news = []

        for symbol in symbols[:2]:  # 最多 2 個幣種
            # 嘗試 Google News
            result = self._use_tool("google_news", {"symbol": symbol, "limit": 5})

            if result.success and result.data:
                self._add_observation(f"Google News: {symbol} - {len(result.data)} 條")
                for news in result.data:
                    news["symbol"] = symbol
                    all_news.append(news)
            else:
                self._add_observation(f"Google News: {symbol} - 獲取失敗")

        # Step 3: 如果新聞太少，嘗試其他來源
        if len(all_news) < 3:
            for symbol in symbols[:1]:
                result = self._use_tool("cryptopanic", {"symbols": [symbol], "limit": 5})
                if result.success and result.data:
                    self._add_observation(f"CryptoPanic: {symbol} - {len(result.data)} 條")
                    for news in result.data:
                        news["symbol"] = symbol
                        all_news.append(news)

        # Step 4: 整理和總結
        if not all_news:
            return AgentResult(
                success=False,
                message="抱歉，無法獲取相關新聞。請稍後再試。",
                agent_name=self.name,
                observations=self._observations
            )

        # 生成摘要
        summary = self._summarize_news(symbols[0] if symbols else "Crypto", all_news)

        # 格式化輸出
        formatted = self._format_news_output(all_news[:10], summary)

        return AgentResult(
            success=True,
            message=formatted,
            data={"news": all_news, "summary": summary},
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
            'ADA': ['ada', 'cardano'],
        }

        query_lower = query.lower()
        for symbol, keywords in crypto_map.items():
            if any(kw in query_lower for kw in keywords):
                symbols.append(symbol)

        return symbols

    def _summarize_news(self, symbol: str, news_list: list) -> str:
        """使用 LLM 總結新聞"""
        news_text = "\n".join([
            f"- [{n.get('source', 'Unknown')}] {n.get('title', 'No Title')}"
            for n in news_list[:10]
        ])

        prompt = self.SUMMARIZE_PROMPT.format(
            symbol=symbol,
            count=len(news_list),
            news_list=news_text
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            return f"總結生成失敗：{e}"

    def _format_news_output(self, news_list: list, summary: str) -> str:
        """格式化新聞輸出"""
        lines = ["📰 **新聞摘要**", "", summary, "", "─" * 40, "📋 **詳細新聞**", ""]

        for i, news in enumerate(news_list, 1):
            title = news.get('title', 'No Title')
            source = news.get('source', 'Unknown')
            url = news.get('url', '')

            lines.append(f"**{i}.** {title}")
            lines.append(f"   📎 {source}")
            if url:
                lines.append(f"   🔗 {url[:60]}...")
            lines.append("")

        return "\n".join(lines)
