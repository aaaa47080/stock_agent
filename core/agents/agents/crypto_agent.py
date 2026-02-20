"""
Agent V4 — Crypto Agent

Merged replacement for TechAgent + NewsAgent.
Handles all crypto analysis: technical indicators + news aggregation.
Detects query intent to decide which tools to invoke.
"""
import re
from typing import Optional
from langchain_core.messages import HumanMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class CryptoAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm           = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "crypto"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute crypto analysis (technical and/or news)."""
        symbol = self._extract_symbol(task.description)
        intent = self._classify_intent(task.description)

        raw_indicators = price_data = None
        all_news = []

        # --- Technical tools ---
        if intent.get("technical"):
            ta_tool = self.tool_registry.get("technical_analysis", caller_agent=self.name)
            if ta_tool:
                try:
                    raw_indicators = ta_tool.handler.invoke({"symbol": symbol, "interval": "1d"})
                except Exception:
                    pass

            p_tool = self.tool_registry.get("price_data", caller_agent=self.name)
            if p_tool:
                try:
                    price_data = p_tool.handler.invoke({"symbol": symbol})
                except Exception:
                    pass

        # --- News tools ---
        if intent.get("news"):
            for t_name, t_args in [
                ("google_news",    {"symbol": symbol, "limit": 5}),
                ("aggregate_news", {"symbol": symbol, "limit": 5}),
            ]:
                tool = self.tool_registry.get(t_name, caller_agent=self.name)
                if tool:
                    try:
                        res = tool.handler.invoke(t_args)
                        if isinstance(res, list):
                            all_news.extend(res)
                    except Exception:
                        pass

            # Fallback to web_search
            if not all_news:
                ws = self.tool_registry.get("web_search", caller_agent=self.name)
                if ws:
                    try:
                        res = ws.handler.invoke({"query": f"{symbol} crypto news", "purpose": "news"})
                        all_news.append({"title": "Web Search", "source": "DuckDuckGo", "description": res})
                    except Exception:
                        pass

        # --- Nothing at all → fail ---
        if not raw_indicators and not price_data and not all_news:
            return AgentResult(
                success=False,
                message=f"無法獲取 {symbol} 的資料，請稍後再試。",
                agent_name=self.name,
                quality="fail",
            )

        # --- Format data ---
        indicators = self._parse_indicators(raw_indicators)
        signals    = self._build_signals(indicators)
        ind_text   = self._format_ind_text(raw_indicators)
        price_text = str(price_data)[:500] if price_data else "無數據"
        news_text  = self._format_news(all_news[:8]) if all_news else "（未擷取）"

        prompt = PromptRegistry.render(
            "crypto_agent", "analysis",
            symbol=symbol,
            query=task.description,
            signals=signals,
            indicators=ind_text,
            price_data=price_text,
            news_data=news_text,
        )

        try:
            response      = self.llm.invoke([HumanMessage(content=prompt)])
            analysis_text = f"🔐 **{symbol} 加密貨幣分析**\n\n{response.content}"
        except Exception as e:
            analysis_text = f"分析生成失敗：{e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"symbol": symbol, "indicators": indicators},
            quality="pass",
        )

    def _classify_intent(self, query: str) -> dict:
        q = query.lower()
        tech_kw = ["技術", "rsi", "macd", "均線", "ma", "k線", "走勢", "technical", "指標", "分析"]
        news_kw = ["新聞", "消息", "動態", "最新", "近況", "news", "報導", "利多", "利空"]

        has_tech = any(k in q for k in tech_kw)
        has_news = any(k in q for k in news_kw)

        # Default: fetch both
        if not has_tech and not has_news:
            return {"technical": True, "news": True}
        return {"technical": has_tech, "news": has_news}

    def _extract_symbol(self, description: str) -> str:
        try:
            prompt = (
                f"從以下文字中提取加密貨幣的交易所 ticker 代號（例如 BTC、ETH、PI、SOL）。"
                f"只回覆 ticker 本身（純英文大寫縮寫），不要其他文字。若無法識別則回覆 BTC。\n\n文字：{description}"
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip().upper().split()[0]
        except Exception:
            return "BTC"

    def _format_ind_text(self, raw) -> str:
        if isinstance(raw, str):  return raw[:1000]
        if isinstance(raw, dict): return "\n".join(f"- {k}: {v}" for k, v in raw.items() if v is not None)
        return "無數據"

    def _parse_indicators(self, raw) -> dict:
        if isinstance(raw, dict): return raw
        if not isinstance(raw, str): return {}
        parsed = {}
        for m in re.finditer(r'\|\s*(RSI\s*\(\d+\)|MACD|MA\d+|MA\s*\d+)\s*\|\s*\$?([-\d.]+)', raw):
            key = re.sub(r'\s*\(\d+\)', '', m.group(1).strip()).replace(' ', '')
            parsed[key] = m.group(2).strip()
        return parsed

    def _build_signals(self, indicators: dict) -> str:
        if not indicators: return "（無可用訊號數據）"
        signals = []
        ma7  = float(indicators.get("MA7")  or indicators.get("ma7")  or 0)
        ma25 = float(indicators.get("MA25") or indicators.get("ma25") or 0)
        if ma7 and ma25:
            signals.append(f"MA7 ({ma7}) {'高於' if ma7 > ma25 else '低於'} MA25 ({ma25})")
        return "\n".join(f"- {s}" for s in signals) if signals else "（無可用訊號數據）"

    def _format_news(self, news_list: list) -> str:
        lines = []
        for n in news_list:
            title = n.get("title", "")
            url   = n.get("url") or n.get("link", "")
            src   = n.get("source", "")
            if url:
                lines.append(f"- [{title}]({url}) _({src})_")
            else:
                lines.append(f"- {title} _({src})_")
        return "\n".join(lines) if lines else "（無新聞資料）"
