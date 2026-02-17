"""
tests/test_graph_no_trading.py

驗證 graph.py 的 analysis_mode routing：
- analysis_only: 分析師後直接結束，不進入辯論/交易
- debate_report: 辯論+裁決後呼叫 format_analysis_report_node，不呼叫 trader/risk/fund
- full_trading: 完整流程（保持舊行為）

所有測試都 mock 節點函式，不需要 OKX API 或真實 LLM。
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────
# Shared mock data
# ─────────────────────────────────────

FAKE_MARKET_DATA = {
    "symbol": "BTC-USDT",
    "current_price": 45000.0,
    "market_type": "spot",
    "price_change_24h": "+1.5%",
}

FAKE_ANALYST_REPORT = MagicMock()
FAKE_ANALYST_REPORT.analyst_type = "technical"
FAKE_ANALYST_REPORT.summary = "測試摘要"
FAKE_ANALYST_REPORT.key_signals = ["RSI 中性"]

FAKE_BULL = MagicMock()
FAKE_BEAR = MagicMock()
FAKE_NEUTRAL = MagicMock()

FAKE_JUDGMENT = MagicMock()
FAKE_JUDGMENT.winning_stance = "neutral"
FAKE_JUDGMENT.key_takeaway = "市場中性，觀望為主"
FAKE_JUDGMENT.confidence_score = 7


def make_base_state(analysis_mode: str) -> dict:
    return {
        "symbol": "BTC-USDT",
        "exchange": "okx",
        "interval": "1d",
        "limit": 200,
        "market_type": "spot",
        "leverage": 1,
        "include_multi_timeframe": False,
        "short_term_interval": "1h",
        "medium_term_interval": "4h",
        "long_term_interval": "1d",
        "analysis_mode": analysis_mode,
        "perform_trading_decision": (analysis_mode == "full_trading"),
        "execute_trade": False,
        "selected_analysts": ["technical"],
        "user_llm_client": MagicMock(),
        "user_provider": "openai",
        "preloaded_data": None,
        "account_balance": None,
        "replan_count": 0,
        "debate_round": 0,
    }


# ─────────────────────────────────────
# Tests
# ─────────────────────────────────────

class TestGraphRouting:
    """Test graph.py routing logic without real API calls."""

    def test_after_analyst_team_router_analysis_only(self):
        """analysis_only 模式應回傳 end_process。"""
        from core.graph import after_analyst_team_router
        state = make_base_state("analysis_only")
        result = after_analyst_team_router(state)
        assert result == "end_process"

    def test_after_analyst_team_router_debate_report(self):
        """debate_report 模式應回傳 proceed_to_debate。"""
        from core.graph import after_analyst_team_router
        state = make_base_state("debate_report")
        result = after_analyst_team_router(state)
        assert result == "proceed_to_debate"

    def test_after_analyst_team_router_full_trading(self):
        """full_trading 模式應回傳 proceed_to_debate。"""
        from core.graph import after_analyst_team_router
        state = make_base_state("full_trading")
        result = after_analyst_team_router(state)
        assert result == "proceed_to_debate"

    def test_after_analyst_team_router_backward_compat_true(self):
        """perform_trading_decision=True 且無 analysis_mode 應退回 proceed_to_debate。"""
        from core.graph import after_analyst_team_router
        state = {
            "perform_trading_decision": True,
            # analysis_mode intentionally absent
        }
        result = after_analyst_team_router(state)
        assert result == "proceed_to_debate"

    def test_after_analyst_team_router_backward_compat_false(self):
        """perform_trading_decision=False 且無 analysis_mode 應退回 end_process。"""
        from core.graph import after_analyst_team_router
        state = {
            "perform_trading_decision": False,
        }
        result = after_analyst_team_router(state)
        assert result == "end_process"

    def test_after_debate_judgment_router_debate_report(self):
        """debate_report 模式應回傳 format_report。"""
        from core.graph import after_debate_judgment_router
        state = make_base_state("debate_report")
        result = after_debate_judgment_router(state)
        assert result == "format_report"

    def test_after_debate_judgment_router_full_trading(self):
        """full_trading 模式應回傳 proceed_to_trader。"""
        from core.graph import after_debate_judgment_router
        state = make_base_state("full_trading")
        result = after_debate_judgment_router(state)
        assert result == "proceed_to_trader"

    def test_format_analysis_report_node_returns_report(self):
        """format_analysis_report_node 應返回含 formatted_report 的 dict。"""
        from core.graph import format_analysis_report_node
        state = make_base_state("debate_report")
        state.update({
            "current_price": 45000.0,
            "market_data": FAKE_MARKET_DATA,
            "analyst_reports": [FAKE_ANALYST_REPORT],
            "debate_judgment": FAKE_JUDGMENT,
        })
        result = format_analysis_report_node(state)
        assert "formatted_report" in result
        report = result["formatted_report"]
        assert isinstance(report, str)
        assert len(report) > 100
        assert "BTC" in report or "45000" in report or "neutral" in report

    def test_format_analysis_report_node_no_judgment(self):
        """沒有 judgment 時 format_analysis_report_node 仍應正常返回。"""
        from core.graph import format_analysis_report_node
        state = make_base_state("debate_report")
        state.update({
            "current_price": 45000.0,
            "market_data": FAKE_MARKET_DATA,
            "analyst_reports": [],
            "debate_judgment": None,
        })
        result = format_analysis_report_node(state)
        assert "formatted_report" in result
        assert isinstance(result["formatted_report"], str)

    def test_agentstate_has_analysis_mode_field(self):
        """AgentState TypedDict 應包含 analysis_mode 和 formatted_report 欄位。"""
        from core.graph import AgentState
        hints = AgentState.__annotations__
        assert "analysis_mode" in hints, "AgentState 缺少 analysis_mode 欄位"
        assert "formatted_report" in hints, "AgentState 缺少 formatted_report 欄位"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
