from unittest.mock import AsyncMock, patch

import pytest

from api.routers.tools import (
    ToolPreferenceRequest,
    _list_tools_impl,
    _set_tool_preference_impl,
    router,
)
from core.agents.base_react_agent import BaseReActAgent
from core.agents.models import SubTask
from core.agents.tool_registry import ToolMetadata
from core.database.tools import normalize_membership_tier


class _FakeTool:
    name = "premium_tool"
    description = "premium tool"
    args = {}

    def invoke(self, kwargs):
        return kwargs


class _FakeRegistry:
    def list_for_agent(self, _agent_name):
        return [
            ToolMetadata(
                name="free_tool",
                description="free tool",
                input_schema={},
                handler=_FakeTool(),
                allowed_agents=["crypto"],
                required_tier="free",
            ),
            ToolMetadata(
                name="premium_tool",
                description="premium tool",
                input_schema={},
                handler=_FakeTool(),
                allowed_agents=["crypto"],
                required_tier="premium",
            ),
            ToolMetadata(
                name="web_search",
                description="discovery tool",
                input_schema={"query": "str", "purpose": "str"},
                handler=_FakeTool(),
                allowed_agents=["crypto"],
                role="discovery_lookup",
                priority=80,
                required_tier="free",
            ),
        ]


class _DummyAgent(BaseReActAgent):
    @property
    def name(self) -> str:
        return "crypto"


def test_normalize_membership_tier_maps_legacy_pro_to_premium():
    assert normalize_membership_tier("pro") == "premium"
    assert normalize_membership_tier("premium") == "premium"
    assert normalize_membership_tier("plus") == "premium"
    assert normalize_membership_tier(None) == "free"


def test_base_react_agent_filters_tools_by_allowed_tool_ids():
    agent = _DummyAgent(
        llm_client=None, tool_registry=_FakeRegistry(), user_tier="free", user_id="u1"
    )

    with patch(
        "core.agents.base_react_agent.get_allowed_tools", return_value=["free_tool"]
    ):
        metas = agent._get_tool_metas(
            SubTask(step=1, description="test", agent="crypto")
        )

    assert [m.name for m in metas] == ["free_tool"]


def test_base_react_agent_respects_empty_allowed_tool_list():
    agent = _DummyAgent(
        llm_client=None,
        tool_registry=_FakeRegistry(),
        user_tier="premium",
        user_id="u1",
    )

    with patch("core.agents.base_react_agent.get_allowed_tools", return_value=[]):
        metas = agent._get_tool_metas(
            SubTask(step=1, description="test", agent="crypto")
        )

    assert metas == []


def test_base_react_agent_falls_back_to_required_tier_filter():
    agent = _DummyAgent(
        llm_client=None, tool_registry=_FakeRegistry(), user_tier="pro", user_id="u1"
    )

    with patch(
        "core.agents.base_react_agent.get_allowed_tools",
        side_effect=RuntimeError("db down"),
    ):
        metas = agent._get_tool_metas(
            SubTask(step=1, description="test", agent="crypto")
        )

    assert [m.name for m in metas] == ["free_tool", "premium_tool", "web_search"]


def test_base_react_agent_prefers_allowed_tools_from_task_context():
    agent = _DummyAgent(
        llm_client=None,
        tool_registry=_FakeRegistry(),
        user_tier="premium",
        user_id="u1",
    )

    with patch(
        "core.agents.base_react_agent.get_allowed_tools",
        side_effect=AssertionError("should not hit db"),
    ):
        metas = agent._get_tool_metas(
            SubTask(
                step=1,
                description="test",
                agent="crypto",
                context={"allowed_tools": ["premium_tool"]},
            )
        )

    assert [m.name for m in metas] == ["premium_tool"]


def test_base_react_agent_prefers_discovery_lookup_when_market_is_unresolved():
    agent = _DummyAgent(
        llm_client=None,
        tool_registry=_FakeRegistry(),
        user_tier="premium",
        user_id="u1",
    )
    task = SubTask(
        step=1,
        description="tsm 現在多少？",
        agent="crypto",
        context={
            "allowed_tools": ["web_search", "premium_tool"],
            "analysis_mode": "verified",
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

    metas = agent._get_tool_metas(task)
    selected = agent._select_required_tool(task, metas)

    assert selected is not None
    assert selected.name == "web_search"


def test_tools_router_exposes_user_tools_routes():
    routes = {route.path for route in router.routes}
    assert "/api/user/tools" in routes
    assert "/api/user/tools/{tool_id}/preference" in routes


@pytest.mark.asyncio
async def test_list_tools_impl_falls_back_when_repo_unavailable():
    current_user = {
        "user_id": "user-1",
        "membership_tier": "free",
    }

    with (
        patch(
            "core.orm.tools_repo.tools_repo.get_tools_for_frontend",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ),
        patch("api.routers.tools.seed_tools_catalog", side_effect=RuntimeError("seed down")),
    ):
        response = await _list_tools_impl(current_user)

    assert response["user_tier"] == "free"
    assert len(response["tools"]) >= 1
    assert any(tool["tool_id"] == "get_crypto_price" for tool in response["tools"])


@pytest.mark.asyncio
async def test_premium_member_can_update_tool_preference():
    current_user = {
        "user_id": "user-1",
        "membership_tier": "premium",
    }
    request = ToolPreferenceRequest(is_enabled=False)

    with (
        patch(
            "core.orm.tools_repo.tools_repo.get_tools_for_frontend",
            new_callable=AsyncMock,
            return_value=[{"tool_id": "get_crypto_price", "locked": False}],
        ),
        patch(
            "core.orm.tools_repo.tools_repo.update_user_tool_preference",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        response = await _set_tool_preference_impl(
            "get_crypto_price", request, current_user
        )

    assert response["success"] is True
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_free_member_cannot_update_tool_preference():
    current_user = {
        "user_id": "user-1",
        "membership_tier": "free",
    }
    request = ToolPreferenceRequest(is_enabled=False)

    with pytest.raises(Exception) as exc_info:
        await _set_tool_preference_impl("get_crypto_price", request, current_user)

    assert getattr(exc_info.value, "status_code", None) == 403
    assert "Premium" in getattr(exc_info.value, "detail", "")
