"""Tests for Orchestrator"""
import pytest
from core.agents_v2.orchestrator import Orchestrator


class TestOrchestrator:
    """Test Orchestrator class"""

    def test_orchestrator_creation(self):
        """Orchestrator should be created with empty agents"""
        orchestrator = Orchestrator()
        assert orchestrator.agents == {}
        # conversation_memory will be initialized in Phase 3
        assert orchestrator.conversation_memory is None
        assert orchestrator.hitl_manager is None
        assert orchestrator.codebook is None
        assert orchestrator.feedback_collector is None

    def test_register_agent(self):
        """Orchestrator should be able to register agents"""
        from core.agents_v2.technical import TechnicalAgent

        orchestrator = Orchestrator()
        agent = TechnicalAgent()
        orchestrator.register_agent(agent)

        assert "technical_analysis" in orchestrator.agents
        assert orchestrator.agents["technical_analysis"] == agent

    def test_unregister_agent(self):
        """Orchestrator should be able to unregister agents"""
        from core.agents_v2.technical import TechnicalAgent

        orchestrator = Orchestrator()
        agent = TechnicalAgent()
        orchestrator.register_agent(agent)

        result = orchestrator.unregister_agent("technical_analysis")
        assert result is True
        assert "technical_analysis" not in orchestrator.agents

    def test_get_agent(self):
        """Orchestrator should be able to get agent by expertise"""
        from core.agents_v2.technical import TechnicalAgent

        orchestrator = Orchestrator()
        agent = TechnicalAgent()
        orchestrator.register_agent(agent)

        retrieved = orchestrator.get_agent("technical_analysis")
        assert retrieved == agent
