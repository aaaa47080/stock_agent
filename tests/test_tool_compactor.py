from unittest.mock import MagicMock, patch

import pytest


def _make_tool(return_value, name="mock_tool"):
    tool = MagicMock()
    tool.name = name
    tool.invoke = MagicMock(return_value=return_value)
    return tool


@pytest.fixture(autouse=True)
def reset_compactor_state():
    from core.agents import tool_compactor

    tool_compactor._reset_for_testing()
    yield
    tool_compactor._reset_for_testing()


def test_small_output_passes_through():
    from core.agents.tool_compactor import wrap_tool

    tool = _make_tool({"price": 100})
    wrapped = wrap_tool(tool)
    assert wrapped.invoke({}) == {"price": 100}


def test_large_string_output_is_compacted():
    from core.agents.tool_compactor import THRESHOLD, wrap_tool

    tool = _make_tool("x" * (THRESHOLD + 1))
    with patch("core.agents.tool_compactor._store_sync", return_value="test-uuid-123"):
        wrapped = wrap_tool(tool)
        result = wrapped.invoke({})

    assert "[COMPACTED:test-uuid-123]" in result


def test_large_dict_output_is_compacted():
    from core.agents.tool_compactor import wrap_tool

    tool = _make_tool({"rows": ["row"] * 1000})
    with patch("core.agents.tool_compactor._store_sync", return_value="uuid-abc"):
        wrapped = wrap_tool(tool)
        result = wrapped.invoke({})

    assert "[COMPACTED:uuid-abc]" in result


def test_compact_summary_contains_preview():
    from core.agents.tool_compactor import THRESHOLD, wrap_tool

    original = "PREVIEW_MARKER" + "A" * (THRESHOLD + 500)
    tool = _make_tool(original)
    with patch("core.agents.tool_compactor._store_sync", return_value="uid"):
        wrapped = wrap_tool(tool)
        result = wrapped.invoke({})

    assert "PREVIEW_MARKER" in result


def test_tool_name_preserved():
    from core.agents.tool_compactor import wrap_tool

    tool = _make_tool("small output", name="tw_stock_price")
    wrapped = wrap_tool(tool)
    assert wrapped.name == "tw_stock_price"


def test_wrap_tool_does_not_mutate_original():
    from core.agents.tool_compactor import THRESHOLD, wrap_tool

    tool = _make_tool("x" * (THRESHOLD + 100))
    original_invoke = tool.invoke
    with patch("core.agents.tool_compactor._store_sync", return_value="uid"):
        wrapped = wrap_tool(tool)

    assert tool.invoke is original_invoke
    assert wrapped is not tool


def test_multiple_wraps_do_not_stack():
    from core.agents.tool_compactor import THRESHOLD, wrap_tool

    tool = _make_tool("x" * (THRESHOLD + 100))
    store_calls = []

    def fake_store(data, owner_id=None, workspace_id=None, session_id=None):
        store_calls.append(data)
        return f"uid-{len(store_calls)}"

    with patch("core.agents.tool_compactor._store_sync", side_effect=fake_store):
        wrapped1 = wrap_tool(tool)
        wrapped2 = wrap_tool(tool)
        wrapped1.invoke({})
        wrapped2.invoke({})

    assert len(store_calls) == 2


def test_store_sync_returns_uuid_string():
    from core.agents.tool_compactor import _store_sync

    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        uid = _store_sync("some data")

    assert isinstance(uid, str) and len(uid) > 0


def test_retrieve_sync_returns_none_for_unknown_key():
    from core.agents.tool_compactor import _retrieve_sync

    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        assert _retrieve_sync("nonexistent-uuid") is None


def test_retrieve_tool_result_error_message():
    from core.agents.tool_compactor import retrieve_tool_result

    with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
        assert "[ERROR]" in retrieve_tool_result("bad-key")


def test_retrieve_tool_result_returns_stored_data():
    from core.agents.tool_compactor import retrieve_tool_result

    with patch(
        "core.agents.tool_compactor._local_store", {"my-uid": "full content here"}
    ):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            assert retrieve_tool_result("my-uid") == "full content here"


def test_retrieve_tool_result_rejects_other_user():
    from core.agents.tool_compactor import _serialize_record, retrieve_tool_result

    with patch(
        "core.agents.tool_compactor._local_store",
        {"owned-uid": _serialize_record("secret", "user-a")},
    ):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            result = retrieve_tool_result("owned-uid", requester_id="user-b")

    assert "[ERROR]" in result


def test_retrieve_tool_result_rejects_other_workspace():
    from core.agents.tool_compactor import _serialize_record, retrieve_tool_result

    with patch(
        "core.agents.tool_compactor._local_store",
        {"owned-uid": _serialize_record("secret", "user-a", workspace_id="ws-a")},
    ):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            result = retrieve_tool_result(
                "owned-uid", requester_id="user-a", workspace_id="ws-b"
            )

    assert "[ERROR]" in result


