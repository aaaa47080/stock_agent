"""
Integration tests for multi-market agent dispatch.
Uses mocked LLM to avoid real API calls.
"""
import pytest
from unittest.mock import MagicMock, patch


def make_mock_llm(content="分析報告"):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


def test_crypto_agent_executes():
    """CryptoAgent can execute with mocked tools."""
    from core.agents.agents.crypto_agent import CryptoAgent
    from core.agents.models import SubTask

    llm = make_mock_llm("BTC 分析：RSI 55，中性偏多")
    tool_registry = MagicMock()
    tool_registry.get.return_value = None  # No tools

    agent = CryptoAgent(llm, tool_registry)
    task  = SubTask(step=1, description="BTC 技術分析", agent="crypto")
    result = agent.execute(task)
    assert result.agent_name == "crypto"


def test_tw_stock_agent_executes():
    """TWStockAgent can execute with mocked tools."""
    from core.agents.agents.tw_stock_agent import TWStockAgent
    from core.agents.models import SubTask

    llm = make_mock_llm("台積電分析報告")
    tool_registry = MagicMock()
    tool_registry.get.return_value = None

    agent = TWStockAgent(llm, tool_registry)
    task  = SubTask(step=1, description="台積電最近走勢", agent="tw_stock")
    result = agent.execute(task)
    assert result.agent_name == "tw_stock"


def test_us_stock_agent_stub():
    """USStockAgent returns stub message."""
    from core.agents.agents.us_stock_agent import USStockAgent
    from core.agents.models import SubTask

    llm = make_mock_llm()
    tool_registry = MagicMock()

    agent  = USStockAgent(llm, tool_registry)
    task   = SubTask(step=1, description="分析 TSM", agent="us_stock")
    result = agent.execute(task)
    assert result.success is True
    assert "TSM" in result.message or "美股" in result.message


def test_universal_resolver_btc():
    """BTC resolves to crypto only."""
    from core.tools.universal_resolver import UniversalSymbolResolver
    r = UniversalSymbolResolver()
    res = r.resolve("BTC")
    assert res["crypto"] == "BTC"
    assert res["tw"] is None


def test_universal_resolver_tw_digit():
    """2330 resolves to tw_stock only."""
    from core.tools.universal_resolver import UniversalSymbolResolver
    r = UniversalSymbolResolver()
    res = r.resolve("2330")
    assert res["tw"] == "2330.TW"
    assert res["crypto"] is None


def test_bootstrap_creates_all_agents():
    """bootstrap() registers all 5 agent types."""
    from core.agents.bootstrap import bootstrap

    mock_llm = make_mock_llm()
    manager  = bootstrap(mock_llm, web_mode=False)

    agent_names = {m.name for m in manager.agent_registry.list_all()}
    assert "crypto"   in agent_names, "CryptoAgent not registered"
    assert "tw_stock" in agent_names, "TWStockAgent not registered"
    assert "chat"     in agent_names, "ChatAgent not registered"
    assert "us_stock" in agent_names, "USStockAgent not registered"
