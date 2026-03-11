import asyncio
from unittest.mock import patch

from api.routers.tools import ToolPreferenceRequest, _set_tool_preference_impl, router
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
        ]


class _DummyAgent(BaseReActAgent):
    @property
    def name(self) -> str:
        return "crypto"


def test_normalize_membership_tier_maps_legacy_pro_to_premium():
    assert normalize_membership_tier("pro") == "premium"
    assert normalize_membership_tier("premium") == "premium"
    assert normalize_membership_tier(None) == "free"


def test_base_react_agent_filters_tools_by_allowed_tool_ids():
    agent = _DummyAgent(llm_client=None, tool_registry=_FakeRegistry(), user_tier="free", user_id="u1")

    with patch("core.agents.base_react_agent.get_allowed_tools", return_value=["free_tool"]):
        metas = agent._get_tool_metas(SubTask(step=1, description="test", agent="crypto"))

    assert [m.name for m in metas] == ["free_tool"]


def test_base_react_agent_respects_empty_allowed_tool_list():
    agent = _DummyAgent(llm_client=None, tool_registry=_FakeRegistry(), user_tier="premium", user_id="u1")

    with patch("core.agents.base_react_agent.get_allowed_tools", return_value=[]):
        metas = agent._get_tool_metas(SubTask(step=1, description="test", agent="crypto"))

    assert metas == []


def test_base_react_agent_falls_back_to_required_tier_filter():
    agent = _DummyAgent(llm_client=None, tool_registry=_FakeRegistry(), user_tier="pro", user_id="u1")

    with patch("core.agents.base_react_agent.get_allowed_tools", side_effect=RuntimeError("db down")):
        metas = agent._get_tool_metas(SubTask(step=1, description="test", agent="crypto"))

    assert [m.name for m in metas] == ["free_tool", "premium_tool"]


def test_tools_router_exposes_user_tools_routes():
    routes = {route.path for route in router.routes}
    assert "/api/user/tools" in routes
    assert "/api/user/tools/{tool_id}/preference" in routes


def test_premium_member_can_update_tool_preference():
    current_user = {
        "user_id": "user-1",
        "membership_tier": "premium",
    }
    request = ToolPreferenceRequest(is_enabled=False)

    with patch("api.routers.tools.get_tools_for_frontend", return_value=[{"tool_id": "get_crypto_price", "locked": False}]), \
         patch("api.routers.tools.update_user_tool_preference") as mock_update:
        response = asyncio.run(_set_tool_preference_impl("get_crypto_price", request, current_user))

    assert response["success"] is True
    mock_update.assert_called_once()
