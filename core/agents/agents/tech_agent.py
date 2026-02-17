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

from ..base import SubAgent
from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class TechAgent(SubAgent):

    @property
    def name(self) -> str:
        return "technical"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute technical analysis for the symbol in task.description."""
        symbol = self._extract_symbol(task.description)

        # Pre-execution: ask user for preferences
        pref = self._ask_user(
            f"我打算分析 {symbol}（RSI、MACD、布林帶）。您有特定偏好嗎？",
            options=["使用預設指標", "聚焦短線（日線）", "聚焦長線（週線）"],
        )
        if pref and pref not in ("使用預設指標", "1", "", None):
            task.description += f"\n使用者偏好：{pref}"

        # Step 1: Get technical indicators (V3 tools return strings)
        raw_indicators = None
        ta_result = self._use_tool("technical_analysis", {"symbol": symbol, "interval": "1d"})
        if ta_result.success and ta_result.data:
            raw_indicators = ta_result.data

        # Step 2: Get price data
        raw_price = None
        price_result = self._use_tool("price_data", {"symbol": symbol})
        if price_result.success and price_result.data:
            raw_price = price_result.data

        # Step 3: Check if we have enough data
        if not raw_indicators and not raw_price:
            return AgentResult(
                success=False,
                message=f"抱歉，無法獲取 {symbol} 的技術分析數據。請稍後再試。",
                agent_name=self.name,
            )

        # Step 4: Parse indicators into dict (handles both string & dict)
        indicators = self._parse_indicators(raw_indicators)

        # Step 5: Build pre-computed signals (the key V4 improvement)
        signals = self._build_signals(indicators)

        # Step 6: Format data for prompt
        # For indicators text: prefer original formatted string from V3 tool
        if isinstance(raw_indicators, str):
            ind_text = raw_indicators[:1000]
        elif isinstance(raw_indicators, dict):
            ind_text = "\n".join(
                f"- {k}: {v}" for k, v in raw_indicators.items() if v is not None
            )
        else:
            ind_text = "無數據"

        price_text = "無數據"
        if raw_price:
            price_text = str(raw_price)[:500]

        # Step 7: Generate analysis via LLM
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
            analysis_text = f"📊 **{symbol} 技術分析**\n\n{signals}\n\n指標：\n{ind_text}\n\n（LLM 分析失敗：{e}）"

        # Step 8: Quality assessment
        quality, reason = self._assess_result_quality(analysis_text, task)
        if quality == "fail":
            action = self._ask_user(
                f"分析結果不佳（{reason}），請選擇處理方式：",
                options=["重試", "接受目前結果", "換個分析方向"],
            )
            if action in ("接受目前結果", "2"):
                return AgentResult(success=True, message=analysis_text, agent_name=self.name, quality="pass")
            if action in ("換個分析方向", "3"):
                task.description += "\n請從不同角度重新分析"
                return self.execute(task)
            return self._handle_fail(reason, task)

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"indicators": indicators, "price_data": raw_price},
            quality=quality,
        )

    def _parse_indicators(self, raw) -> dict:
        """Parse indicator data — handles both dict and V3 Markdown string."""
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}

        parsed = {}
        # Parse from Markdown table: | RSI (14) | 30.80 | ...
        for match in re.finditer(
            r'\|\s*(RSI\s*\(\d+\)|MACD|MA\d+|MA\s*\d+|布林帶[上下]軌)\s*\|\s*\$?([-\d.]+)',
            raw,
        ):
            key = match.group(1).strip()
            val = match.group(2).strip()
            # Normalize key names
            key_norm = re.sub(r'\s*\(\d+\)', '', key).replace(' ', '')
            parsed[key_norm] = val

        # Also parse: - **當前價格**: $1987.2100
        price_match = re.search(r'當前價格[:\s]*\$?([\d,.]+)', raw)
        if price_match:
            parsed['current_price'] = price_match.group(1).replace(',', '')

        # Parse: - **波動率**: 3.63%
        vol_match = re.search(r'波動率[:\s]*([\d.]+)%', raw)
        if vol_match:
            parsed['volatility'] = vol_match.group(1)

        return parsed

    def _build_signals(self, indicators: dict) -> str:
        """
        Compute MA/RSI comparisons in CODE, not LLM.
        This fixes the hallucination bug from V3.
        """
        if not indicators:
            return "（無可用訊號數據）"

        signals = []

        ma7 = indicators.get("MA7") or indicators.get("ma7")
        ma25 = indicators.get("MA25") or indicators.get("ma25")
        if ma7 and ma25:
            try:
                ma7f, ma25f = float(ma7), float(ma25)
                if ma7f > ma25f:
                    signals.append(f"MA7 ({ma7f:.4f}) 高於 MA25 ({ma25f:.4f})，短期趨勢偏多")
                else:
                    signals.append(f"MA7 ({ma7f:.4f}) 低於 MA25 ({ma25f:.4f})，短期趨勢偏空")
            except (ValueError, TypeError):
                pass

        rsi = indicators.get("RSI") or indicators.get("rsi")
        if rsi:
            try:
                rsif = float(rsi)
                if rsif > 70:
                    signals.append(f"RSI ({rsif:.1f}) 超買區，注意回調風險")
                elif rsif < 30:
                    signals.append(f"RSI ({rsif:.1f}) 超賣區，可能反彈")
                else:
                    signals.append(f"RSI ({rsif:.1f}) 中性區間")
            except (ValueError, TypeError):
                pass

        # MACD signal
        macd = indicators.get("MACD") or indicators.get("macd")
        if macd:
            try:
                macdf = float(macd)
                if macdf > 0:
                    signals.append(f"MACD ({macdf:.4f}) 正值，多頭動能")
                else:
                    signals.append(f"MACD ({macdf:.4f}) 負值，空頭動能")
            except (ValueError, TypeError):
                pass

        return "\n".join(f"- {s}" for s in signals) if signals else "（無可用訊號數據）"

    def _extract_symbol(self, description: str) -> str:
        """Extract crypto symbol from task description."""
        crypto_map = {
            'BTC': ['btc', 'bitcoin', '比特幣'],
            'ETH': ['eth', 'ethereum', '以太坊'],
            'SOL': ['sol', 'solana'],
            'PI': ['pi', 'pi network', 'pi幣'],
            'DOGE': ['doge', 'dogecoin'],
            'XRP': ['xrp', 'ripple'],
            'BNB': ['bnb', 'binance'],
        }
        desc_lower = description.lower()
        for symbol, keywords in crypto_map.items():
            if any(kw in desc_lower for kw in keywords):
                return symbol
        return "BTC"  # default
