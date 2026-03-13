from unittest.mock import MagicMock

from core.agents.base_react_agent import BaseReActAgent
from core.agents.models import SubTask
from core.agents.tool_registry import ToolMetadata


class FakePriceTool:
    name = "get_crypto_price"
    description = "獲取加密貨幣的即時價格"
    args = {"symbol": {"type": "string"}}

    def invoke(self, kwargs):
        return {"symbol": kwargs["symbol"], "price": 123.45}


class DummyAgent(BaseReActAgent):
    @property
    def name(self) -> str:
        return "crypto"


class DummyToolRegistry:
    def list_for_agent(self, _agent_name):
        return [ToolMetadata(
            name="get_crypto_price",
            description="獲取加密貨幣即時價格",
            input_schema={"symbol": "str"},
            handler=FakePriceTool(),
            allowed_agents=["crypto"],
            role="market_lookup",
            priority=100,
        )]


def test_execute_forces_tool_before_llm_when_tool_required():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="BTC 現價為 123.45 美元。")
    agent = DummyAgent(llm, DummyToolRegistry())

    task = SubTask(
        step=1,
        description="BTC 現在多少錢？",
        agent="crypto",
        context={
            "language": "zh-TW",
            "tool_required": True,
            "symbols": {"crypto": "BTC", "tw": None, "us": None},
        },
    )

    result = agent.execute(task)

    assert result.success is True
    assert "123.45" in result.message
    llm.invoke.assert_called_once()


def test_verified_mode_fails_when_required_tool_is_unavailable():
    llm = MagicMock()

    class EmptyRegistry:
        def list_for_agent(self, _agent_name):
            return []

    agent = DummyAgent(llm, EmptyRegistry())
    task = SubTask(
        step=1,
        description="AAPL 現在多少？",
        agent="crypto",
        context={
            "language": "zh-TW",
            "analysis_mode": "verified",
            "tool_required": True,
            "symbols": {"us": "AAPL"},
            "allowed_tools": [],
            "metadata": {
                "market_resolution": {
                    "requires_discovery_lookup": False,
                },
                "query_profile": {
                    "query_type": "price_lookup",
                },
            },
        },
    )

    result = agent.execute(task)

    assert result.success is False
    assert result.quality == "fail"
    assert result.quality_fail_reason == "verified_tool_unavailable"
    assert result.data["query_type"] == "price_lookup"
    assert result.data["resolved_market"] == "us"
    assert result.data["policy_path"] == "market_lookup"
    llm.invoke.assert_not_called()


def test_verified_mode_fails_with_discovery_reason_when_market_resolution_is_missing():
    llm = MagicMock()

    class EmptyRegistry:
        def list_for_agent(self, _agent_name):
            return []

    agent = DummyAgent(llm, EmptyRegistry())
    task = SubTask(
        step=1,
        description="tsm 現在多少？",
        agent="crypto",
        context={
            "language": "zh-TW",
            "analysis_mode": "verified",
            "tool_required": False,
            "allowed_tools": [],
            "metadata": {
                "market_resolution": {
                    "requires_discovery_lookup": True,
                },
                "query_profile": {
                    "query_type": "price_lookup",
                },
            },
        },
    )

    result = agent.execute(task)

    assert result.success is False
    assert result.quality_fail_reason == "verified_discovery_tool_unavailable"
    assert result.data["query_type"] == "price_lookup"
    assert result.data["resolved_market"] is None
    assert result.data["policy_path"] == "discovery_lookup"
    llm.invoke.assert_not_called()
