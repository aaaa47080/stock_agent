"""
Tests for chat history inheritance fixes:

1. list-content handling (anti-garbled output)
2. history injection into synthesize_fallback and synthesize_runtime prompts
3. tool_compactor config passthrough
4. Integration: LLM round-trip with gpt-5-mini (marked slow)
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agents.models import SubTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeTool:
    name = "fake_tool"
    description = "A fake tool"
    args = {"query": {"type": "string"}}

    def invoke(self, kwargs):
        return {"result": "ok"}


class _FakeToolRegistry:
    def list_for_agent(self, agent_name):
        return []


class _DummyAgent:
    """Minimal agent that doesn't extend BaseReActAgent (for execution mixin tests)."""

    def execute(self, task):
        from core.agents.models import AgentResult

        return AgentResult(success=True, message="done", agent_name="dummy")


# ---------------------------------------------------------------------------
# 1. list-content handling — LLM returns list[dict] content
# ---------------------------------------------------------------------------


class TestListContentHandling:
    """Ensure response.content is normalized from list[dict] to str everywhere."""

    def test_base_react_agent_summarize_tool_result_list_content(self):
        from core.agents.base_react_agent import BaseReActAgent

        class DummyAgent(BaseReActAgent):
            @property
            def name(self) -> str:
                return "test"

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content=[
                {"type": "text", "text": "BTC is at "},
                {"type": "text", "text": "$100,000"},
            ]
        )

        agent = DummyAgent(llm, _FakeToolRegistry())
        task = SubTask(
            step=0,
            description="test",
            agent="test",
            context={
                "language": "zh-TW",
                "tool_required": True,
                "symbols": {"crypto": "BTC"},
            },
        )

        with patch(
            "core.agents.base_react_agent.get_allowed_tools",
            return_value=["fake_tool"],
        ):
            from core.agents.tool_registry import ToolMetadata

            meta = ToolMetadata(
                name="fake_tool",
                description="test",
                input_schema={"symbol": "str"},
                handler=_FakeTool(),
                allowed_agents=["test"],
                role="market_lookup",
                priority=10,
            )
            agent._filter_tool_metas = lambda task=None: [meta]
            agent._get_tool_metas = lambda task=None: [meta]

            result = agent.execute(task)

        assert isinstance(result.message, str)
        assert "BTC is at $100,000" in result.message

    def test_base_react_agent_execute_without_tools_list_content(self):
        from core.agents.base_react_agent import BaseReActAgent

        class DummyAgent(BaseReActAgent):
            @property
            def name(self) -> str:
                return "chat"

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content=[
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "World"},
            ]
        )

        agent = DummyAgent(llm, _FakeToolRegistry())
        task = SubTask(
            step=0,
            description="Hi",
            agent="chat",
            context={"language": "en"},
        )
        result = agent.execute(task)

        assert result.success is True
        assert result.message == "Hello World"

    @pytest.mark.asyncio
    async def test_llm_invoke_mixin_list_content(self):
        from core.agents.manager.llm import LLMInvokeMixin

        class FakeManager(LLMInvokeMixin):
            def __init__(self):
                self.llm = MagicMock()
                self._token_tracker = MagicMock()
                self._token_tracker.is_over_budget.return_value = False

        mgr = FakeManager()
        mgr.llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content=[
                    {"type": "text", "text": "Part1"},
                    {"type": "text", "text": "Part2"},
                ],
                usage_metadata=None,
            )
        )

        result = await mgr._llm_invoke("test prompt", task_type="simple_qa")
        assert result == "Part1Part2"

    @pytest.mark.asyncio
    async def test_execution_mixin_list_content(self):
        from core.agents.manager.execution import ExecutionMixin
        from core.agents.models import AgentContext

        class FakeManager(ExecutionMixin):
            def __init__(self):
                self.llm = MagicMock()

        mgr = FakeManager()
        mgr.llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content=[
                    {"type": "text", "text": "Answer: "},
                    {"type": "text", "text": "42"},
                ]
            )
        )

        ctx = AgentContext(
            history_summary="",
            original_query="test",
            task_description="test",
            symbols={},
            analysis_mode="quick",
            dependency_results={},
            allowed_tools=[],
            metadata={},
        )

        class NoExecuteAgent:
            pass

        result = await mgr._execute_agent(NoExecuteAgent(), ctx)
        assert result["message"] == "Answer: 42"

    def test_watcher_list_content(self):
        from core.agents.watcher import WatcherAgent

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content=[
                {"type": "text", "text": '```json\n{"status": "PASS", "feedback": "ok"}\n```'},
            ]
        )

        agent = WatcherAgent(llm)
        result = agent.critique("BTC?", "check price", "BTC is $95k")
        assert isinstance(result, dict)
        assert result.get("status") == "PASS"

    def test_experience_store_list_content(self):
        from core.database.experiences import ExperienceStore

        store = ExperienceStore()
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content=[{"type": "text", "text": "1,2"}],
        )

        candidates = [
            {"query_text": "q1", "outcome": "pass", "tools_used": []},
            {"query_text": "q2", "outcome": "pass", "tools_used": []},
        ]
        result = store._layer3_llm_rerank(
            candidates=candidates,
            current_query="test",
            llm=llm,
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_memory_store_list_content(self):
        from core.database.memory import MemoryStore

        store = MemoryStore.__new__(MemoryStore)
        store.user_id = "test"
        store.session_id = "test"
        store._scope = "test"

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content=[
                {"type": "text", "text": '```json\n{"facts": [{"key": "k", "value": "v", "source_turn": 0, "confidence": "high"}]}\n```'},
            ]
        )

        with patch.object(store, "facts_to_text", return_value=""):
            with patch.object(store, "write_facts"):
                result = await store.extract_facts_from_turn(
                    "hello", "hi", 0, llm
                )
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# 2. History injection in synthesize prompts
# ---------------------------------------------------------------------------