def test_base_react_agent_wraps_tools_non_mutating():
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.tool_compactor import _CompactingToolWrapper
    from core.agents.tool_registry import ToolMetadata

    class DummyAgent(BaseReActAgent):
        @property
        def name(self) -> str:
            return "dummy"

    big_tool = _make_tool("x" * 5000, name="big_tool")
    original_invoke = big_tool.invoke
    registry_meta = ToolMetadata(
        name="big_tool",
        description="test",
        input_schema={},
        handler=big_tool,
        allowed_agents=[],
        required_tier="free",
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]
    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry, user_id="user-1")

    with patch(
        "core.agents.base_react_agent.get_allowed_tools", return_value=["big_tool"]
    ):
        metas = agent._get_tool_metas()

    assert isinstance(metas[0].handler, _CompactingToolWrapper)
    assert metas[0].handler._owner_id == "user-1"
    assert big_tool.invoke is original_invoke
    assert registry_meta.handler is big_tool


def test_base_react_agent_wraps_tools_with_workspace_scope():
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.tool_registry import ToolMetadata

    class DummyAgent(BaseReActAgent):
        @property
        def name(self) -> str:
            return "dummy"

    tool = _make_tool("small")
    registry_meta = ToolMetadata(
        name="tool",
        description="test",
        input_schema={},
        handler=tool,
        allowed_agents=[],
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]
    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry, user_id="user-1")

    task = MagicMock()
    task.context = {"workspace_id": "ws-1", "user_id": "user-1"}

    with patch("core.agents.base_react_agent.get_allowed_tools", return_value=["tool"]):
        metas = agent._get_tool_metas(task)

    assert metas[0].handler._workspace_id == "ws-1"


def test_repeated_get_tool_metas_does_not_double_wrap():
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.tool_registry import ToolMetadata

    class DummyAgent(BaseReActAgent):
        @property
        def name(self) -> str:
            return "dummy"

    tool = _make_tool("small output")
    registry_meta = ToolMetadata(
        name="t",
        description="",
        input_schema={},
        handler=tool,
        allowed_agents=[],
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]
    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry)

    with patch("core.agents.base_react_agent.get_allowed_tools", return_value=["t"]):
        metas1 = agent._get_tool_metas()
        metas2 = agent._get_tool_metas()

    assert metas1[0].handler._original is tool
    assert metas2[0].handler._original is tool


def test_required_tool_path_compacts_large_output():
    from core.agents.base_react_agent import BaseReActAgent
    from core.agents.models import AgentResult, SubTask
    from core.agents.tool_registry import ToolMetadata

    class DummyAgent(BaseReActAgent):
        @property
        def name(self) -> str:
            return "dummy"

    big_tool = _make_tool("x" * 5000, name="forced_tool")
    registry_meta = ToolMetadata(
        name="forced_tool",
        description="test",
        input_schema={"symbol": "str"},
        handler=big_tool,
        allowed_agents=[],
        required_tier="free",
        role="market_lookup",
    )
    registry = MagicMock()
    registry.list_for_agent.return_value = [registry_meta]
    agent = DummyAgent(llm_client=MagicMock(), tool_registry=registry)
    captured = {}

    def fake_summarize(self, task, meta, tool_result, language):
        captured["tool_result"] = tool_result
        return AgentResult(success=True, message="ok", agent_name="dummy")

    task = SubTask(
        step=1,
        description="test",
        agent="dummy",
        context={"symbols": {"crypto": "BTC"}, "tool_required": True},
    )

    with patch("core.agents.tool_compactor._store_sync", return_value="forced-uid"):
        with patch(
            "core.agents.base_react_agent.get_allowed_tools",
            return_value=["forced_tool"],
        ):
            with patch.object(
                type(agent), "_summarize_required_tool_result", fake_summarize
            ):
                wrapped_metas = agent._get_tool_metas(task)
                agent._execute_with_required_tool(task, wrapped_metas, "zh-TW")

    assert "[COMPACTED:forced-uid]" in str(captured.get("tool_result", ""))


# ── tool stat collection ──────────────────────────────────────────────────────


def test_wrapper_records_pending_stat_on_success():
    """After invoke(), wrapper exposes a pending stat tuple."""
    from core.agents.tool_compactor import _reset_for_testing, wrap_tool

    _reset_for_testing()
    tool = _make_tool("small output")
    wrapped = wrap_tool(tool, owner_id="u1")
    wrapped.invoke({})
    assert wrapped.last_stat is not None
    stat = wrapped.last_stat
    assert stat["tool_name"] == "mock_tool"
    assert stat["success"] is True
    assert stat["output_chars"] > 0


def test_wrapper_records_pending_stat_on_failure():
    """After a failing invoke(), last_stat has success=False and error_type set."""
    from core.agents.tool_compactor import _reset_for_testing, wrap_tool

    _reset_for_testing()
    tool = MagicMock()
    tool.name = "fail_tool"
    tool.invoke = MagicMock(side_effect=RuntimeError("API down"))
    wrapped = wrap_tool(tool, owner_id="u1")
    try:
        wrapped.invoke({})
    except RuntimeError:
        pass
    assert wrapped.last_stat is not None
    assert wrapped.last_stat["success"] is False
    assert wrapped.last_stat["error_type"] == "RuntimeError"
