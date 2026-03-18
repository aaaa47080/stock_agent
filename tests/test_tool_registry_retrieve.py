from unittest.mock import MagicMock, patch


def test_retrieve_tool_result_returns_stored():
    from core.agents.tool_compactor import retrieve_tool_result

    with patch("core.agents.tool_compactor._local_store", {"abc-123": "full data here"}):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            assert retrieve_tool_result("abc-123") == "full data here"


def test_retrieve_tool_result_unknown_key():
    from core.agents.tool_compactor import retrieve_tool_result

    with patch("core.agents.tool_compactor._local_store", {}):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            assert "[ERROR]" in retrieve_tool_result("nonexistent-key")


def test_tool_result_retrieve_registered_in_bootstrap():
    from core.agents.bootstrap import bootstrap, invalidate_manager_cache

    user_id = "test-user-retrieve"
    invalidate_manager_cache(user_id)

    with patch("core.agents.base_react_agent.get_allowed_tools", side_effect=Exception("no db")):
        fake_llm = MagicMock()
        fake_llm.invoke = MagicMock(return_value=MagicMock(content="ok"))
        manager = bootstrap(fake_llm, user_tier="free", user_id=user_id, session_id="retrieve-test")

    tool = manager.tool_registry.get("tool_result_retrieve")
    assert tool is not None


def test_tool_result_retrieve_enforces_user_scope():
    from core.agents.bootstrap import bootstrap, invalidate_manager_cache
    from core.agents.tool_compactor import _serialize_record

    user_id = "scope-user"
    invalidate_manager_cache(user_id)

    with patch("core.agents.base_react_agent.get_allowed_tools", side_effect=Exception("no db")):
        fake_llm = MagicMock()
        fake_llm.invoke = MagicMock(return_value=MagicMock(content="ok"))
        manager = bootstrap(fake_llm, user_tier="free", user_id=user_id, session_id="retrieve-scope")

    tool = manager.tool_registry.get("tool_result_retrieve")
    with patch("core.agents.tool_compactor._local_store", {"uid-1": _serialize_record("secret", "other-user")}):
        result = tool.handler.invoke({"uuid": "uid-1"})

    assert "[ERROR]" in result


def test_retrieve_tool_result_allows_same_scope_workspace():
    from core.agents.tool_compactor import _serialize_record, retrieve_tool_result

    with patch(
        "core.agents.tool_compactor._local_store",
        {"uid-2": _serialize_record("ok", "scope-user", workspace_id="ws-1")},
    ):
        with patch("core.agents.tool_compactor._get_redis_sync", return_value=None):
            result = retrieve_tool_result("uid-2", requester_id="scope-user", workspace_id="ws-1")

    assert result == "ok"
