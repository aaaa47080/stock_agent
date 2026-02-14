"""
Tests for core Pydantic models in core/models.py
"""
import pytest
from pydantic import ValidationError

from core.models import (
    TaskAnalysis,
    SubTask,
    TaskPlan,
    MultiTimeframeData,
    AnalystReport,
    ResearcherDebate,
    FactCheckResult,
    TraderDecision,
    RiskAssessment,
    FinalApproval,
    DebateJudgment
)


class TestTaskAnalysis:
    """Tests for TaskAnalysis model"""

    def test_required_fields(self):
        """Test required fields"""
        analysis = TaskAnalysis(
            is_complex=True,
            assigned_agent="crypto_agent"
        )
        assert analysis.is_complex is True
        assert analysis.assigned_agent == "crypto_agent"

    def test_default_values(self):
        """Test default values"""
        analysis = TaskAnalysis(
            is_complex=False,
            assigned_agent="default_agent"
        )
        assert analysis.complexity_reason == ""
        assert analysis.symbols == []
        assert analysis.confidence == 0.8
        assert analysis.original_question == ""

    def test_custom_values(self):
        """Test with custom values"""
        analysis = TaskAnalysis(
            is_complex=True,
            complexity_reason="Multi-step analysis required",
            assigned_agent="trading_agent",
            symbols=["BTC", "ETH"],
            confidence=0.95,
            original_question="What is BTC price?"
        )
        assert analysis.symbols == ["BTC", "ETH"]
        assert analysis.confidence == 0.95

    def test_confidence_boundary_values(self):
        """Test confidence field boundaries (ge=0, le=1)"""
        # Minimum
        analysis = TaskAnalysis(is_complex=True, assigned_agent="agent", confidence=0.0)
        assert analysis.confidence == 0.0

        # Maximum
        analysis = TaskAnalysis(is_complex=True, assigned_agent="agent", confidence=1.0)
        assert analysis.confidence == 1.0

    def test_confidence_out_of_range(self):
        """Test that confidence out of range raises ValidationError"""
        with pytest.raises(ValidationError):
            TaskAnalysis(is_complex=True, assigned_agent="agent", confidence=-0.1)

        with pytest.raises(ValidationError):
            TaskAnalysis(is_complex=True, assigned_agent="agent", confidence=1.1)


class TestSubTask:
    """Tests for SubTask model"""

    def test_required_fields(self):
        """Test required fields"""
        task = SubTask(
            id="task_1",
            description="Analyze BTC",
            assigned_agent="analyst"
        )
        assert task.id == "task_1"
        assert task.description == "Analyze BTC"
        assert task.assigned_agent == "analyst"

    def test_default_values(self):
        """Test default values"""
        task = SubTask(id="task_1", description="Test", assigned_agent="agent")
        assert task.tools_hint == []
        assert task.dependencies == []
        assert task.status == "pending"
        assert task.result is None
        assert task.symbol is None
        assert task.priority == 5

    def test_valid_status_values(self):
        """Test valid status values"""
        for status in ["pending", "in_progress", "completed", "failed"]:
            task = SubTask(
                id="task_1",
                description="Test",
                assigned_agent="agent",
                status=status
            )
            assert task.status == status

    def test_custom_values(self):
        """Test with custom values"""
        task = SubTask(
            id="task_2",
            description="Complex analysis",
            assigned_agent="expert_agent",
            tools_hint=["technical_analysis", "news_analysis"],
            dependencies=["task_1"],
            status="in_progress",
            result="Partial result",
            symbol="ETH",
            priority=1
        )
        assert task.tools_hint == ["technical_analysis", "news_analysis"]
        assert task.dependencies == ["task_1"]
        assert task.priority == 1


