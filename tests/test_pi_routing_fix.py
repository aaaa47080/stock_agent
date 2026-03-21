"""
測試 PI 路由與工具選擇修復
- 使用 MockLLM 替代真實 API，驗證流程邏輯
- 不需要外網連線
"""

import inspect
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


class MockLLM:
    """模擬 LLM，根據 prompt 內容回傳預設回應，不需真實 API。"""

    def __init__(self):
        self._tools = []

    def bind_tools(self, tools, **kwargs):
        clone = MockLLM()
        clone._tools = list(tools)
        return clone

    def invoke(self, messages, **kwargs):
        prompt = " ".join(
            m.content if hasattr(m, "content") else str(m) for m in messages
        )
        return self._make_response(prompt)

    async def ainvoke(self, messages, **kwargs):
        return self.invoke(messages, **kwargs)

    def _make_response(self, prompt: str):
        from langchain_core.messages import AIMessage

        prompt_lower = prompt.lower()

        if '"status"' in prompt or "json" in prompt_lower and "tasks" in prompt_lower:
            if "pi" in prompt_lower and (
                "price" in prompt_lower
                or "價格" in prompt_lower
                or "多少" in prompt_lower
            ):
                payload = {
                    "status": "ready",
                    "user_intent": "查詢 Pi Network 即時價格",
                    "entities": {"symbol": "PI", "market": "crypto"},
                    "tasks": [
                        {
                            "id": "task_1",
                            "name": "查詢 PI 即時價格",
                            "agent": "crypto",
                            "description": "pi network 價格是多少",
                            "dependencies": [],
                        }
                    ],
                    "aggregation_strategy": "combine_all",
                }
            elif "btc" in prompt_lower or "bitcoin" in prompt_lower:
                payload = {
                    "status": "ready",
                    "user_intent": "查詢 BTC 即時價格",
                    "entities": {"symbol": "BTC", "market": "crypto"},
                    "tasks": [
                        {
                            "id": "task_1",
                            "name": "查詢 BTC 即時價格",
                            "agent": "crypto",
                            "description": "BTC 現在多少錢",
                            "dependencies": [],
                        }
                    ],
                    "aggregation_strategy": "combine_all",
                }
            elif "你好" in prompt_lower or "hello" in prompt_lower:
                payload = {
                    "status": "direct_response",
                    "user_intent": "打招呼",
                    "direct_response_text": "你好！有什麼我可以幫忙的嗎？",
                    "tasks": [],
                }
            else:
                payload = {
                    "status": "ready",
                    "user_intent": "一般查詢",
                    "entities": {},
                    "tasks": [
                        {
                            "id": "task_1",
                            "name": "處理查詢",
                            "agent": "chat",
                            "description": "一般查詢",
                            "dependencies": [],
                        }
                    ],
                    "aggregation_strategy": "combine_all",
                }
            return AIMessage(
                content=f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
            )

        if self._tools:
            tool_names = [t.name for t in self._tools]
            if "pi" in prompt_lower and "get_pi_price" in tool_names:
                from langchain_core.messages import AIMessage as AI

                msg = AI(content="")
                msg.tool_calls = [
                    {
                        "name": "get_pi_price",
                        "args": {},
                        "id": "call_pi_001",
                        "type": "tool_call",
                    }
                ]
                return msg
            if "btc" in prompt_lower and "get_crypto_price" in tool_names:
                msg = AIMessage(content="")
                msg.tool_calls = [
                    {
                        "name": "get_crypto_price",
                        "args": {"symbol": "BTC"},
                        "id": "call_btc_001",
                        "type": "tool_call",
                    }
                ]
                return msg

        return AIMessage(content="Mock 回應：查詢完成。")

    def __getattr__(self, name):
        return getattr(object, name)


@pytest.fixture(scope="module")
def manager_fixture():
    """Create manager with MockLLM for testing."""
    from core.agents.bootstrap import bootstrap

    mock_llm = MockLLM()
    return bootstrap(mock_llm, web_mode=False, language="zh-TW")


class TestManagerAgentCodeCleanup:
    """Test 1: _detect_boundary_route 已從 ManagerAgent 移除"""

    def test_detect_boundary_route_removed(self):
        """ManagerAgent 不應包含舊的 boundary route 檢測方法"""
        from core.agents.manager import ManagerAgent

        src = inspect.getsource(ManagerAgent)
        assert "_detect_boundary_route" not in src
        assert "_extract_market_entities" not in src
        assert "_extract_symbol_candidates" not in src
        assert "_symbol_resolver" not in src
        assert "unicodedata" not in src
        assert "UniversalSymbolResolver" not in src


class TestCryptoAgentTools:
    """Test 2: Crypto Agent 有 get_pi_price 工具"""

    def test_crypto_agent_has_pi_tools(self, manager_fixture):
        """Crypto agent 應包含 PI 相關工具"""
        crypto_agent = manager_fixture.agent_registry.get("crypto")
        tools = crypto_agent._get_tools()
        tool_names = [t.name for t in tools]

        assert "get_pi_price" in tool_names
        assert "get_pi_network_info" in tool_names
        assert "get_crypto_price" in tool_names


class TestSystemPrompt:
    """Test 3: System Prompt 不再寫死工具名"""

    def test_prompt_no_hardcoded_tools(self):
        """Prompt 不應硬編碼工具名"""
        from core.agents.prompt_registry import PromptRegistry

        PromptRegistry.load()
        prompt_zh = PromptRegistry.get("crypto_agent", "system", "zh-TW")
        prompt_en = PromptRegistry.get("crypto_agent", "system", "en")

        assert "使用 `get_crypto_price`" not in prompt_zh
        assert "use `get_crypto_price`" not in prompt_en
        assert "工具失敗處理" in prompt_zh or "dedicated tool" in prompt_en


@pytest.mark.asyncio
class TestManagerRouting:
    """Test 4 & 5: Manager 路由流程"""

    async def test_pi_query_routes_to_crypto(self, manager_fixture):
        """PI 查詢應路由到 crypto agent"""
        from core.agents.manager import MANAGER_GRAPH_RECURSION_LIMIT

        config = {
            "configurable": {"thread_id": "test_pi_routing"},
            "recursion_limit": MANAGER_GRAPH_RECURSION_LIMIT,
        }

        result = await manager_fixture.graph.ainvoke(
            {
                "session_id": "test_pi_routing",
                "query": "pi network 價格是多少",
                "history": "",
                "language": "zh-TW",
            },
            config,
        )

        intent = result.get("intent_understanding", {})
        task_graph_dict = result.get("task_graph", {})

        def get_agents_from_graph(node):
            if not node:
                return []
            agents = []
            if isinstance(node, dict):
                if node.get("agent"):
                    agents.append(node["agent"])
                for child in node.get("children", []):
                    agents.extend(get_agents_from_graph(child))
            return agents

        root = task_graph_dict.get("root", {}) if task_graph_dict else {}
        agents_used = get_agents_from_graph(root)

        assert intent.get("status") is not None
        assert "crypto" in agents_used
        assert not intent.get("boundary_routed", False)

    async def test_greeting_returns_direct_response(self, manager_fixture):
        """打招呼應直接回應，不呼叫工具"""

        config = {
            "configurable": {"thread_id": "test_greet"},
            "recursion_limit": 60,
        }

        result = await manager_fixture.graph.ainvoke(
            {
                "session_id": "test_greet",
                "query": "你好",
                "history": "",
                "language": "zh-TW",
            },
            config,
        )

        intent = result.get("intent_understanding", {})
        assert intent.get("status") == "direct_response"
        assert result.get("final_response") is not None
