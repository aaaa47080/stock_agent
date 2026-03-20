import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.agents.manager import ManagerAgent


def test_manager_passes_pre_resolved_allowed_tools_to_agent_context():
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
    manager._execute_agent = AsyncMock(
        return_value={
            "message": "ok",
            "success": True,
            "data": {},
            "quality": "pass",
            "quality_fail_reason": None,
        }
    )
    manager.tool_access_resolver = MagicMock()
    manager.tool_access_resolver.resolve_for_agent.return_value = ["tool_a", "tool_b"]
    manager._build_market_resolution_metadata = MagicMock(
        return_value={"candidates": ["AAPL"]}
    )
    manager._build_query_policy_metadata = MagicMock(
        return_value={"query_type": "price_lookup"}
    )

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

    result = asyncio.run(manager._execute_single_task(task, state, {}))

    assert result["success"] is True
    manager.tool_access_resolver.resolve_for_agent.assert_called_once_with("crypto")

    passed_context = manager._execute_agent.await_args.args[1]
    assert passed_context.allowed_tools == ["tool_a", "tool_b"]


def test_manager_passes_analysis_mode_to_agent_context():
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
    manager._execute_agent = AsyncMock(
        return_value={
            "message": "ok",
            "success": True,
            "data": {},
            "quality": "pass",
            "quality_fail_reason": None,
        }
    )
    manager.tool_access_resolver = MagicMock()
    manager.tool_access_resolver.resolve_for_agent.return_value = ["tool_a"]
    manager._build_market_resolution_metadata = MagicMock(
        return_value={"candidates": ["AAPL"]}
    )
    manager._build_query_policy_metadata = MagicMock(
        return_value={"query_type": "price_lookup"}
    )

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

    asyncio.run(manager._execute_single_task(task, state, {}))

    passed_context = manager._execute_agent.await_args.args[1]
    assert passed_context.analysis_mode == "verified"


def test_manager_merges_trace_metadata_into_task_result():
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
    manager._execute_agent = AsyncMock(
        return_value={
            "message": "ok",
            "success": True,
            "data": {"policy_path": "market_lookup"},
            "quality": "pass",
            "quality_fail_reason": None,
        }
    )
    manager.tool_access_resolver = MagicMock()
    manager.tool_access_resolver.resolve_for_agent.return_value = ["tool_a"]
    manager._build_market_resolution_metadata = MagicMock(
        return_value={
            "candidates": ["AAPL"],
            "matched_entities": {"us": "AAPL"},
        }
    )
    manager._build_query_policy_metadata = MagicMock(
        return_value={"query_type": "price_lookup"}
    )

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

    result = asyncio.run(manager._execute_single_task(task, state, {}))

    assert result["data"]["query_type"] == "price_lookup"
    assert result["data"]["resolved_market"] == "us"
    assert result["data"]["policy_path"] == "market_lookup"


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
    query_profile = manager._build_query_policy_metadata(
        "tsm 現在多少？", market_resolution
    )

    assert query_profile["query_type"] == "price_lookup"
    assert query_profile["has_symbol_candidates"] is True


def test_manager_reconciles_llm_entities_with_structural_resolver():
    llm = MagicMock()
    agent_registry = MagicMock()
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
    )
    manager._symbol_resolver.resolve_with_context = MagicMock(
        return_value={
            "resolution": {"crypto": None, "tw": "2330.TW", "us": "TSM"},
            "candidates": {
                "tw": {"symbol": "2330.TW", "score": 0.5, "match_type": "fuzzy"},
                "us": {"symbol": "TSM", "score": 0.72, "match_type": "ticker"},
            },
            "primary_market": "us",
            "primary_score": 0.72,
            "ambiguous": False,
        }
    )

    entities = manager._reconcile_market_entities(
        "TSM 現在多少？",
        "",
        {"tw": "2330.TW", "us": None, "crypto": None},
    )

    assert entities["us"] == "TSM"
    assert entities["tw"] is None


def test_manager_applies_structural_override_for_single_price_task():
    llm = MagicMock()
    agent_registry = MagicMock()
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
    )
    manager._detect_boundary_route = MagicMock(
        return_value={
            "task": {
                "id": "task_1",
                "name": "處理 TSM 相關查詢",
                "agent": "us_stock",
                "description": "TSM 現在多少？",
                "dependencies": [],
            },
            "entities": {"crypto": None, "tw": None, "us": "TSM"},
        }
    )

    overridden = manager._apply_structural_task_overrides(
        [
            {
                "id": "task_1",
                "name": "查詢台股價格",
                "agent": "tw_stock",
                "description": "TSM 現在多少？",
                "dependencies": [],
            }
        ],
        query="TSM 現在多少？",
        history="",
        entities={"crypto": None, "tw": None, "us": "TSM"},
        query_profile={"query_type": "price_lookup"},
    )

    assert overridden[0]["agent"] == "us_stock"
    assert overridden[0]["name"] == "處理 TSM 相關查詢"
    assert overridden[0]["description"] == "TSM 現在多少？"


def test_manager_extract_market_entities_does_not_let_history_override_current_query():
    llm = MagicMock()
    agent_registry = MagicMock()
    tool_registry = MagicMock()

    manager = ManagerAgent(
        llm_client=llm,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
    )
    manager._symbol_resolver.resolve_with_context = MagicMock(
        return_value={
            "resolution": {"crypto": "BTC", "tw": None, "us": None},
            "candidates": {
                "crypto": {
                    "symbol": "BTC",
                    "score": 0.92,
                    "match_type": "known_symbol",
                },
            },
            "primary_market": "crypto",
            "primary_score": 0.92,
            "ambiguous": False,
        }
    )

    entities = manager._extract_market_entities(
        "BTC現在多少？",
        history="上一輪在聊台灣半導體與台積電 ADR",
    )

    manager._symbol_resolver.resolve_with_context.assert_called_once_with(
        "BTC", context_text="BTC現在多少?"
    )
    assert entities["crypto"] == "BTC"
    assert entities["tw"] is None