class TestTaskPlan:
    """Tests for TaskPlan model"""

    def test_required_fields(self):
        """Test required fields"""
        plan = TaskPlan(original_question="What is BTC price?")
        assert plan.original_question == "What is BTC price?"

    def test_default_values(self):
        """Test default values"""
        plan = TaskPlan(original_question="Test question")
        assert plan.is_complex is False
        assert plan.complexity_reason == ""
        assert plan.subtasks == []
        assert plan.execution_strategy == "parallel"
        assert plan.estimated_steps == 1

    def test_valid_execution_strategies(self):
        """Test valid execution strategy values"""
        for strategy in ["parallel", "sequential", "mixed", "direct"]:
            plan = TaskPlan(
                original_question="Test",
                execution_strategy=strategy
            )
            assert plan.execution_strategy == strategy

    def test_with_subtasks(self):
        """Test with subtasks"""
        subtask = SubTask(
            id="sub_1",
            description="Analyze",
            assigned_agent="agent"
        )
        plan = TaskPlan(
            original_question="Test",
            subtasks=[subtask]
        )
        assert len(plan.subtasks) == 1


class TestMultiTimeframeData:
    """Tests for MultiTimeframeData model"""

    def test_all_none_defaults(self):
        """Test that all fields default to None"""
        data = MultiTimeframeData()
        assert data.short_term is None
        assert data.medium_term is None
        assert data.long_term is None
        assert data.overall_trend is None

    def test_with_data(self):
        """Test with actual data"""
        data = MultiTimeframeData(
            short_term={"trend": "bullish"},
            medium_term={"trend": "neutral"},
            long_term={"trend": "bearish"},
            overall_trend={"consensus": "neutral"}
        )
        assert data.short_term["trend"] == "bullish"
        assert data.long_term["trend"] == "bearish"


class TestAnalystReport:
    """Tests for AnalystReport model"""

    def test_required_fields(self):
        """Test required fields"""
        report = AnalystReport(
            analyst_type="technical",
            summary="This is a detailed analysis of the market conditions.",
            key_findings=["RSI is overbought", "MACD shows bearish divergence"],
            confidence=75.0
        )
        assert report.analyst_type == "technical"
        assert len(report.key_findings) == 2

    def test_default_values(self):
        """Test default values"""
        report = AnalystReport(
            analyst_type="fundamental",
            summary="A" * 50,  # min_length=50
            key_findings=[],
            confidence=50.0
        )
        assert report.bullish_points == []
        assert report.bearish_points == []
        assert report.multi_timeframe_analysis is None

    def test_min_length_summary(self):
        """Test that summary must be at least 50 characters"""
        with pytest.raises(ValidationError):
            AnalystReport(
                analyst_type="technical",
                summary="Too short",  # Less than 50 chars
                key_findings=[],
                confidence=50.0
            )

    def test_confidence_boundaries(self):
        """Test confidence boundaries (ge=0, le=100)"""
        report = AnalystReport(
            analyst_type="test",
            summary="A" * 50,
            key_findings=[],
            confidence=0.0
        )
        assert report.confidence == 0.0

        report = AnalystReport(
            analyst_type="test",
            summary="A" * 50,
            key_findings=[],
            confidence=100.0
        )
        assert report.confidence == 100.0


class TestResearcherDebate:
    """Tests for ResearcherDebate model"""

    def test_required_fields(self):
        """Test required fields"""
        debate = ResearcherDebate(
            researcher_stance="Bull",
            argument="This is a detailed argument supporting the bullish case for the asset based on strong technical indicators and positive market momentum trends.",
            key_points=["Strong fundamentals", "Positive momentum"],
            confidence=80.0
        )
        assert debate.researcher_stance == "Bull"
        assert debate.round_number == 1

    def test_valid_stances(self):
        """Test valid stance values"""
        for stance in ["Bull", "Bear", "Neutral"]:
            debate = ResearcherDebate(
                researcher_stance=stance,
                argument="A" * 100,
                key_points=[],
                confidence=50.0
            )
            assert debate.researcher_stance == stance

    def test_min_length_argument(self):
        """Test that argument must be at least 100 characters"""
        with pytest.raises(ValidationError):
            ResearcherDebate(
                researcher_stance="Bull",
                argument="Too short argument",
                key_points=[],
                confidence=50.0
            )


