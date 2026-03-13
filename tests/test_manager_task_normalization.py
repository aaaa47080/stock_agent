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
        priority=10,
    ))
    agent_registry.register(object(), AgentMetadata(
        name="tw_stock",
        display_name="TW Stock Agent",
        description="tw",
        capabilities=["tw"],
        priority=10,
    ))
    agent_registry.register(object(), AgentMetadata(
        name="us_stock",
        display_name="US Stock Agent",
        description="us",
        capabilities=["us"],
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
async def test_aggregate_results_node_keeps_intermediate_text_out_of_final_response():
    manager = build_manager()

    result = await manager._aggregate_results_node({
        "task_results": {
            "task_1": {
                "success": True,
                "agent_name": "us_stock",
                "message": "AAPL 目前為 255 美元",
            }
        },
        "intent_understanding": {"aggregation_strategy": "combine_all"},
    })

    assert "aggregated_response" in result
    assert "final_response" not in result
    assert "Sub-Agent 執行結果" in result["aggregated_response"]


def test_finalize_mode_response_appends_verified_evidence():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response="AAPL 目前為 255 美元。",
        analysis_mode="verified",
        evidence={
            "used_tools": ["us_stock_price"],
            "data_as_of": "2026-03-13T10:00:00Z",
            "verification_status": "verified",
        },
    )

    assert "### 驗證資訊" in finalized
    assert "us_stock_price" in finalized
    assert "2026-03-13T10:00:00Z" in finalized


def test_finalize_mode_response_strips_internal_sub_agent_headers():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response="# Sub-Agent 執行結果\n\n### 任務 1 [us_stock]\nAAPL 目前為 255 美元。",
        analysis_mode="research",
        evidence={},
    )

    assert "Sub-Agent 執行結果" not in finalized
    assert "任務 1" not in finalized
    assert "AAPL 目前為 255 美元。" in finalized


def test_finalize_mode_response_replaces_model_generated_verified_footer():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response=(
            "AAPL 目前為 255 美元。\n\n"
            "### 驗證資訊\n"
            "- Apple Inc. (AAPL) 股價資訊來自於最新市場數據。"
        ),
        analysis_mode="verified",
        evidence={
            "used_tools": ["us_stock_price"],
            "data_as_of": "2026-03-13T10:00:00Z",
            "verification_status": "verified",
        },
    )

    assert "Apple Inc. (AAPL) 股價資訊來自於最新市場數據。" not in finalized
    assert finalized.count("### 驗證資訊") == 1
    assert "us_stock_price" in finalized


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
