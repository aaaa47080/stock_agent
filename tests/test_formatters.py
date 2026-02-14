"""
Tests for formatters module
"""
import pytest
from unittest.mock import MagicMock

from core.tools.formatters import (
    format_full_analysis_result,
    format_compact_analysis_result
)


class MockAnalystReport:
    """Mock analyst report object"""
    def __init__(self, analyst_type, bullish_points=None, bearish_points=None):
        self.analyst_type = analyst_type
        self.bullish_points = bullish_points or []
        self.bearish_points = bearish_points or []


class MockDebateJudgment:
    """Mock debate judgment object"""
    def __init__(
        self,
        winning_stance="多頭",
        suggested_action="買入",
        winning_reason="Technical indicators bullish",
        strongest_bull_point="Strong RSI",
        strongest_bear_point="Market uncertainty",
        fatal_flaw=None,
        key_takeaway="Overall positive outlook"
    ):
        self.winning_stance = winning_stance
        self.suggested_action = suggested_action
        self.winning_reason = winning_reason
        self.strongest_bull_point = strongest_bull_point
        self.strongest_bear_point = strongest_bear_point
        self.fatal_flaw = fatal_flaw
        self.key_takeaway = key_takeaway


class MockTraderDecision:
    """Mock trader decision object"""
    def __init__(
        self,
        decision="買入",
        entry_price=50000.0,
        stop_loss=48000.0,
        take_profit=55000.0,
        position_size=0.1,
        follows_judge=True,
        reasoning="Good entry point",
        key_risk="Market volatility",
        deviation_reason=None
    ):
        self.decision = decision
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.position_size = position_size
        self.follows_judge = follows_judge
        self.reasoning = reasoning
        self.key_risk = key_risk
        self.deviation_reason = deviation_reason


class MockRiskAssessment:
    """Mock risk assessment object"""
    def __init__(
        self,
        risk_level="中",
        assessment="Moderate risk",
        adjusted_position_size=0.08,
        warnings=None
    ):
        self.risk_level = risk_level
        self.assessment = assessment
        self.adjusted_position_size = adjusted_position_size
        self.warnings = warnings or []


class MockFinalApproval:
    """Mock final approval object"""
    def __init__(
        self,
        final_decision="批准買入",
        final_position_size=0.08,
        execution_notes="Execute at market open",
        rationale="Strong fundamentals"
    ):
        self.final_decision = final_decision
        self.final_position_size = final_position_size
        self.execution_notes = execution_notes
        self.rationale = rationale


