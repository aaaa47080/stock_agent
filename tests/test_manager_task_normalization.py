from unittest.mock import MagicMock, AsyncMock

import pytest

from core.agents.agent_registry import AgentRegistry, AgentMetadata
from core.agents.manager import ManagerAgent, MAX_GRAPH_TASKS, CLEAR_SENTINEL
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


def test_apply_structural_task_overrides_aligns_single_task_agent_to_resolved_market():
    manager = build_manager()

    overridden = manager._apply_structural_task_overrides(
        tasks=[{
            "id": "task_1",
            "name": "原始任務",
            "agent": "tw_stock",
            "description": "它今天為什麼跌？",
            "dependencies": [],
        }],
        query="它今天為什麼跌？",
        history="使用者: AAPL 現在多少？",
        entities={"crypto": None, "tw": None, "us": "AAPL"},
        query_profile={"query_type": "market_event"},
    )

    assert len(overridden) == 1
    assert overridden[0]["agent"] == "us_stock"
    assert overridden[0]["description"] == "它今天為什麼跌？"


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


def test_finalize_mode_response_removes_inline_verified_sentence():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response="AAPL 目前為 255 美元。\n\n驗證資訊：資料時間為 2026-03-13。",
        analysis_mode="verified",
        evidence={
            "used_tools": ["us_stock_price"],
            "data_as_of": "2026-03-13T10:00:00Z",
            "verification_status": "verified",
        },
    )

    assert "驗證資訊：資料時間為 2026-03-13。" not in finalized
    assert finalized.count("### 驗證資訊") == 1


def test_finalize_mode_response_replaces_lower_level_research_footer():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response=(
            "### 重點結論\nAAPL 穩定。\n\n"
            "#### 研究依據\n"
            "- 資料來源：舊內容"
        ),
        analysis_mode="research",
        evidence={
            "used_tools": ["us_stock_price"],
            "data_as_of": "2026-03-14T00:00:00Z",
        },
    )

    assert "資料來源：舊內容" not in finalized
    assert finalized.count("### 研究依據") == 1
    assert "us_stock_price" in finalized


def test_finalize_mode_response_removes_inline_research_sentence():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response="### 重點結論\nAAPL 穩定。\n\n研究依據：即時股價資料來源於 US Stock Price 查詢。",
        analysis_mode="research",
        evidence={
            "used_tools": ["us_stock_price"],
            "data_as_of": "2026-03-14T00:00:00Z",
        },
    )

    assert "研究依據：即時股價資料來源於 US Stock Price 查詢。" not in finalized
    assert finalized.count("### 研究依據") == 1
    assert "us_stock_price" in finalized


def test_build_response_format_guidance_uses_research_structure_for_single_asset():
    manager = build_manager()

    guidance = manager._build_response_format_guidance("research", "請分析 AAPL。")

    assert "### 重點結論" in guidance
    assert "### 標的比較" not in guidance


def test_build_response_format_guidance_uses_compare_structure_for_compare_query():
    manager = build_manager()

    guidance = manager._build_response_format_guidance("research", "比較 TSM ADR 和 2330。")

    assert "### 標的比較" in guidance
    assert "| 項目 | 標的A | 標的B |" in guidance


def test_apply_pronoun_entity_carryover_uses_previous_single_market_entity():
    manager = build_manager()

    carried = manager._apply_pronoun_entity_carryover(
        query="它今天為什麼跌？",
        current_entities={"crypto": None, "tw": None, "us": None},
        prior_entities={"crypto": None, "tw": None, "us": "AAPL"},
    )

    assert carried["us"] == "AAPL"
    assert carried["tw"] is None
    assert carried["crypto"] is None


def test_apply_pronoun_entity_carryover_does_not_override_explicit_symbol():
    manager = build_manager()

    carried = manager._apply_pronoun_entity_carryover(
        query="改看 NVDA",
        current_entities={"crypto": None, "tw": None, "us": "NVDA"},
        prior_entities={"crypto": None, "tw": None, "us": "AAPL"},
    )

    assert carried["us"] == "NVDA"


def test_apply_pronoun_entity_carryover_overrides_drifted_current_entity():
    manager = build_manager()

    carried = manager._apply_pronoun_entity_carryover(
        query="它今天為什麼跌？",
        current_entities={"crypto": None, "tw": "2330.TW", "us": None},
        prior_entities={"crypto": None, "tw": None, "us": "AAPL"},
    )

    assert carried["us"] == "AAPL"
    assert carried["tw"] is None


def test_extract_market_entities_uses_latest_user_utterance_for_pronoun_query():
    manager = build_manager()

    entities = manager._extract_market_entities(
        "它今天為什麼跌？",
        history="使用者: AAPL 現在多少？\n助手: 回覆略",
    )

    assert entities["us"] == "AAPL"


def test_reconcile_market_entities_prefers_resolver_when_symbol_conflicts():
    manager = build_manager()

    reconciled = manager._reconcile_market_entities(
        query="它今天為什麼跌？",
        history="使用者: AAPL 現在多少？\n助手: 回覆略",
        llm_entities={"crypto": None, "tw": None, "us": "TSM"},
    )

    assert reconciled["us"] == "AAPL"


def test_finalize_mode_response_strips_compare_block_for_non_compare_query():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response=(
            "### 標的比較\n"
            "| 項目 | 標的A | 標的B |\n"
            "|------|-------|-------|\n"
            "| 價格 | 1 | 2 |\n\n"
            "### 分析結論\n重點結論"
        ),
        analysis_mode="quick",
        evidence={},
        query="請分析單一標的",
    )

    assert "### 標的比較" not in finalized
    assert "### 分析結論" in finalized


def test_finalize_mode_response_verified_causal_question_requires_evidence():
    manager = build_manager()

    finalized = manager._finalize_mode_response(
        response="今天下跌是因為市場恐慌。",
        analysis_mode="verified",
        evidence={"verification_status": None},
        query="它今天為什麼跌？",
    )

    assert "缺少可驗證的事件資料來源" in finalized


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


@pytest.mark.asyncio
async def test_understand_intent_sets_processed_query_and_resets_previous_task_results():
    manager = build_manager()
    manager._llm_invoke = AsyncMock(return_value="""
    {
      "status": "ready",
      "user_intent": "查詢價格",
      "entities": {"crypto": null, "tw": null, "us": "AAPL"},
      "tasks": [{"id":"task_1","name":"處理請求","agent":"us_stock","description":"AAPL現在多少？","dependencies":[]}],
      "aggregation_strategy": "combine_all"
    }
    """)

    result = await manager._understand_intent_node({
        "query": "AAPL現在多少？",
        "history": "",
        "_processed_query": "上一輪問題",
        "task_results": {"task_legacy": {"success": True}},
    })

    assert result["_processed_query"] == "AAPL現在多少？"
    assert result["task_results"] == {CLEAR_SENTINEL: True}
