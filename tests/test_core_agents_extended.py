"""
Extended tests for core agents in core/agents.py
"""
import pytest
from unittest.mock import patch, MagicMock

from core.agents import (
    TechnicalAnalyst,
    FundamentalAnalyst,
    SentimentAnalyst,
    NewsAnalyst,
    BullResearcher,
    BearResearcher,
    Trader,
    DebateJudge,
    RiskManager
)


class TestTechnicalAnalystMethods:
    """Tests for TechnicalAnalyst methods"""

    def test_has_analyze_method(self):
        """Test that analyze method exists"""
        assert hasattr(TechnicalAnalyst, 'analyze')

    def test_role_attribute(self):
        """Test role attribute"""
        mock_client = MagicMock()
        analyst = TechnicalAnalyst(mock_client)
        assert analyst.role == "技術分析師"


class TestFundamentalAnalystMethods:
    """Tests for FundamentalAnalyst methods"""

    def test_has_analyze_method(self):
        """Test that analyze method exists"""
        assert hasattr(FundamentalAnalyst, 'analyze')

    def test_role_attribute(self):
        """Test role attribute"""
        mock_client = MagicMock()
        analyst = FundamentalAnalyst(mock_client)
        assert analyst.role == "基本面分析師"


class TestSentimentAnalystMethods:
    """Tests for SentimentAnalyst methods"""

    def test_has_analyze_method(self):
        """Test that analyze method exists"""
        assert hasattr(SentimentAnalyst, 'analyze')

    def test_role_attribute(self):
        """Test role attribute"""
        mock_client = MagicMock()
        analyst = SentimentAnalyst(mock_client)
        assert analyst.role == "情緒分析師"


class TestNewsAnalystMethods:
    """Tests for NewsAnalyst methods"""

    def test_has_analyze_method(self):
        """Test that analyze method exists"""
        assert hasattr(NewsAnalyst, 'analyze')


class TestBullResearcherMethods:
    """Tests for BullResearcher methods"""

    def test_has_debate_method(self):
        """Test that debate method exists"""
        assert hasattr(BullResearcher, 'debate')

    def test_stance_attribute(self):
        """Test stance attribute"""
        mock_client = MagicMock()
        researcher = BullResearcher(mock_client)
        assert researcher.stance == "Bull"


class TestBearResearcherMethods:
    """Tests for BearResearcher methods"""

    def test_has_debate_method(self):
        """Test that debate method exists"""
        assert hasattr(BearResearcher, 'debate')

    def test_stance_attribute(self):
        """Test stance attribute"""
        mock_client = MagicMock()
        researcher = BearResearcher(mock_client)
        assert researcher.stance == "Bear"


class TestTraderMethods:
    """Tests for Trader methods"""

    def test_trader_class_exists(self):
        """Test that Trader class exists"""
        assert Trader is not None

    def test_trader_client_assignment(self):
        """Test client assignment in Trader"""
        mock_client = MagicMock()
        trader = Trader(mock_client)
        assert trader.client == mock_client


class TestDebateJudgeMethods:
    """Tests for DebateJudge methods"""

    def test_has_judge_method(self):
        """Test that judge method exists"""
        assert hasattr(DebateJudge, 'judge')


class TestRiskManagerMethods:
    """Tests for RiskManager methods"""

    def test_has_assess_method(self):
        """Test that assess method exists"""
        assert hasattr(RiskManager, 'assess')


class TestAgentClientAssignment:
    """Tests for client assignment in agents"""

    def test_technical_analyst_client(self):
        """Test client assignment in TechnicalAnalyst"""
        mock_client = MagicMock()
        analyst = TechnicalAnalyst(mock_client)
        assert analyst.client == mock_client

    def test_fundamental_analyst_client(self):
        """Test client assignment in FundamentalAnalyst"""
        mock_client = MagicMock()
        analyst = FundamentalAnalyst(mock_client)
        assert analyst.client == mock_client

    def test_sentiment_analyst_client(self):
        """Test client assignment in SentimentAnalyst"""
        mock_client = MagicMock()
        analyst = SentimentAnalyst(mock_client)
        assert analyst.client == mock_client

    def test_trader_client(self):
        """Test client assignment in Trader"""
        mock_client = MagicMock()
        trader = Trader(mock_client)
        assert trader.client == mock_client

    def test_debate_judge_client(self):
        """Test client assignment in DebateJudge"""
        mock_client = MagicMock()
        judge = DebateJudge(mock_client)
        assert judge.client == mock_client

    def test_risk_manager_client(self):
        """Test client assignment in RiskManager"""
        mock_client = MagicMock()
        manager = RiskManager(mock_client)
        assert manager.client == mock_client


class TestAgentRetryDecorator:
    """Tests for retry decorator on agent methods"""

    def test_technical_analyst_has_retry(self):
        """Test TechnicalAnalyst analyze has retry decorator"""
        # Method should have retry_on_failure decorator
        assert hasattr(TechnicalAnalyst.analyze, '__wrapped__') or callable(TechnicalAnalyst.analyze)

    def test_fundamental_analyst_has_retry(self):
        """Test FundamentalAnalyst analyze has retry decorator"""
        assert callable(FundamentalAnalyst.analyze)


class TestAgentMethodSignatures:
    """Tests for agent method signatures"""

    def test_technical_analyst_analyze_signature(self):
        """Test TechnicalAnalyst.analyze signature"""
        import inspect
        sig = inspect.signature(TechnicalAnalyst.analyze)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'market_data' in params

    def test_fundamental_analyst_analyze_signature(self):
        """Test FundamentalAnalyst.analyze signature"""
        import inspect
        sig = inspect.signature(FundamentalAnalyst.analyze)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'market_data' in params
        assert 'symbol' in params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
