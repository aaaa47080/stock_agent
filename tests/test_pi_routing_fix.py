"""
測試 PI 路由與工具選擇修復
- 使用 MockLLM 替代真實 API，驗證流程邏輯
- 不需要外網連線
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage

# ── Mock LLM ────────────────────────────────────────────────────────────────


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

    def _make_response(self, prompt: str) -> AIMessage:
        prompt_lower = prompt.lower()

        # Manager intent understanding: 回傳 JSON task plan
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

        # Agent 工具呼叫決策
        if self._tools:
            tool_names = [t.name for t in self._tools]
            # 優先選 PI 專用工具
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
            # BTC → get_crypto_price
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
        # 讓 LanguageAwareLLM 的 __getattr__ 不炸
        return getattr(object, name)


# ── Test Cases ───────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
results = []


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, label, detail))
    print(f"  {status} {label}" + (f"  ({detail})" if detail else ""))
    return condition


# ── Test 1: _detect_boundary_route 已移除 ────────────────────────────────────

print("\n[Test 1] _detect_boundary_route 已從 ManagerAgent 移除")
import inspect

from core.agents.bootstrap import bootstrap
from core.agents.manager import ManagerAgent

src = inspect.getsource(ManagerAgent)
check("_detect_boundary_route 不存在", "_detect_boundary_route" not in src)
check("_extract_market_entities 不存在", "_extract_market_entities" not in src)
check("_extract_symbol_candidates 不存在", "_extract_symbol_candidates" not in src)
check("_symbol_resolver 不存在", "_symbol_resolver" not in src)
check("unicodedata import 已移除", "unicodedata" not in src)
check("UniversalSymbolResolver import 已移除", "UniversalSymbolResolver" not in src)


# ── Test 2: Crypto Agent 有 get_pi_price 工具 ────────────────────────────────

print("\n[Test 2] Crypto Agent 工具清單包含 get_pi_price")
mock_llm = MockLLM()
manager = bootstrap(mock_llm, web_mode=False, language="zh-TW")

crypto_agent = manager.agent_registry.get("crypto")
tools = crypto_agent._get_tools()
tool_names = [t.name for t in tools]

check(
    "crypto agent 有 get_pi_price",
    "get_pi_price" in tool_names,
    f"工具數={len(tool_names)}",
)
check("crypto agent 有 get_pi_network_info", "get_pi_network_info" in tool_names)
check("crypto agent 有 get_crypto_price", "get_crypto_price" in tool_names)


# ── Test 3: System Prompt 不再寫死工具名 ─────────────────────────────────────

print("\n[Test 3] crypto_agent.yaml system prompt 不再強制指定工具")
from core.agents.prompt_registry import PromptRegistry

PromptRegistry.load()
prompt_zh = PromptRegistry.get("crypto_agent", "system", "zh-TW")
prompt_en = PromptRegistry.get("crypto_agent", "system", "en")

# 舊的寫法：「使用 `get_crypto_price`」（絕對指令）
old_pattern_zh = "使用 `get_crypto_price`"
old_pattern_en = "use `get_crypto_price`"

check("ZH prompt 不再寫死 get_crypto_price", old_pattern_zh not in prompt_zh)
check("EN prompt 不再寫死 get_crypto_price", old_pattern_en not in prompt_en)
check("ZH prompt 有工具失敗重試指引", "工具失敗處理" in prompt_zh)
check("EN prompt 有 dedicated tool 描述", "dedicated tool" in prompt_en)


# ── Test 4: Manager 路由流程（用 MockLLM 實際走一次 graph）─────────────────────

print("\n[Test 4] Manager graph 實際路由 PI 查詢 → crypto agent")


async def run_routing_test():
    from core.agents.manager import MANAGER_GRAPH_RECURSION_LIMIT

    config = {
        "configurable": {"thread_id": "test_pi_routing"},
        "recursion_limit": MANAGER_GRAPH_RECURSION_LIMIT,
    }

    result = await manager.graph.ainvoke(
        {
            "session_id": "test_pi_routing",
            "query": "pi network 價格是多少",
            "history": "",
            "language": "zh-TW",
        },
        config,
    )

    return result


result = asyncio.run(run_routing_test())

intent = result.get("intent_understanding", {})
task_graph_dict = result.get("task_graph", {})


# 從 task graph 找 agent
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

check(
    "intent_understanding 有 status",
    bool(intent.get("status")),
    intent.get("status", "missing"),
)
check("PI 查詢路由到 crypto agent", "crypto" in agents_used, f"agents={agents_used}")
check(
    "boundary_routed 不存在（走 LLM 路由）",
    not intent.get("boundary_routed", False),
    "boundary_routed=" + str(intent.get("boundary_routed")),
)


# ── Test 5: 打招呼 → direct_response，不呼叫工具 ──────────────────────────────

print("\n[Test 5] 打招呼 → direct_response（不走 agent）")


async def run_greet_test():
    config = {
        "configurable": {"thread_id": "test_greet"},
        "recursion_limit": 60,
    }
    return await manager.graph.ainvoke(
        {
            "session_id": "test_greet",
            "query": "你好",
            "history": "",
            "language": "zh-TW",
        },
        config,
    )


greet_result = asyncio.run(run_greet_test())
greet_intent = greet_result.get("intent_understanding", {})
check(
    "你好 → direct_response",
    greet_intent.get("status") == "direct_response",
    f"status={greet_intent.get('status')}",
)
check("有直接回應文字", bool(greet_result.get("final_response")))


# ── Summary ──────────────────────────────────────────────────────────────────

total = len(results)
passed = sum(1 for r in results if r[0] == PASS)
failed = total - passed

print(f"\n{'=' * 60}")
print(
    f"  測試結果：{PASS} {passed}/{total} 通過  {'❌ ' + str(failed) + ' 失敗' if failed else ''}"
)
print(f"{'=' * 60}")

if failed:
    print("\n失敗項目：")
    for s, _line, d in results:
        if s == FAIL:
            print(f"  {s} {_line}  {d}")
    sys.exit(1)
