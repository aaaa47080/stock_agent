"""
Agent V4 — News Agent

新聞搜集 Agent: 多來源新聞聚合與總結。
"""
from typing import Optional

from langchain_core.messages import HumanMessage

from ..base import SubAgent
from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class NewsAgent(SubAgent):

    @property
    def name(self) -> str:
        return "news"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute news gathering and summarization."""
        symbol = self._extract_symbol(task.description)

        # Pre-execution: ask user for preferences
        pref = self._ask_user(
            f"我打算搜尋 {symbol} 最新新聞（7 天內）。有特定偏好嗎？",
            options=["使用預設設定", "只看今日新聞", "擴大到一個月"],
        )
        if pref and pref not in ("使用預設設定", "1", "", None):
            task.description += f"\n使用者偏好：{pref}"

        # Step 1: Gather news from multiple sources
        all_news = []

        # Try google_news first
        result = self._use_tool("google_news", {"symbol": symbol, "limit": 5})
        if result.success and result.data:
            if isinstance(result.data, list):
                for news in result.data:
                    news["symbol"] = symbol
                    all_news.append(news)

        # Try aggregate_news if we have too few
        if len(all_news) < 3:
            result2 = self._use_tool("aggregate_news", {"symbol": symbol, "limit": 5})
            if result2.success and result2.data:
                if isinstance(result2.data, list):
                    for news in result2.data:
                        news["symbol"] = symbol
                        all_news.append(news)

        # Step 2: Check if we got anything
        if not all_news:
            return AgentResult(
                success=False,
                message=f"抱歉，無法獲取 {symbol} 的相關新聞。請稍後再試。",
                agent_name=self.name,
            )

        # Step 3: Format news for LLM summarization
        news_text = "\n".join(
            f"- [{n.get('source', 'Unknown')}] {n.get('title', 'No Title')}"
            for n in all_news[:10]
        )

        # Step 4: LLM summarize
        prompt = PromptRegistry.render(
            "news_agent", "summarize",
            symbol=symbol,
            news_items=news_text,
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            summary = response.content
        except Exception as e:
            summary = f"（新聞總結生成失敗：{e}）"

        # Step 5: Format output
        output = self._format_output(all_news[:10], summary)

        # Step 6: Quality assessment
        quality, reason = self._assess_result_quality(output, task)
        if quality == "fail":
            action = self._ask_user(
                f"新聞摘要結果不佳（{reason}），請選擇處理方式：",
                options=["重試", "接受目前結果", "換個搜尋範圍"],
            )
            if action in ("接受目前結果", "2"):
                return AgentResult(success=True, message=output, agent_name=self.name, quality="pass")
            if action in ("換個搜尋範圍", "3"):
                task.description += "\n請擴大搜尋範圍重新查詢"
                return self.execute(task)
            return self._handle_fail(reason, task)

        return AgentResult(
            success=True,
            message=output,
            agent_name=self.name,
            data={"news": all_news, "summary": summary},
            quality=quality,
        )

    def _format_output(self, news_list: list, summary: str) -> str:
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

    def _extract_symbol(self, description: str) -> str:
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
        desc_lower = description.lower()
        for symbol, keywords in crypto_map.items():
            if any(kw in desc_lower for kw in keywords):
                return symbol
        return "BTC"
