"""Tests for Orchestrator"""
import pytest
from core.agents_v2.orchestrator import Orchestrator
from core.agents_v2.task import Task, TaskType


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


class TestOrchestratorTaskParsing:
    """Test Orchestrator task parsing"""

    def test_parse_simple_price_query(self):
        """Should parse simple price query correctly"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("BTC 現價多少")
        assert task.type == TaskType.SIMPLE_PRICE
        assert "BTC" in task.symbols

    def test_parse_analysis_query(self):
        """Should parse analysis query correctly"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("分析 ETH 技術面")
        assert task.type == TaskType.ANALYSIS
        assert "ETH" in task.symbols

    def test_parse_deep_analysis_query(self):
        """Should parse deep analysis query correctly"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("深度分析 SOL，包含多空辯論")
        assert task.type == TaskType.DEEP_ANALYSIS
        assert "SOL" in task.symbols

    def test_parse_multiple_symbols(self):
        """Should extract multiple symbols"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("比較 BTC 和 ETH")
        assert "BTC" in task.symbols
        assert "ETH" in task.symbols

    def test_parse_analysis_depth(self):
        """Should detect analysis depth"""
        orchestrator = Orchestrator()

        task_deep = orchestrator.parse_task("深度分析 BTC")
        assert task_deep.analysis_depth == "deep"

        task_quick = orchestrator.parse_task("快速看一眼 ETH")
        assert task_quick.analysis_depth == "quick"

    def test_parse_needs_backtest(self):
        """Should detect backtest requirement"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("BTC 歷史回測分析")
        assert task.needs_backtest is True
