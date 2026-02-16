"""Tests for Professional Agent base classes"""
import pytest
from abc import ABC
from core.agents_v2.base import AgentState, ProfessionalAgent
from core.agents_v2.models import Viewpoint, DiscussionRound


class TestAgentState:
    """Test AgentState enum values"""

    def test_agent_state_values(self):
        """AgentState should have all required states"""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.ANALYZING.value == "analyzing"
        assert AgentState.DISCUSSING.value == "discussing"
        assert AgentState.WAITING_FEEDBACK.value == "waiting_feedback"
        assert AgentState.COMPLETED.value == "completed"


class TestViewpoint:
    """Test Viewpoint dataclass"""

    def test_viewpoint_creation(self):
        """Viewpoint should be created with required fields"""
        viewpoint = Viewpoint(
            content="BTC 短期偏多",
            confidence=0.75,
            evidence=["RSI 65", "價格高於 MA20"],
            tools_used=["rsi", "macd"]
        )
        assert viewpoint.content == "BTC 短期偏多"
        assert viewpoint.confidence == 0.75
        assert len(viewpoint.evidence) == 2
        assert viewpoint.user_agreed is None

    def test_viewpoint_user_agreed_default(self):
        """user_agreed should default to None"""
        viewpoint = Viewpoint(
            content="test",
            confidence=0.5,
            evidence=[],
            tools_used=[]
        )
        assert viewpoint.user_agreed is None


class TestDiscussionRound:
    """Test DiscussionRound dataclass"""

    def test_discussion_round_creation(self):
        """DiscussionRound should track speaker and content"""
        round_ = DiscussionRound(
            speaker="agent",
            content="我認為技術面偏多",
            type="proposal"
        )
        assert round_.speaker == "agent"
        assert round_.type == "proposal"


class TestProfessionalAgent:
    """Test ProfessionalAgent abstract base class"""

    def test_professional_agent_is_abstract(self):
        """ProfessionalAgent should be abstract"""
        assert issubclass(ProfessionalAgent, ABC)

    def test_cannot_instantiate_directly(self):
        """Should not be able to instantiate ProfessionalAgent directly"""
        with pytest.raises(TypeError):
            ProfessionalAgent(
                expertise="test",
                system_prompt="test prompt"
            )

    def test_concrete_implementation_required(self):
        """Concrete implementation must implement abstract methods"""

        class IncompleteAgent(ProfessionalAgent):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent(
                expertise="test",
                system_prompt="test prompt"
            )

    def test_complete_implementation_works(self):
        """A complete implementation should be instantiable"""

        class CompleteAgent(ProfessionalAgent):
            def select_tools(self, task):
                return []

            def should_participate(self, task):
                return True, "Always participate"

        agent = CompleteAgent(
            expertise="test",
            system_prompt="test prompt"
        )
        assert agent.expertise == "test"
        assert agent.system_prompt == "test prompt"
        assert agent.personality == "balanced"
        assert agent.state == AgentState.IDLE

    def test_agent_has_expected_attributes(self):
        """ProfessionalAgent should have all expected attributes"""

        class TestAgent(ProfessionalAgent):
            def select_tools(self, task):
                return []

            def should_participate(self, task):
                return True, "Always participate"

        agent = TestAgent(
            expertise="technical_analysis",
            system_prompt="You are a technical analyst",
            personality="aggressive"
        )

        assert agent.expertise == "technical_analysis"
        assert agent.system_prompt == "You are a technical analyst"
        assert agent.personality == "aggressive"
        assert agent.state == AgentState.IDLE
        assert agent.available_tools == []
        assert agent.current_viewpoint is None
        assert agent.discussion_history == []
