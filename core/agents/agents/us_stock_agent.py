"""
Agent V4 — US Stock Agent (Full Implementation)

Multi-language US stock analysis with real-time data,
technicals, fundamentals, earnings, and news.

Supports:
- Real-time price data (15-min delayed via Yahoo Finance)
- Technical indicators (RSI, MACD, MA, Bollinger Bands)
- Fundamental analysis (P/E, EPS, ROE, etc.)
- Earnings data and calendar
- Latest news aggregation
- Institutional holdings
- Insider transactions

Languages: zh-TW, zh-CN, en
"""
import json
from langchain_core.messages import HumanMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class USStockAgent:
    """
    美股分析 Agent
    
    提供完整的美股分析功能，包括：
    - 即時價格
    - 技術指標
    - 基本面分析
    - 財報數據
    - 新聞聚合
    """
    
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "us_stock"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute US stock analysis."""
        language = (task.context or {}).get("language", "zh-TW")
        
        # 1. Extract ticker
        ticker = self._extract_ticker(task.description)
        if not ticker or ticker == "UNKNOWN":
            msg_map = {
                "zh-TW": "無法識別美股代號，請提供股票代號（如 AAPL）或公司名稱（如 Apple）。",
                "zh-CN": "无法识别美股代号，请提供股票代号（如 AAPL）或公司名称（如 Apple）。",
                "en": "Unable to recognize US stock ticker. Please provide stock symbol (e.g., AAPL) or company name (e.g., Apple).",
            }
            return AgentResult(
                success=False,
                message=msg_map.get(language, msg_map["zh-TW"]),
                agent_name=self.name,
                quality="fail",
            )

        # 2. Classify intent
        intent = self._classify_intent(task.description)

        # 3. Fetch data
        price_data = self._run_tool("us_stock_price", {"symbol": ticker}) if intent.get("price") else {}
        technical_data = self._run_tool("us_technical_analysis", {"symbol": ticker}) if intent.get("technical") else {}
        fundamentals_data = self._run_tool("us_fundamentals", {"symbol": ticker}) if intent.get("fundamentals") else {}
        earnings_data = self._run_tool("us_earnings", {"symbol": ticker}) if intent.get("earnings") else {}
        news_data = self._run_tool("us_news", {"symbol": ticker, "limit": 5}) if intent.get("news") else []
        institutional_data = self._run_tool("us_institutional_holders", {"symbol": ticker}) if intent.get("institutional") else {}

        # Check if all data fetching failed
        all_empty = not any([
            price_data and not price_data.get("error"),
            technical_data and not technical_data.get("error"),
            fundamentals_data and not fundamentals_data.get("error"),
            earnings_data and not earnings_data.get("error"),
            news_data,
        ])
        
        if all_empty:
            msg_map = {
                "zh-TW": f"無法獲取 {ticker} 的資料，請稍後再試。",
                "zh-CN": f"无法获取 {ticker} 的资料，请稍后再试。",
                "en": f"Unable to fetch data for {ticker}. Please try again later.",
            }
            return AgentResult(
                success=False,
                message=msg_map.get(language, msg_map["zh-TW"]),
                agent_name=self.name,
                quality="fail",
            )

        # 4. Format data for prompt
        def fmt(d):
            if not d:
                return "(Not fetched)" if language == "en" else "（未抓取）"
            if isinstance(d, dict) and d.get("error"):
                error_msg = d.get("error", "Unknown error")
                return f"(Error: {error_msg})" if language == "en" else f"（錯誤：{error_msg}）"
            if isinstance(d, list):
                if not d:
                    return "(No data)" if language == "en" else "（無資料）"
                return "\n".join(
                    f"- [{item.get('title','')} ({item.get('source','')})]({item.get('url','')})"
                    for item in d[:5]
                )
            return json.dumps(d, ensure_ascii=False, indent=2, default=str)

        # Get company name from price_data (yfinance shortName) — no hardcode needed
        company_name = self._get_company_name(ticker, price_data)

        # 5. Render prompt with multi-language support
        prompt = PromptRegistry.render(
            "us_stock_agent", "analysis", language,
            ticker=ticker,
            company_name=company_name,
            query=task.description,
            price_data=fmt(price_data) if price_data and not price_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            technical_data=fmt(technical_data) if technical_data and not technical_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            fundamentals_data=fmt(fundamentals_data) if fundamentals_data and not fundamentals_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            earnings_data=fmt(earnings_data) if earnings_data and not earnings_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            news_data=fmt(news_data),
            institutional_data=fmt(institutional_data) if institutional_data and not institutional_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
        )

        # 6. Generate response
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            # Multi-language prefix
            prefix_map = {
                "zh-TW": f"🇺🇸 **{company_name or ticker} 美股分析**",
                "zh-CN": f"🇺🇸 **{company_name or ticker} 美股分析**",
                "en": f"🇺🇸 **{company_name or ticker} US Stock Analysis**",
            }
            prefix = prefix_map.get(language, prefix_map["zh-TW"])
            
            # Add disclaimer about delayed data
            disclaimer_map = {
                "zh-TW": "\n\n> ⚠️ 註：價格數據延遲 15 分鐘",
                "zh-CN": "\n\n> ⚠️ 注：价格数据延迟 15 分钟",
                "en": "\n\n> ⚠️ Note: Price data is delayed by 15 minutes",
            }
            disclaimer = disclaimer_map.get(language, disclaimer_map["zh-TW"])
            
            analysis_text = f"{prefix}\n\n{response.content}{disclaimer}"
        except Exception as e:
            analysis_text = f"Analysis generation failed: {e}" if language == "en" else f"分析生成失敗：{e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"ticker": ticker, "company_name": company_name},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        """
        Extract US stock ticker from description using LLM as primary resolver.

        Strategy:
        1. Explicit [TICKER] prefix injected by _plan_node (zero-cost fast path)
        2. LLM: "你是美股專家，萃取股票代碼，只回傳代碼，無法辨識回傳 None"
        """
        import re

        # 1. Fast path: explicit prefix "[SMCI] ..." put by _plan_node
        prefix_match = re.match(r'^\[([A-Z]{1,6})\]', description.strip())
        if prefix_match:
            return prefix_match.group(1)

        # 2. LLM as primary extractor — handles any language, any format
        if self.llm:
            try:
                prompt_text = PromptRegistry.render(
                    "us_stock_agent", "extract_symbol",
                    description=description
                )
                response = self.llm.invoke([HumanMessage(content=prompt_text)])
                result = response.content.strip().upper().split()[0]
                if result != "NONE" and re.match(r'^[A-Z]{1,6}$', result):
                    return result
            except Exception:
                pass

        return "UNKNOWN"

    def _get_company_name(self, ticker: str, price_data: dict = None) -> str:
        """Get company name from price_data (yfinance shortName) or return ticker as fallback."""
        if price_data and isinstance(price_data, dict):
            name = price_data.get("name") or price_data.get("shortName") or price_data.get("longName")
            if name and name != ticker:
                return name
        return ticker

    def _classify_intent(self, query: str) -> dict:
        """
        Use LLM to determine which data categories are needed.
        Returns dict with boolean flags for each data category.
        """
        default_full = {
            "price": True, "technical": True, "fundamentals": False,
            "earnings": False, "news": True, "institutional": False,
        }
        if not self.llm:
            return default_full

        try:
            prompt_text = PromptRegistry.render(
                "us_stock_agent", "classify_intent",
                query=query
            )
            response = self.llm.invoke([HumanMessage(content=prompt_text)])
            import json, re
            raw = response.content.strip()
            m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                keys = ["price", "technical", "fundamentals", "earnings", "news", "institutional"]
                return {k: bool(data.get(k, False)) for k in keys}
        except Exception:
            pass

        return default_full

    def _run_tool(self, tool_name: str, args: dict):
        """
        Run a registered tool.
        
        Args:
            tool_name: Name of the tool to run
            args: Arguments to pass to the tool
        
        Returns:
            Tool result or None if failed
        """
        tool = self.tool_registry.get(tool_name, caller_agent=self.name)
        if not tool:
            return None
        try:
            return tool.handler.invoke(args)
        except Exception as e:
            # Return error info for debugging
            return {"error": str(e)}