class TestHistoryInjectionInPrompts:
    """Verify that synthesize_fallback and synthesize_runtime include history."""

    def test_synthesize_fallback_prompt_contains_history(self):
        from core.agents.prompt_registry import PromptRegistry

        rendered = PromptRegistry.render(
            "manager",
            "synthesize_fallback",
            query="那他現在多少錢？",
            memory_section="",
            history="用戶：比特幣怎麼樣了？\n助手：BTC 目前 $95,000",
        )

        assert "比特幣怎麼樣了" in rendered
        assert "對話歷史" in rendered

    def test_synthesize_runtime_prompt_contains_history(self):
        from core.agents.prompt_registry import PromptRegistry

        rendered = PromptRegistry.render(
            "manager",
            "synthesize_runtime",
            query="他呢？",
            memory_block="",
            history="用戶：以太坊多少？\n助手：ETH 約 $3,500",
            analysis_mode="quick",
            num_results=1,
            results="[crypto] ETH = $3,500",
            evidence="",
            response_contract="",
            response_format_guidance="",
        )

        assert "以太坊多少" in rendered
        assert "對話歷史" in rendered

    def test_synthesize_fallback_uses_pronoun_resolution_hint(self):
        from core.agents.prompt_registry import PromptRegistry

        rendered = PromptRegistry.render(
            "manager",
            "synthesize_fallback",
            query="那他呢？",
            memory_section="",
            history="用戶：台積電多少？",
        )

        assert "代詞" in rendered


# ---------------------------------------------------------------------------
# 3. Tool compactor config passthrough
# ---------------------------------------------------------------------------


class TestToolCompactorConfigPassthrough:
    """Ensure _CompactingToolWrapper passes config to underlying tools."""

    def test_invoke_passes_config(self):
        from core.agents.tool_compactor import wrap_tool

        inner = MagicMock()
        inner.name = "test_tool"
        inner.invoke.return_value = "result"

        wrapped = wrap_tool(inner, owner_id="u1")

        wrapped.invoke("input_data", config={"tags": ["test"]})

        inner.invoke.assert_called_once_with(
            "input_data", config={"tags": ["test"]}
        )

    def test_ainvoke_delegates_to_original(self):
        from core.agents.tool_compactor import wrap_tool

        inner = MagicMock()
        inner.name = "test_tool"
        inner.ainvoke = AsyncMock(return_value="async_result")

        wrapped = wrap_tool(inner, owner_id="u1")

        result = asyncio.get_event_loop().run_until_complete(
            wrapped.ainvoke("input_data", config={"tags": ["test"]})
        )

        assert result == "async_result"
        inner.ainvoke.assert_called_once_with(
            "input_data", config={"tags": ["test"]}
        )

    def test_ainvoke_falls_back_to_invoke_when_no_async(self):
        from core.agents.tool_compactor import wrap_tool

        inner = MagicMock()
        inner.name = "test_tool"
        inner.invoke.return_value = "sync_result"
        del inner.ainvoke

        wrapped = wrap_tool(inner, owner_id="u1")

        result = asyncio.get_event_loop().run_until_complete(
            wrapped.ainvoke("input_data")
        )

        assert result == "sync_result"


