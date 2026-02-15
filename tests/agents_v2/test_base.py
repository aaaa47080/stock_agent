"""Tests for Professional Agent base classes"""
import pytest
from core.agents_v2.base import AgentState


class TestAgentState:
    """Test AgentState enum values"""

    def test_agent_state_values(self):
        """AgentState should have all required states"""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.ANALYZING.value == "analyzing"
        assert AgentState.DISCUSSING.value == "discussing"
        assert AgentState.WAITING_FEEDBACK.value == "waiting_feedback"
        assert AgentState.COMPLETED.value == "completed"
