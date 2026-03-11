from unittest.mock import MagicMock, AsyncMock

import pytest

from core.agents.agent_registry import AgentRegistry, AgentMetadata
from core.agents.manager import ManagerAgent, MAX_GRAPH_TASKS
from core.agents.tool_registry import ToolRegistry


def build_manager():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="{}")
    agent_registry = AgentRegistry()
    agent_registry.register(object(), AgentMetadata(
        name="crypto",
        display_name="Crypto Agent",
        description="crypto",
        capabilities=["crypto"],
        allowed_tools=[],
        priority=10,
    ))
    agent_registry.register(object(), AgentMetadata(
        name="tw_stock",
        display_name="TW Stock Agent",
        description="tw",
        capabilities=["tw"],
        allowed_tools=[],
        priority=10,
    ))
    agent_registry.register(object(), AgentMetadata(
        name="us_stock",
        display_name="US Stock Agent",
        description="us",
        capabilities=["us"],
        allowed_tools=[],
        priority=8,
    ))
    return ManagerAgent(llm, agent_registry, ToolRegistry())


def test_normalize_tasks_truncates_large_plan_and_filters_dependencies():
    manager = build_manager()

    tasks = [
        {
            "id": f"task_{i}",
            "name": f"Task {i}",
            "agent": "chat",
            "description": f"step {i}",
            "dependencies": [f"task_{i - 1}"] if i > 1 else [],
        }
        for i in range(1, MAX_GRAPH_TASKS + 4)
    ]

    normalized = manager._normalize_tasks(tasks, "分析 Pi")

    assert len(normalized) == MAX_GRAPH_TASKS
    assert normalized[-1]["id"] == f"task_{MAX_GRAPH_TASKS}"
    assert all(
        dep in {task["id"] for task in normalized}
        for task in normalized
        for dep in task["dependencies"]
    )


def test_normalize_tasks_falls_back_to_single_chat_task_for_invalid_input():
    manager = build_manager()

    normalized = manager._normalize_tasks("not-a-list", "Pi 幣值得投資嗎")

    assert normalized == []
    fallback = manager._normalize_tasks([], "Pi 幣值得投資嗎")
    assert fallback == [{
        "id": "task_1",
        "name": "處理請求",
        "agent": "chat",
        "description": "Pi 幣值得投資嗎",
        "dependencies": [],
    }]


def test_detect_boundary_route_for_crypto_price_query():
    manager = build_manager()

    route = manager._detect_boundary_route("請問 BTC 現在多少錢？")

    assert route is not None
    assert route["task"]["agent"] == "crypto"
    assert route["entities"]["crypto"] == "BTC"


def test_detect_boundary_route_normalizes_mixed_width_crypto_symbol():
    manager = build_manager()

    route = manager._detect_boundary_route("pｉ幣價格目前是多少")

    assert route is not None
    assert route["task"]["agent"] == "crypto"
    assert route["entities"]["crypto"] == "PI"


def test_detect_boundary_route_ignores_greeting():
    manager = build_manager()

    route = manager._detect_boundary_route("你好")

    assert route is None


@pytest.mark.asyncio
async def test_synthesize_response_does_not_fallback_to_llm_after_tool_failure():
    manager = build_manager()
    manager._track_conversation = AsyncMock()
    manager._llm_invoke = AsyncMock(return_value="不應該被呼叫")

    result = await manager._synthesize_response_node({
        "query": "pi network目前價格多少",
        "_processed_query": "",
        "task_results": {},
        "tool_failure_detected": True,
        "tool_failure_issues": [{"problem": "價格數據異常：無法獲取"}],
    })

    assert "目前工具未能取得有效資料" in result["final_response"]
    assert "價格數據異常：無法獲取" in result["final_response"]
    manager._llm_invoke.assert_not_called()