# ---------------------------------------------------------------------------
# 4. Integration: LLM round-trip with gpt-5-mini
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestLLMRoundTrip:
    """Real LLM round-trip tests using gpt-5-mini from .env (marked slow)."""

    @pytest.fixture(autouse=True)
    def _load_env(self):
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or not api_key.startswith("sk-"):
            pytest.skip("OPENAI_API_KEY not configured")

    def _make_llm(self):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-5-mini", temperature=0)

    def test_list_content_round_trip(self):
        """Verify the model returns content that our normalization handles."""
        llm = self._make_llm()
        response = llm.invoke([{"role": "user", "content": "Say exactly: hello world"}])

        content = response.content
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )

        assert isinstance(content, str)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_manager_llm_invoke_round_trip(self):
        """Full manager _llm_invoke with gpt-5-mini."""
        from core.agents.manager.llm import LLMInvokeMixin

        class FakeManager(LLMInvokeMixin):
            def __init__(self):
                self.llm = self._make_llm()
                self._token_tracker = MagicMock()
                self._token_tracker.is_over_budget.return_value = False

            def _make_llm(self):
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(model="gpt-5-mini", temperature=0)

        mgr = FakeManager()
        result = await mgr._llm_invoke("Reply with just: OK", task_type="simple_qa")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_history_context_round_trip(self):
        """Verify history context is passed through prompt and model understands it."""
        from core.agents.prompt_registry import PromptRegistry

        llm = self._make_llm()

        prompt = PromptRegistry.render(
            "manager",
            "synthesize_fallback",
            query="那他現在多少錢？",
            memory_section="",
            history="用戶：比特幣怎麼樣了？\n助手：BTC 目前價格約 $95,000",
        )

        from langchain_core.messages import HumanMessage, SystemMessage

        response = llm.invoke(
            [
                SystemMessage(content="你是一個專業的加密貨幣分析助手。"),
                HumanMessage(content=prompt),
            ]
        )

        content = response.content
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )

        assert isinstance(content, str)
        assert len(content) > 0
        assert "BTC" in content or "比特幣" in content


# ---------------------------------------------------------------------------
# 5. Fixes for maxmini-reported issues
# ---------------------------------------------------------------------------


class TestMemoryStoreRetryOnImportError:
    """Issue 1: _memory_store should retry on next call after ImportError."""

    def test_retry_after_import_error(self):
        from core.agents.manager.memory import MemoryMixin

        class FakeManager(MemoryMixin):
            def __init__(self):
                self._memory_store = None
                self.user_id = "u1"
                self.session_id = "s1"

        mgr = FakeManager()

        with patch("core.config.TEST_MODE", False):
            with patch(
                "core.database.memory.MemoryStore",
                side_effect=ImportError("no module"),
            ):
                result = mgr._get_memory_store()
                assert result is None
                assert mgr._memory_store is None

            with patch(
                "core.database.memory.MemoryStore",
                return_value="memory_ok",
            ):
                result = mgr._get_memory_store()
                assert result == "memory_ok"
                assert mgr._memory_store == "memory_ok"

    def test_force_memory_in_test_mode(self):
        from core.agents.manager.memory import MemoryMixin

        class FakeManager(MemoryMixin):
            def __init__(self):
                self._memory_store = None
                self.user_id = "u1"
                self.session_id = "s1"

        mgr = FakeManager()

        with patch("core.config.TEST_MODE", True):
            result = mgr._get_memory_store()
            assert result is None

            mgr._force_memory_in_test = True
            with patch(
                "core.database.memory.MemoryStore",
                return_value="test_memory",
            ):
                result = mgr._get_memory_store()
                assert result == "test_memory"