class TestFactCheckResult:
    """Tests for FactCheckResult model"""

    def test_required_fields(self):
        """Test required fields"""
        result = FactCheckResult(
            is_accurate=True,
            confidence_score=95.0,
            comment="Data is accurate"
        )
        assert result.is_accurate is True
        assert result.confidence_score == 95.0

    def test_default_corrections(self):
        """Test default corrections list"""
        result = FactCheckResult(
            is_accurate=True,
            confidence_score=100.0,
            comment="All good"
        )
        assert result.corrections == []

    def test_with_corrections(self):
        """Test with corrections"""
        result = FactCheckResult(
            is_accurate=False,
            corrections=["Price was incorrect", "Date was wrong"],
            confidence_score=30.0,
            comment="Multiple errors found"
        )
        assert len(result.corrections) == 2


class TestTraderDecision:
    """Tests for TraderDecision model"""

    def test_required_fields(self):
        """Test required fields"""
        decision = TraderDecision(
            decision="Buy",
            reasoning="Based on strong technical indicators and positive momentum.",
            position_size=0.1,
            follows_judge=True,
            key_risk="Market volatility"
        )
        assert decision.decision == "Buy"
        assert decision.follows_judge is True

    def test_valid_decisions(self):
        """Test valid decision values"""
        for dec in ["Buy", "Sell", "Hold", "Long", "Short"]:
            decision = TraderDecision(
                decision=dec,
                reasoning="A" * 20,
                position_size=0.1,
                follows_judge=True,
                key_risk="Risk"
            )
            assert decision.decision == dec

    def test_position_size_boundaries(self):
        """Test position size boundaries (ge=0, le=1)"""
        decision = TraderDecision(
            decision="Buy",
            reasoning="A" * 20,
            position_size=0.0,
            follows_judge=True,
            key_risk="Risk"
        )
        assert decision.position_size == 0.0

        decision = TraderDecision(
            decision="Buy",
            reasoning="A" * 20,
            position_size=1.0,
            follows_judge=True,
            key_risk="Risk"
        )
        assert decision.position_size == 1.0

    def test_leverage_boundaries(self):
        """Test leverage boundaries (ge=1, le=125)"""
        decision = TraderDecision(
            decision="Long",
            reasoning="A" * 20,
            position_size=0.1,
            leverage=1,
            follows_judge=True,
            key_risk="Risk"
        )
        assert decision.leverage == 1

        decision = TraderDecision(
            decision="Long",
            reasoning="A" * 20,
            position_size=0.1,
            leverage=125,
            follows_judge=True,
            key_risk="Risk"
        )
        assert decision.leverage == 125

    def test_min_length_reasoning(self):
        """Test that reasoning must be at least 20 characters"""
        with pytest.raises(ValidationError):
            TraderDecision(
                decision="Buy",
                reasoning="Too short",
                position_size=0.1,
                follows_judge=True,
                key_risk="Risk"
            )


class TestRiskAssessment:
    """Tests for RiskAssessment model"""

    def test_required_fields(self):
        """Test required fields"""
        assessment = RiskAssessment(
            risk_level="中風險",
            assessment="The risk level is moderate based on current market conditions.",
            warnings=["High volatility expected"],
            suggested_adjustments="Reduce position size",
            approve=True,
            adjusted_position_size=0.05
        )
        assert assessment.risk_level == "中風險"
        assert assessment.approve is True

    def test_valid_risk_levels(self):
        """Test valid risk level values"""
        levels = ['低風險', '中低風險', '中風險', '中高風險', '高風險', '極高風險']
        for level in levels:
            assessment = RiskAssessment(
                risk_level=level,
                assessment="A" * 20,
                warnings=[],
                suggested_adjustments="None",
                approve=True,
                adjusted_position_size=0.1
            )
            assert assessment.risk_level == level

    def test_min_length_assessment(self):
        """Test that assessment must be at least 20 characters"""
        with pytest.raises(ValidationError):
            RiskAssessment(
                risk_level="中風險",
                assessment="Too short",
                warnings=[],
                suggested_adjustments="None",
                approve=True,
                adjusted_position_size=0.1
            )


