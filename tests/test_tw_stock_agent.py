"""Tests for TWStockAgent."""
import pytest
from unittest.mock import MagicMock, patch
from core.agents.agents.tw_stock_agent import TWStockAgent
from core.agents.models import SubTask, AgentResult


def make_agent(mock_llm=None):
    if mock_llm is None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="台積電分析報告")
    tool_registry = MagicMock()
    tool_registry.get.return_value = None  # No tools available
    return TWStockAgent(mock_llm, tool_registry)


def test_agent_name():
    agent = make_agent()
    assert agent.name == "tw_stock"


def test_execute_returns_agent_result():
    agent = make_agent()
    task = SubTask(step=1, description="台積電技術分析", agent="tw_stock")
    result = agent.execute(task)
    assert isinstance(result, AgentResult)
    assert result.agent_name == "tw_stock"


def test_extract_ticker_from_code():
    agent = make_agent()
    ticker = agent._extract_ticker("請分析 2330")
    assert ticker == "2330.TW"


def test_extract_ticker_from_name():
    agent = make_agent()
    # With resolver mocked
    with patch.object(agent.resolver, 'resolve', return_value="2330.TW"):
        ticker = agent._extract_ticker("台積電最近怎樣")
        assert ticker == "2330.TW"


def test_execute_no_data_returns_failure():
    agent = make_agent()
    task = SubTask(step=1, description="2330 分析", agent="tw_stock")
    result = agent.execute(task)
    # Even with no tools, should return an AgentResult (not throw)
    assert isinstance(result, AgentResult)