class TestConsolidateIndexLogic:
    """Issue 2: consolidate() should not double-slice with stale DB index."""

    def test_consolidate_uses_full_messages_slice(self):
        from core.database.memory import MemoryStore

        store = MemoryStore.__new__(MemoryStore)
        store.user_id = "u1"
        store.session_id = "s1"
        store._last_consolidated_index = None

        messages = [
            {"role": "user", "content": f"msg {i}", "timestamp": "2026-01-01"}
            for i in range(10)
        ]

        with patch.object(store, "read_long_term", return_value=""):
            with patch.object(store, "append_history"):
                with patch.object(store, "write_long_term"):
                    with patch.object(store, "set_last_consolidated_index"):
                        with patch.object(store, "write_compact_state"):
                            llm = MagicMock()
                            llm.invoke.return_value = MagicMock(
                                content=json.dumps({
                                    "history_entry": "summary",
                                    "memory_update": "mem",
                                    "compact_state": {
                                        "goal": "g",
                                        "progress": "p",
                                        "open_questions": "",
                                        "next_steps": "",
                                    },
                                })
                            )

                            async def run():
                                return await store.consolidate(
                                    messages=messages,
                                    llm=llm,
                                    memory_window=4,
                                )

                            result = asyncio.get_event_loop().run_until_complete(run())

        assert result is True
        invoke_prompt = llm.invoke.call_args[0][0][0].content
        assert "msg 0" in invoke_prompt
        assert "msg 7" in invoke_prompt


class TestExtractFactsToolsUsed:
    """Issue 4: _extract_facts_background should forward tools_used."""

    @pytest.mark.asyncio
    async def test_extract_facts_background_passes_tools_used(self):
        from core.agents.manager.memory import MemoryMixin

        class FakeManager(MemoryMixin):
            def __init__(self):
                self._memory_store = None
                self.llm = MagicMock()

        mgr = FakeManager()

        mock_store = MagicMock()
        mock_store.extract_facts_from_turn = AsyncMock()

        with patch.object(mgr, "_get_memory_store", return_value=mock_store):
            await mgr._extract_facts_background(
                "BTC?", "BTC is $95k", 1, tools_used=["get_crypto_price"]
            )

        mock_store.extract_facts_from_turn.assert_called_once_with(
            user_message="BTC?",
            assistant_message="BTC is $95k",
            turn_index=1,
            llm=mgr.llm,
            tools_used=["get_crypto_price"],
        )

    @pytest.mark.asyncio
    async def test_extract_facts_from_turn_includes_tools_in_prompt(self):
        from core.database.memory import MemoryStore

        store = MemoryStore.__new__(MemoryStore)
        store.user_id = "u1"
        store.session_id = "s1"
        store._last_consolidated_index = None

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content='{"facts": []}',
        )

        with patch.object(store, "facts_to_text", return_value=""):
            with patch.object(store, "write_facts"):
                await store.extract_facts_from_turn(
                    "查 BTC 價格",
                    "BTC $95k",
                    turn_index=1,
                    llm=llm,
                    tools_used=["get_crypto_price"],
                )

        call_args = llm.invoke.call_args[0][0][0].content
        assert "get_crypto_price" in call_args

    @pytest.mark.asyncio
    async def test_extract_facts_from_turn_no_tools_section_when_empty(self):
        from core.database.memory import MemoryStore

        store = MemoryStore.__new__(MemoryStore)
        store.user_id = "u1"
        store.session_id = "s1"
        store._last_consolidated_index = None

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content='{"facts": []}',
        )

        with patch.object(store, "facts_to_text", return_value=""):
            with patch.object(store, "write_facts"):
                await store.extract_facts_from_turn(
                    "你好",
                    "嗨",
                    turn_index=1,
                    llm=llm,
                    tools_used=None,
                )

        call_args = llm.invoke.call_args[0][0][0].content
        assert "本輪使用工具" not in call_args
