"""Tests for Professional Agent base classes"""
import pytest
from core.agents_v2.base import AgentState
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