class TestFinalApproval:
    """Tests for FinalApproval model"""

    def test_required_fields(self):
        """Test required fields"""
        approval = FinalApproval(
            approved=True,
            final_decision="Execute buy order",
            final_position_size=0.1,
            execution_notes="Execute at market open",
            rationale="Strong buy signal confirmed"
        )
        assert approval.approved is True
        assert approval.final_position_size == 0.1

    def test_optional_leverage(self):
        """Test optional leverage field"""
        approval = FinalApproval(
            approved=True,
            final_decision="Execute",
            final_position_size=0.1,
            execution_notes="Notes",
            rationale="Rationale",
            approved_leverage=10
        )
        assert approval.approved_leverage == 10

    def test_leverage_boundaries(self):
        """Test leverage boundaries"""
        # Minimum
        approval = FinalApproval(
            approved=True,
            final_decision="Execute",
            final_position_size=0.1,
            execution_notes="Notes",
            rationale="Rationale",
            approved_leverage=1
        )
        assert approval.approved_leverage == 1

        # Maximum
        approval = FinalApproval(
            approved=True,
            final_decision="Execute",
            final_position_size=0.1,
            execution_notes="Notes",
            rationale="Rationale",
            approved_leverage=125
        )
        assert approval.approved_leverage == 125


class TestDebateJudgment:
    """Tests for DebateJudgment model"""

    def test_required_fields(self):
        """Test required fields"""
        judgment = DebateJudgment(
            bull_evaluation="Bull case has strong momentum arguments.",
            bear_evaluation="Bear case raises valid valuation concerns.",
            neutral_evaluation="Neutral stance highlights market uncertainty.",
            strongest_bull_point="Strong institutional adoption",
            strongest_bear_point="Regulatory concerns",
            winning_stance="Bull",
            winning_reason="Bull arguments are more convincing.",
            suggested_action="適度做多",
            action_rationale="Moderate bullish outlook",
            key_takeaway="Market shows upward momentum"
        )
        assert judgment.winning_stance == "Bull"
        assert judgment.fatal_flaw is None

    def test_valid_winning_stances(self):
        """Test valid winning stance values"""
        for stance in ["Bull", "Bear", "Neutral", "Tie"]:
            judgment = DebateJudgment(
                bull_evaluation="A" * 10,
                bear_evaluation="A" * 10,
                neutral_evaluation="A" * 10,
                strongest_bull_point="Point",
                strongest_bear_point="Point",
                winning_stance=stance,
                winning_reason="A" * 10,
                suggested_action="觀望",
                action_rationale="Rationale",
                key_takeaway="Takeaway"
            )
            assert judgment.winning_stance == stance

    def test_valid_suggested_actions(self):
        """Test valid suggested action values"""
        actions = ['強烈做多', '適度做多', '觀望', '適度做空', '強烈做空']
        for action in actions:
            judgment = DebateJudgment(
                bull_evaluation="A" * 10,
                bear_evaluation="A" * 10,
                neutral_evaluation="A" * 10,
                strongest_bull_point="Point",
                strongest_bear_point="Point",
                winning_stance="Bull",
                winning_reason="A" * 10,
                suggested_action=action,
                action_rationale="Rationale",
                key_takeaway="Takeaway"
            )
            assert judgment.suggested_action == action

    def test_min_length_evaluations(self):
        """Test that evaluations must be at least 10 characters"""
        with pytest.raises(ValidationError):
            DebateJudgment(
                bull_evaluation="Short",  # Less than 10
                bear_evaluation="A" * 10,
                neutral_evaluation="A" * 10,
                strongest_bull_point="Point",
                strongest_bear_point="Point",
                winning_stance="Bull",
                winning_reason="A" * 10,
                suggested_action="觀望",
                action_rationale="Rationale",
                key_takeaway="Takeaway"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
