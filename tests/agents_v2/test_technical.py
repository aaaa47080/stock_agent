"""Tests for Technical Agent"""
import pytest
from core.agents_v2.task import Task, TaskType
from core.agents_v2.technical import TechnicalAgent


class TestTask:
    """Test Task model"""

    def test_task_creation(self):
        """Task should be created with required fields"""
        task = Task(
            query="分析 BTC",
            type=TaskType.ANALYSIS,
            symbols=["BTC"],
            timeframe="4h"
        )
        assert task.query == "分析 BTC"
        assert task.type == TaskType.ANALYSIS
        assert task.symbols == ["BTC"]

    def test_task_simple_price_type(self):
        """Task should support simple_price type"""
        task = Task(
            query="BTC 現價多少",
            type=TaskType.SIMPLE_PRICE,
            symbols=["BTC"]
        )
        assert task.type == TaskType.SIMPLE_PRICE


class TestTechnicalAgent:
    """Test TechnicalAgent implementation"""

    def test_technical_agent_creation(self):
        """TechnicalAgent should be created with correct expertise"""
        agent = TechnicalAgent()
        assert agent.expertise == "technical_analysis"
        assert agent.personality == "analytical"
        assert agent.state.value == "idle"

    def test_should_participate_for_analysis(self):
        """TechnicalAgent should participate in analysis tasks"""
        agent = TechnicalAgent()
        task = Task(
            query="分析 BTC 技術面",
            type=TaskType.ANALYSIS,
            symbols=["BTC"]
        )
        should_join, reason = agent.should_participate(task)
        assert should_join is True
        assert "技術分析" in reason

    def test_should_not_participate_for_simple_price(self):
        """TechnicalAgent should not participate in simple price queries"""
        agent = TechnicalAgent()
        task = Task(
            query="BTC 現價多少",
            type=TaskType.SIMPLE_PRICE,
            symbols=["BTC"]
        )
        should_join, reason = agent.should_participate(task)
        assert should_join is False