class TestFormatFullAnalysisResult:
    """Tests for format_full_analysis_result function"""

    def test_basic_result(self):
        """Test basic analysis result formatting"""
        result = {
            'current_price': 50000.0,
            'analyst_reports': [],
            'debate_judgment': None,
            'trader_decision': None,
            'risk_assessment': None,
            'final_approval': None,
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "BTC" in output
        assert "現貨" in output
        assert "1d" in output
        assert "$50000.0000" in output

    def test_with_analyst_reports(self):
        """Test formatting with analyst reports"""
        report1 = MockAnalystReport("技術分析", ["RSI看多"], ["MACD看空"])
        report2 = MockAnalystReport("基本面分析", ["強勁財報"], [])

        result = {
            'current_price': 50000.0,
            'analyst_reports': [report1, report2],
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "技術分析" in output
        assert "基本面分析" in output
        assert "分析師觀點摘要" in output

    def test_with_debate_judgment(self):
        """Test formatting with debate judgment"""
        judgment = MockDebateJudgment()

        result = {
            'current_price': 50000.0,
            'debate_judgment': judgment,
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "多空辯論裁決" in output
        assert "多頭" in output
        assert "買入" in output

    def test_with_trader_decision(self):
        """Test formatting with trader decision"""
        decision = MockTraderDecision()

        result = {
            'current_price': 50000.0,
            'trader_decision': decision,
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "交易決策" in output
        assert "買入" in output
        assert "$50000.0000" in output

    def test_with_risk_assessment(self):
        """Test formatting with risk assessment"""
        risk = MockRiskAssessment(warnings=["High volatility"])

        result = {
            'current_price': 50000.0,
            'risk_assessment': risk,
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "風險評估" in output
        assert "中" in output
        assert "High volatility" in output

    def test_with_final_approval(self):
        """Test formatting with final approval"""
        approval = MockFinalApproval()

        result = {
            'current_price': 50000.0,
            'final_approval': approval,
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "最終審批" in output
        assert "批准買入" in output

    def test_with_news_data(self):
        """Test formatting with news data"""
        result = {
            'current_price': 50000.0,
            'market_data': {
                '新聞資訊': [
                    {'title': 'BTC reaches new high', 'source': 'Reuters', 'url': 'https://example.com'},
                    {'title': 'Market analysis', 'source': 'Bloomberg', 'url': ''}
                ]
            }
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "相關新聞快訊" in output
        assert "BTC reaches new high" in output

    def test_complete_result(self):
        """Test formatting with all components"""
        result = {
            'current_price': 50000.0,
            'analyst_reports': [MockAnalystReport("技術", ["看多"], [])],
            'debate_judgment': MockDebateJudgment(),
            'trader_decision': MockTraderDecision(),
            'risk_assessment': MockRiskAssessment(),
            'final_approval': MockFinalApproval(),
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "BTC" in output
        assert "分析師觀點" in output
        assert "多空辯論" in output
        assert "交易決策" in output
        assert "風險評估" in output
        assert "最終審批" in output

    def test_disclaimer_included(self):
        """Test that disclaimer is included"""
        result = {'current_price': 50000.0, 'market_data': {}}
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "免責聲明" in output

    def test_fatal_flaw_display(self):
        """Test that fatal flaw is displayed when present"""
        judgment = MockDebateJudgment(fatal_flaw="Critical pattern failure")

        result = {
            'current_price': 50000.0,
            'debate_judgment': judgment,
            'market_data': {}
        }
        output = format_full_analysis_result(result, "現貨", "BTC", "1d")

        assert "致命缺陷" in output
        assert "Critical pattern failure" in output


class TestFormatCompactAnalysisResult:
    """Tests for format_compact_analysis_result function"""

    def test_basic_compact_result(self):
        """Test basic compact result formatting"""
        result = {
            'current_price': 50000.0,
            'final_approval': None,
            'trader_decision': None,
            'risk_assessment': None,
            'debate_judgment': None,
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "BTC" in output
        assert "分析結論" in output

    def test_compact_with_final_approval_buy(self):
        """Test compact formatting with buy decision"""
        approval = MockFinalApproval(final_decision="買入")

        result = {
            'current_price': 50000.0,
            'final_approval': approval,
            'trader_decision': MockTraderDecision(),
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "🟢" in output  # Buy emoji
        assert "買入" in output

    def test_compact_with_final_approval_sell(self):
        """Test compact formatting with sell decision"""
        approval = MockFinalApproval(final_decision="賣出")

        result = {
            'current_price': 50000.0,
            'final_approval': approval,
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "🔴" in output  # Sell emoji

    def test_compact_with_risk_level_low(self):
        """Test compact formatting with low risk"""
        risk = MockRiskAssessment(risk_level="低")

        result = {
            'current_price': 50000.0,
            'risk_assessment': risk,
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "🟢" in output  # Low risk emoji
        assert "低" in output

    def test_compact_with_risk_level_high(self):
        """Test compact formatting with high risk"""
        risk = MockRiskAssessment(risk_level="高")

        result = {
            'current_price': 50000.0,
            'risk_assessment': risk,
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "🔴" in output  # High risk emoji

    def test_compact_with_debate_judgment(self):
        """Test compact formatting with debate judgment"""
        judgment = MockDebateJudgment(winning_stance="多頭", suggested_action="進場")

        result = {
            'current_price': 50000.0,
            'debate_judgment': judgment,
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "辯論結論" in output
        assert "多頭勝出" in output

    def test_compact_with_news(self):
        """Test compact formatting with news (limited to 3)"""
        result = {
            'current_price': 50000.0,
            'market_data': {
                '新聞資訊': [
                    {'title': f'News {i}', 'source': 'Test', 'url': ''} for i in range(5)
                ]
            }
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        # Should only show first 3 news items
        assert "News 0" in output
        assert "News 1" in output
        assert "News 2" in output

    def test_compact_disclaimer_included(self):
        """Test that disclaimer is included in compact format"""
        result = {'current_price': 50000.0, 'market_data': {}}
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "免責聲明" in output

    def test_compact_shows_key_numbers(self):
        """Test that compact format shows key trading numbers"""
        decision = MockTraderDecision(
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=55000.0
        )

        result = {
            'current_price': 50000.0,
            'final_approval': MockFinalApproval(),
            'trader_decision': decision,
            'market_data': {}
        }
        output = format_compact_analysis_result(result, "現貨", "BTC", "1d")

        assert "$50000.0000" in output  # Entry
        assert "$48000.0000" in output  # Stop loss
        assert "$55000.0000" in output  # Take profit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
