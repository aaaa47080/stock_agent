"""
Agent V4 — TW Stock Agent

台股全方位分析：即時價格、技術指標、基本面、籌碼、新聞。
Uses TWSymbolResolver to accept any form of TW stock identifier.
"""
import json
from langchain_core.messages import HumanMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry
from core.tools.tw_symbol_resolver import TWSymbolResolver


class TWStockAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm          = llm_client
        self.tool_registry = tool_registry
        self.resolver      = TWSymbolResolver()

    @property
    def name(self) -> str:
        return "tw_stock"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute TW stock analysis."""
        # 1. Resolve ticker
        ticker = self._extract_ticker(task.description)
        if not ticker:
            return AgentResult(
                success=False,
                message="無法識別台股代號，請提供股票代號（如 2330）或公司名稱（如 台積電）。",
                agent_name=self.name,
                quality="fail",
            )

        company_name = self._get_company_name(ticker)

        # 2. Determine which tools to call based on query intent
        intent = self._classify_intent(task.description)

        # 3. Fetch data (only what's needed)
        price_data        = self._run_tool("tw_stock_price",       {"ticker": ticker})         if intent.get("price")       else {}
        technical_data    = self._run_tool("tw_technical_analysis", {"ticker": ticker})        if intent.get("technical")   else {}
        fundamentals_data = self._run_tool("tw_fundamentals",       {"ticker": ticker})        if intent.get("fundamentals") else {}
        institutional_data = self._run_tool("tw_institutional",     {"ticker": ticker})        if intent.get("institutional") else {}
        news_data         = self._run_tool("tw_news", {"ticker": ticker, "company_name": company_name}) if intent.get("news") else []

        # If nothing fetched at all, refuse
        all_empty = not any([price_data, technical_data, fundamentals_data, institutional_data, news_data])
        if all_empty:
            return AgentResult(
                success=False,
                message=f"無法獲取 {ticker} 的資料，請稍後再試。",
                agent_name=self.name,
                quality="fail",
            )

        # 4. Format data for prompt
        def fmt(d):
            if not d:
                return "（未擷取）"
            if isinstance(d, list):
                if not d:
                    return "（無資料）"
                return "\n".join(
                    f"- [{item.get('title','')}]({item.get('url','')})"
                    f" _({item.get('source','')})_"
                    for item in d[:6]
                )
            return json.dumps(d, ensure_ascii=False, indent=2)

        prompt = PromptRegistry.render(
            "tw_stock_agent", "analysis",
            ticker=ticker,
            company_name=company_name,
            query=task.description,
            price_data=fmt(price_data),
            technical_data=fmt(technical_data),
            fundamentals_data=fmt(fundamentals_data),
            institutional_data=fmt(institutional_data),
            news_data=fmt(news_data),
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            analysis_text = f"🇹🇼 **{company_name or ticker} 台股分析**\n\n{response.content}"
        except Exception as e:
            analysis_text = f"分析生成失敗：{e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"ticker": ticker, "company_name": company_name},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        """Try to extract a TW ticker from the description text."""
        import re

        # Try direct digit match first
        match = re.search(r'\b(\d{4,6})\b', description)
        if match:
            resolved = self.resolver.resolve(match.group(1))
            if resolved:
                return resolved

        # Try resolver on whole description or key noun phrases
        # Split by common delimiters and try each word
        words = re.split(r'[\s,，。！？、「」【】]+', description)
        for word in words:
            if 2 <= len(word) <= 8:
                resolved = self.resolver.resolve(word)
                if resolved:
                    return resolved

        # Try the whole description as a last resort
        resolved = self.resolver.resolve(description[:20])
        return resolved or ""

    def _get_company_name(self, ticker: str) -> str:
        """Lookup company name from resolved ticker."""
        code = ticker.split(".")[0]
        if self.resolver._cache:
            for s in self.resolver._cache:
                if s["code"] == code:
                    return s["name"]
        return ""

    def _classify_intent(self, query: str) -> dict:
        """Determine which data categories are relevant to the query."""
        q = query.lower()

        tech_kw  = ["技術", "rsi", "macd", "kd", "均線", "ma", "k線", "走勢", "technical"]
        fund_kw  = ["基本面", "本益比", "pe", "eps", "獲利", "財報", "殖利率", "stock price"]
        inst_kw  = ["法人", "外資", "投信", "自營", "籌碼", "買超", "賣超"]
        news_kw  = ["新聞", "消息", "動態", "最新", "近況", "利多", "利空", "事件"]
        price_kw = ["價格", "現價", "多少", "price", "報價"]

        has_tech  = any(k in q for k in tech_kw)
        has_fund  = any(k in q for k in fund_kw)
        has_inst  = any(k in q for k in inst_kw)
        has_news  = any(k in q for k in news_kw)
        has_price = any(k in q for k in price_kw)

        # If none specifically detected, fetch price + technical + news (default full view)
        if not any([has_tech, has_fund, has_inst, has_news, has_price]):
            return {"price": True, "technical": True, "fundamentals": False, "institutional": False, "news": True}

        return {
            "price":        has_price or has_tech,
            "technical":    has_tech or (not any([has_fund, has_inst, has_news])),
            "fundamentals": has_fund,
            "institutional": has_inst,
            "news":         has_news,
        }

    def _run_tool(self, tool_name: str, args: dict):
        """Run a registered tool, return result or empty fallback."""
        tool = self.tool_registry.get(tool_name, caller_agent=self.name)
        if not tool:
            return None
        try:
            return tool.handler.invoke(args)
        except Exception as e:
            print(f"[TWStockAgent] {tool_name} failed: {e}")
            return None
