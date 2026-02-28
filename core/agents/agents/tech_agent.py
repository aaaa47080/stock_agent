"""
Agent V4 — Tech Agent

技術分析 Agent: RSI, MACD, MA 等指標分析。
Uses _build_signals() to pre-compute indicator comparisons in CODE,
preventing LLM hallucination of numeric values.

NOTE: V3 tools return `.data` as formatted strings (Markdown), not dicts.
      This agent handles both string and dict data formats.
"""
import re
from typing import Optional

from langchain_core.messages import HumanMessage

# from ..base import SubAgent # Removed
from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class TechAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "technical"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute technical analysis for the symbol in task.description."""
        symbol = self._extract_symbol(task.description)

        # Step 1: Get technical indicators
        raw_indicators = None
        # Manual tool execution
        ta_tool = self.tool_registry.get("technical_analysis", caller_agent=self.name)
        if ta_tool:
            try:
                # Direct invoke handler
                res = ta_tool.handler.invoke({"symbol": symbol, "interval": "1d"})
                raw_indicators = res
            except Exception as e:
                pass

        # Step 2: Get price data
        raw_price = None
        p_tool = self.tool_registry.get("price_data", caller_agent=self.name)
        if p_tool:
            try:
                res = p_tool.handler.invoke({"symbol": symbol})
                raw_price = res
            except Exception as e:
                pass

        # Step 3: Check data
        if not raw_indicators and not raw_price:
            # Native Refusal Logic
            return AgentResult(
                success=False,
                message=f"抱歉，無法獲取 {symbol} 的技術分析數據 (Refused: No Data)。",
                agent_name=self.name,
                quality="fail"
            )

        # Step 4: Parse
        indicators = self._parse_indicators(raw_indicators)
        # Step 5: Signals
        signals = self._build_signals(indicators)

        # Format texts
        ind_text = self._format_ind_text(raw_indicators)
        price_text = str(raw_price)[:500] if raw_price else "無數據"

        # Step 7: GEN
        prompt = PromptRegistry.render(
            "tech_agent", "analysis",
            symbol=symbol,
            signals=signals,
            indicators=ind_text,
            price_data=price_text,
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            analysis_text = f"📊 **{symbol} 技術分析**\n\n{response.content}"
        except Exception as e:
            analysis_text = f"📊 **analysis error**: {e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"indicators": indicators},
            quality="pass",
        )

    def _format_ind_text(self, raw_indicators) -> str:
        if isinstance(raw_indicators, str):
            return raw_indicators[:1000]
        elif isinstance(raw_indicators, dict):
            return "\n".join(f"- {k}: {v}" for k, v in raw_indicators.items() if v is not None)
        return "無數據"

    def _parse_indicators(self, raw) -> dict:
        """Parse indicator data."""
        if isinstance(raw, dict): return raw
        if not isinstance(raw, str): return {}
        parsed = {}
        for match in re.finditer(r'\|\s*(RSI\s*\(\d+\)|MACD|MA\d+|MA\s*\d+|布林帶[上下]軌)\s*\|\s*\$?([-\d.]+)', raw):
            key_norm = re.sub(r'\s*\(\d+\)', '', match.group(1).strip()).replace(' ', '')
            parsed[key_norm] = match.group(2).strip()
        return parsed

    def _build_signals(self, indicators: dict) -> str:
        if not indicators: return "（無可用訊號數據）"
        signals = []
        # ... simplified signal logic ...
        ma7 = float(indicators.get("MA7") or indicators.get("ma7") or 0)
        ma25 = float(indicators.get("MA25") or indicators.get("ma25") or 0)
        if ma7 and ma25:
            signals.append(f"MA7 ({ma7}) {'高於' if ma7 > ma25 else '低於'} MA25 ({ma25})")
        return "\n".join(f"- {s}" for s in signals) if signals else "（無可用訊號數據）"

    def _extract_symbol(self, description: str) -> str:
        from langchain_core.messages import HumanMessage
        try:
            prompt_text = PromptRegistry.render(
                "tech_agent", "extract_symbol",
                description=description
            )
            response = self.llm.invoke([HumanMessage(content=prompt_text)])
            return response.content.strip().upper().split()[0]
        except Exception:
            return "BTC"
