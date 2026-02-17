"""
Agent V4 — FullAnalysisAgent

完整市場分析 Agent：
  技術分析 + 情緒分析 + 基本面分析 + 新聞 → 多空辯論 → 裁決報告
  使用 graph.py 的 debate_report 模式（不執行交易決策）。
"""
import re
from typing import Optional, Tuple

from ..base import SubAgent
from ..models import SubTask, AgentResult


class FullAnalysisAgent(SubAgent):

    @property
    def name(self) -> str:
        return "full_analysis"

    def execute(self, task: SubTask) -> AgentResult:
        """Run full analysis pipeline and return a formatted report."""
        from core.graph import app as graph_app
        from core.tools.helpers import find_available_exchange

        symbol = self._extract_symbol(task.description)
        interval = self._extract_interval(task.description)

        # Pre-execution: warn user about time cost, offer lighter alternative
        confirm = self._ask_user(
            f"即將進行 {symbol} 完整四維分析（技術＋情緒＋基本面＋新聞），耗時較長。確認繼續？",
            options=["確認執行", "改為快速技術分析"],
        )
        if confirm in ("改為快速技術分析", "2"):
            from .tech_agent import TechAgent
            tech = TechAgent(self.llm, list(self.tools.values()), self.hitl)
            tech.hitl_fn = self.hitl_fn
            return tech.execute(task)

        # 查找可用交易所
        exchange, normalized_symbol = find_available_exchange(symbol)
        if not exchange:
            return AgentResult(
                success=False,
                message=f"找不到 {symbol} 的交易對，請確認幣種名稱是否正確。",
                agent_name=self.name,
            )

        print(f"[FullAnalysisAgent] 分析 {normalized_symbol} @ {exchange}, interval={interval}")

        state = {
            "symbol": normalized_symbol,
            "exchange": exchange,
            "interval": interval,
            "limit": 200,
            "market_type": "spot",
            "leverage": 1,
            "include_multi_timeframe": True,
            "short_term_interval": "1h",
            "medium_term_interval": "4h",
            "long_term_interval": "1d",
            # 核心：debate_report 模式 — 跑辯論但不跑交易
            "analysis_mode": "debate_report",
            "perform_trading_decision": False,  # 向後兼容
            "execute_trade": False,
            "selected_analysts": ["technical", "sentiment", "fundamental", "news"],
            "user_llm_client": self.llm,
            "user_provider": "openai",
            "preloaded_data": None,
            "account_balance": None,
        }

        try:
            result = graph_app.invoke(state)
        except Exception as e:
            print(f"[FullAnalysisAgent] graph.invoke 失敗: {e}")
            return AgentResult(
                success=False,
                message=f"分析過程中發生錯誤：{e}",
                agent_name=self.name,
            )

        report = result.get("formatted_report") or self._fallback_report(result, symbol)

        quality, reason = self._assess_result_quality(report, task)
        if quality == "fail":
            fail_result = self._handle_fail(reason, task)
            if fail_result.success and fail_result.quality == "pass":
                fail_result.message = report
            return fail_result

        return AgentResult(
            success=True,
            message=report,
            agent_name=self.name,
            data={"symbol": normalized_symbol, "exchange": exchange, "interval": interval},
            quality="pass",
        )

    def _extract_symbol(self, description: str) -> str:
        """Extract crypto symbol from task description."""
        crypto_map = {
            "BTC": ["btc", "bitcoin", "比特幣"],
            "ETH": ["eth", "ethereum", "以太坊", "以太幣"],
            "SOL": ["sol", "solana"],
            "PI": ["pi", "pi network", "pi幣"],
            "DOGE": ["doge", "dogecoin"],
            "XRP": ["xrp", "ripple"],
            "BNB": ["bnb", "binance"],
            "ADA": ["ada", "cardano"],
            "AVAX": ["avax", "avalanche"],
            "LINK": ["link", "chainlink"],
        }
        desc_lower = description.lower()
        for symbol, keywords in crypto_map.items():
            if any(kw in desc_lower for kw in keywords):
                return symbol

        # Fallback: uppercase 3-5 letter token
        match = re.search(r'\b([A-Z]{2,5})\b', description)
        if match:
            return match.group(1)
        return "BTC"

    def _extract_interval(self, description: str) -> str:
        """Extract time interval from task description."""
        desc_lower = description.lower()
        if any(w in desc_lower for w in ["1小時", "1h", "小時"]):
            return "1h"
        if any(w in desc_lower for w in ["4小時", "4h"]):
            return "4h"
        if any(w in desc_lower for w in ["週", "weekly", "1w"]):
            return "1w"
        return "1d"  # default: daily

    def _fallback_report(self, result: dict, symbol: str) -> str:
        """Build a minimal report if formatted_report is absent."""
        lines = [f"## {symbol} 分析報告\n"]
        judgment = result.get("debate_judgment")
        if judgment:
            winning_stance = getattr(judgment, "winning_stance", "N/A")
            key_takeaway = getattr(judgment, "key_takeaway", "")
            lines.append(f"**裁決方向**: {winning_stance}")
            if key_takeaway:
                lines.append(f"**關鍵結論**: {key_takeaway}")
        else:
            lines.append("分析完成，但無法取得裁決結果。")
        lines.append("\n---\n*本報告由 AI 分析師生成，僅供參考，不構成投資建議。*")
        return "\n".join(lines)
