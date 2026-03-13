from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.manager import ManagerAgent


@pytest.mark.asyncio
async def test_manager_passes_pre_resolved_allowed_tools_to_agent_context():
    llm = MagicMock()
    agent_registry = MagicMock()
    fake_agent = MagicMock()
    agent_registry.get.return_value = fake_agent
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        user_tier="premium",
        user_id="user-1",
    )
    manager._execute_agent = AsyncMock(return_value={
        "message": "ok",
        "success": True,
        "data": {},
        "quality": "pass",
        "quality_fail_reason": None,
    })
    manager.tool_access_resolver = MagicMock()
    manager.tool_access_resolver.resolve_for_agent.return_value = ["tool_a", "tool_b"]
    manager._build_market_resolution_metadata = MagicMock(return_value={"candidates": ["AAPL"]})
    manager._build_query_policy_metadata = MagicMock(return_value={"query_type": "price_lookup"})

    task = MagicMock()
    task.agent = "crypto"
    task.id = "task_1"
    task.name = "查價格"
    task.description = "AAPL 股價是多少"
    task.dependencies = []

    state = {
        "query": "AAPL 股價是多少",
        "history": "",
        "intent_understanding": {"entities": {"us": "AAPL"}},
    }

    result = await manager._execute_single_task(task, state, {})

    assert result["success"] is True
    manager.tool_access_resolver.resolve_for_agent.assert_called_once_with("crypto")

    passed_context = manager._execute_agent.await_args.args[1]
    assert passed_context.allowed_tools == ["tool_a", "tool_b"]


@pytest.mark.asyncio
async def test_manager_passes_analysis_mode_to_agent_context():
    llm = MagicMock()
    agent_registry = MagicMock()
    fake_agent = MagicMock()
    agent_registry.get.return_value = fake_agent
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        user_tier="premium",
        user_id="user-1",
    )
    manager._execute_agent = AsyncMock(return_value={
        "message": "ok",
        "success": True,
        "data": {},
        "quality": "pass",
        "quality_fail_reason": None,
    })
    manager.tool_access_resolver = MagicMock()
    manager.tool_access_resolver.resolve_for_agent.return_value = ["tool_a"]
    manager._build_market_resolution_metadata = MagicMock(return_value={"candidates": ["AAPL"]})
    manager._build_query_policy_metadata = MagicMock(return_value={"query_type": "price_lookup"})

    task = MagicMock()
    task.agent = "crypto"
    task.id = "task_1"
    task.name = "查價格"
    task.description = "AAPL 股價是多少"
    task.dependencies = []

    state = {
        "query": "AAPL 股價是多少",
        "history": "",
        "analysis_mode": "verified",
        "intent_understanding": {"entities": {"us": "AAPL"}},
    }

    await manager._execute_single_task(task, state, {})

    passed_context = manager._execute_agent.await_args.args[1]
    assert passed_context.analysis_mode == "verified"


def test_manager_builds_generic_market_resolution_metadata():
    llm = MagicMock()
    agent_registry = MagicMock()
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
    )

    metadata = manager._build_market_resolution_metadata(
        "tsm 現在多少？",
        {"crypto": None, "tw": None, "us": None},
    )

    assert "tsm" in metadata["candidates"]
    assert metadata["requires_discovery_lookup"] is True


def test_manager_builds_query_policy_metadata_for_price_lookup():
    llm = MagicMock()
    agent_registry = MagicMock()
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
    )

    market_resolution = manager._build_market_resolution_metadata(
        "tsm 現在多少？",
        {"crypto": None, "tw": None, "us": None},
    )
    query_profile = manager._build_query_policy_metadata("tsm 現在多少？", market_resolution)

    assert query_profile["query_type"] == "price_lookup"
    assert query_profile["has_symbol_candidates"] is True
