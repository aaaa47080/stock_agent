"""
Agent V4 — US Stock Agent (STUB)

Placeholder for future US stock analysis.
Currently identifies US stock symbols and returns a "coming soon" message.
"""
import re
from ..models import SubTask, AgentResult


# Simple set of common US stock tickers for identification
_US_PATTERN = re.compile(r'\b([A-Z]{1,5})\b')


class USStockAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "us_stock"

    def execute(self, task: SubTask) -> AgentResult:
        """Return stub response identifying the US stock symbol."""
        description = task.description
        ticker = self._extract_ticker(description)
        exchange = self._guess_exchange(ticker)

        message = (
            f"📈 **美股 {ticker}** ({exchange})\n\n"
            f"美股完整分析功能正在開發中，敬請期待！\n\n"
            f"目前支援：\n"
            f"- 🇹🇼 台股分析（輸入股票代號如 2330 或公司名稱）\n"
            f"- 🔐 加密貨幣分析（BTC、ETH 等）"
        )
        return AgentResult(
            success=True,
            message=message,
            agent_name=self.name,
            data={"ticker": ticker, "exchange": exchange},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        matches = _US_PATTERN.findall(description.upper())
        # Filter out common words that aren't tickers
        stopwords = {"A", "I", "IS", "IN", "OF", "THE", "AND", "OR", "FOR",
                     "BTC", "ETH", "SOL", "ADA", "DOT"}
        for m in matches:
            if m not in stopwords and len(m) >= 2:
                return m
        return "UNKNOWN"

    def _guess_exchange(self, ticker: str) -> str:
        nasdaq_known = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "NFLX"}
        nyse_known   = {"TSM", "JPM", "BAC", "WMT", "XOM", "BRK", "JNJ", "V", "PG"}
        if ticker in nasdaq_known:
            return "NASDAQ"
        if ticker in nyse_known:
            return "NYSE"
        return "NYSE/NASDAQ"
