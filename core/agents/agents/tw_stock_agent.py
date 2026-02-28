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
        language = (task.context or {}).get("language", "zh-TW")  # 獲取用戶語言偏好
        ticker = self._extract_ticker(task.description)
        if not ticker:
            msg_map = {
                "zh-TW": "無法識別台股代號，請提供股票代號（如 2330）或公司名稱（如 台積電）。",
                "zh-CN": "无法识别台股代号，请提供股票代号（如 2330）或公司名称（如 台积电）。",
                "en": "Unable to recognize TW stock ticker. Please provide stock code (e.g., 2330) or company name (e.g., TSMC).",
            }
            return AgentResult(
                success=False,
                message=msg_map.get(language, msg_map["zh-TW"]),
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
                return "（未擷取）" if language == "zh-TW" else "(Not fetched)" if language == "en" else "（未抓取）"
            if isinstance(d, list):
                if not d:
                    return "（無資料）" if language == "zh-TW" else "(No data)" if language == "en" else "（无资料）"
                return "\n".join(
                    f"- [{item.get('title','')}]({item.get('url','')})"
                    f" _({item.get('source','')})_"
                    for item in d[:6]
                )
            return json.dumps(d, ensure_ascii=False, indent=2)

        prompt = PromptRegistry.render(
            "tw_stock_agent", "analysis", language,
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
            
            # Multi-language prefix
            prefix_map = {
                "zh-TW": f"🇹🇼 **{company_name or ticker} 台股分析**",
                "zh-CN": f"🇹🇼 **{company_name or ticker} 台股分析**",
                "en": f"🇹🇼 **{company_name or ticker} TW Stock Analysis**",
            }
            analysis_text = f"{prefix_map.get(language, prefix_map['zh-TW'])}\n\n{response.content}"
        except Exception as e:
            analysis_text = f"分析生成失敗：{e}" if language == "zh-TW" else f"Analysis generation failed: {e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"ticker": ticker, "company_name": company_name},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        """
        Extract TW stock ticker from description.

        Strategy:
        1. Explicit [TICKER] prefix injected by _plan_node (e.g., [2330.TW])
        2. Symbol resolver: numeric code or company name
        3. LLM fallback: "你是台股專家，萃取股票代碼，只回傳代碼，無法辨識回傳 None"
        """
        import re

        # 1. Fast path: explicit prefix "[2330.TW] ..." from _plan_node
        prefix_match = re.match(r'^\[([^\]]+)\]', description.strip())
        if prefix_match:
            candidate = prefix_match.group(1)
            resolved = self.resolver.resolve(candidate)
            if resolved:
                return resolved

        # 2. Symbol resolver: try numeric code, then word-by-word
        digit_match = re.search(r'\b(\d{4,6})\b', description)
        if digit_match:
            resolved = self.resolver.resolve(digit_match.group(1))
            if resolved:
                return resolved

        words = re.split(r'[\s,，。！？、「」【】\[\]]+', description)
        for word in words:
            if 2 <= len(word) <= 8:
                resolved = self.resolver.resolve(word)
                if resolved:
                    return resolved

        # 3. LLM fallback — handles any form of company name
        if self.llm:
            try:
                prompt_text = PromptRegistry.render(
                    "tw_stock_agent", "extract_symbol",
                    description=description
                )
                response = self.llm.invoke([HumanMessage(content=prompt_text)])
                result = response.content.strip().split()[0]
                if result.upper() != "NONE" and re.match(r'^\d{4,6}$', result):
                    resolved = self.resolver.resolve(result)
                    return resolved or result
            except Exception:
                pass

        return ""

    def _get_company_name(self, ticker: str) -> str:
        """Lookup company name from resolved ticker."""
        code = ticker.split(".")[0]
        if self.resolver._cache:
            for s in self.resolver._cache:
                if s["code"] == code:
                    return s["name"]
        return ""

    def _classify_intent(self, query: str) -> dict:
        """
        Use LLM to determine which data categories are needed.
        Returns dict with boolean flags for each data category.
        """
        default_full = {
            "price": True, "technical": True, "fundamentals": False,
            "institutional": False, "news": True,
        }
        if not self.llm:
            return default_full

        try:
            prompt_text = PromptRegistry.render(
                "tw_stock_agent", "classify_intent",
                query=query
            )
            response = self.llm.invoke([HumanMessage(content=prompt_text)])
            import json, re
            raw = response.content.strip()
            m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                keys = ["price", "technical", "fundamentals", "institutional", "news"]
                return {k: bool(data.get(k, False)) for k in keys}
        except Exception:
            pass

        return default_full

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
