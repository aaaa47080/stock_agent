"""
Manager Agent - Main Module

Contains the ManagerAgent class definition, graph building, and module-level
utilities (constants, checkpointer, background task runner, etc.).

All mixins are combined here via multiple inheritance to form the complete
ManagerAgent class.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from api.utils import logger
from core.agents.context_budget import (
    CONTEXT_CHAR_BUDGET,
    CompactPrompt,
    format_compact_state,
    history_exceeds_budget,
)
from core.database.experiences import ExperienceStore
from core.tools.universal_resolver import UniversalSymbolResolver

from ..agent_registry import AgentRegistry
from ..analysis_policy import AnalysisPolicyResolver
from ..models import ManagerState
from ..router import AgentRouter
from ..tool_access_resolver import ToolAccessResolver
from ..tool_registry import ToolRegistry
from ..tracing import TraceCollector
from .entity_resolver import EntityResolverMixin
from .execution import ExecutionMixin
from .llm import LLMInvokeMixin
from .memory import MemoryMixin
from .mixin_base import ManagerAgentMixin
from .nodes import NodesMixin
from .response import ResponseMixin
from .routing import RoutingMixin

# ============================================================================
# Module-level variables and constants
# ============================================================================

_experience_store = ExperienceStore()

_background_tasks: set = set()


def _run_background(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _on_done(t):
        _background_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            import logging

            logging.getLogger(__name__).error(
                "[Background task] failed: %s", exc, exc_info=exc
            )

    task.add_done_callback(_on_done)
    return task


def _extract_model_name_for_manager(llm: Any) -> str:
    """Extract model name from a (possibly LanguageAwareLLM-wrapped) LLM."""
    inner = getattr(llm, "_llm", llm)
    return (
        getattr(inner, "model_name", None) or getattr(inner, "model", None) or "unknown"
    )


_per_user_checkpointer: Dict[str, MemorySaver] = {}
_CHECKPOINTER_MAX = 512
_checkpointer_lock = threading.Lock()


def _get_checkpointer(user_id: str, session_id: str) -> MemorySaver:
    """Return a per-session checkpointer to prevent cross-user state leakage."""
    key = f"{user_id}:{session_id}"
    with _checkpointer_lock:
        if key not in _per_user_checkpointer:
            _per_user_checkpointer[key] = MemorySaver()
            if len(_per_user_checkpointer) > _CHECKPOINTER_MAX:
                # Remove oldest entry (FIFO, not true LRU but better than arbitrary)
                oldest_key = next(iter(_per_user_checkpointer))
                _per_user_checkpointer.pop(oldest_key, None)
        return _per_user_checkpointer[key]


# Memory consolidation trigger threshold
MEMORY_CONSOLIDATION_THRESHOLD = 12  # 降到 12 則（約 6 輪對話）
MEMORY_IDLE_TIMEOUT = 300  # 閒置 5 分鐘後整合
MANAGER_GRAPH_RECURSION_LIMIT = 60
MAX_GRAPH_TASKS = 8
AGENT_EXECUTION_TIMEOUT = 60  # seconds


# ============================================================================
# Context budget helpers (module-level for easy patching in tests)
# ============================================================================


def _read_compact_for_manager(user_id: str, session_id: str) -> Optional[CompactPrompt]:
    """Read compact session state, return as CompactPrompt or None."""
    try:
        from core.database.memory import get_memory_store

        store = get_memory_store(user_id, session_id=session_id)
        state = store.read_compact_state()
        if state is None:
            return None
        return CompactPrompt(
            goal=state.goal,
            progress=state.progress,
            open_questions=state.open_questions,
            next_steps=state.next_steps,
        )
    except Exception:
        return None


def _get_history_for_prompt(
    raw_history: str,
    user_id: str,
    session_id: str,
) -> str:
    """Return history string for LLM prompt, respecting CONTEXT_CHAR_BUDGET.

    Priority:
      1. raw_history within budget → return as-is
      2. over budget + compact state available → return formatted compact block
      3. over budget + no compact state → truncate raw history to budget
    """
    import sys

    # Use the facade module's attributes so that test patches on
    # "core.agents.manager.history_exceeds_budget" and
    # "core.agents.manager._read_compact_for_manager" take effect.
    facade = sys.modules.get("core.agents.manager")
    _hEB = facade.history_exceeds_budget if facade else history_exceeds_budget
    _rcfm = facade._read_compact_for_manager if facade else _read_compact_for_manager
    _fcs = facade.format_compact_state if facade else format_compact_state

    if not _hEB(raw_history):
        return raw_history
    compact = _rcfm(user_id, session_id)
    if compact is not None:
        return _fcs(compact)
    # Fallback: truncate to budget (tail — keep most recent)
    return raw_history[-CONTEXT_CHAR_BUDGET:]


# ============================================================================
# TracedGraph — 在 graph.ainvoke 完成後自動記錄 trace summary
# ============================================================================


class _TracedGraph:
    """輕量 proxy，在 ainvoke / invoke 完成後觸發 trace summary logging。

    不修改 graph 本身行為，只附加事後 hook。
    """

    def __init__(self, graph: Any, on_complete: Callable[[], None]):
        self._graph = graph
        self._on_complete = on_complete

    async def ainvoke(
        self, input: Any, config: Optional[Any] = None, **kwargs: Any
    ) -> Any:
        """代理 graph.ainvoke，完成後記錄 trace summary。"""
        try:
            result = await self._graph.ainvoke(input, config, **kwargs)
            return result
        finally:
            try:
                self._on_complete()
            except Exception:
                pass

    def invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        """代理 graph.invoke，完成後記錄 trace summary。"""
        try:
            result = self._graph.invoke(input, config, **kwargs)
            return result
        finally:
            try:
                self._on_complete()
            except Exception:
                pass

    def __getattr__(self, name: str) -> Any:
        """透明代理其他屬性（如 get_graph, stream 等）。"""
        return getattr(self._graph, name)


# ============================================================================
# ManagerAgent
# ============================================================================


class ManagerAgent(
    NodesMixin,
    RoutingMixin,
    EntityResolverMixin,
    ResponseMixin,
    LLMInvokeMixin,
    MemoryMixin,
    ExecutionMixin,
    ManagerAgentMixin,
):
    """
    新版 ManagerAgent

    特點：
    - 開放式意圖理解（無硬編碼）
    - Vending/Restaurant 雙模式
    - DAG 任務執行
    - 選擇性上下文傳輸
    - 長期記憶整合（持久化）
    """

    def __init__(
        self,
        llm_client,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        web_mode: bool = False,
        user_tier: str = "free",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.llm = llm_client
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.web_mode = web_mode
        self.router = AgentRouter(agent_registry)
        self.user_tier = user_tier

        # 用戶和會話標識
        self.user_id = user_id or "anonymous"
        self.session_id = session_id or "default"
        self.tool_access_resolver = ToolAccessResolver(
            user_tier=self.user_tier, user_id=self.user_id
        )
        self.analysis_policy_resolver = AnalysisPolicyResolver()

        # 短期記憶（每個 session 獨立）
        self._memory_cache: Dict[str, Any] = {}

        # 長期記憶存儲（延遲初始化）
        self._memory_store = None

        # 進度回調
        self.progress_callback: Optional[Callable] = None

        # 記憶整合控制（nanobot 風格）
        self._consolidating = False  # 是否正在整合中
        self._consolidation_lock = asyncio.Lock()  # 整合鎖
        self._last_consolidated_index = 0  # 已整合的消息索引
        self._consolidation_task: Optional[asyncio.Task] = None  # 背景整合任務

        self._message_count = 0  # 當前會話消息計數
        self._last_activity_time = time.time()  # 最後活動時間（用於閒置整合）

        # Token 追蹤與模型路由
        from ..model_router import ModelRouter
        from ..token_tracker import TokenTracker

        self._model_router = ModelRouter()
        self._token_tracker = TokenTracker()

        # 結構化追蹤
        self._trace_collector = TraceCollector(
            session_id=self.session_id,
        )

        # 建立 LangGraph
        raw_graph = self._build_graph()
        self.graph = _TracedGraph(raw_graph, self._log_trace_summary)
        self._symbol_resolver = UniversalSymbolResolver()

    def _build_graph(self) -> StateGraph:
        """建立 LangGraph 狀態圖 - 簡化版統一規劃流程"""
        builder = StateGraph(ManagerState)

        # 添加節點（用 tracing wrapper 包裹，trace 失敗不影響主流程）
        builder.add_node(
            "understand_intent", self._wrap_with_trace(self._understand_intent_node)
        )
        builder.add_node("execute_task", self._wrap_with_trace(self._execute_task_node))
        builder.add_node(
            "aggregate_results", self._wrap_with_trace(self._aggregate_results_node)
        )
        builder.add_node(
            "reflect_on_results", self._wrap_with_trace(self._reflect_on_results_node)
        )
        builder.add_node(
            "synthesize_response", self._wrap_with_trace(self._synthesize_response_node)
        )

        # 設定入口
        builder.set_entry_point("understand_intent")

        # 條件邊：根據意圖理解結果決定下一步
        builder.add_conditional_edges(
            "understand_intent",
            self._after_intent_understanding,
            {
                "clarify": END,  # 需要澄清，直接結束（返回 clarification_question）
                "direct_response": END,  # 簡單打招呼/閒聊，直接結束
                "execute": "execute_task",  # 可以執行
            },
        )

        # 任務執行循環
        builder.add_conditional_edges(
            "execute_task",
            self._after_task_execution,
            {
                "next_task": "execute_task",
                "aggregate": "aggregate_results",
            },
        )

        builder.add_edge("aggregate_results", "reflect_on_results")
        builder.add_edge("reflect_on_results", "synthesize_response")
        builder.add_edge("synthesize_response", END)

        return builder.compile(
            checkpointer=_get_checkpointer(self.user_id, self.session_id)
        )

    def _wrap_with_trace(self, node_fn):
        """將 node function 包上 tracing wrapper。

        trace 記錄完全在 try/except 中，失敗不影響主流程。
        wrapper 透過 TraceCollector.start_trace / finish_trace 記錄
        節點的開始時間、結束時間和輸出摘要。
        """

        async def traced_node(state: ManagerState) -> Dict:
            node_name = node_fn.__name__
            trace = None
            try:
                trace = self._trace_collector.start_trace(
                    node_name,
                    input_summary=state.get("query", ""),
                )
            except Exception:
                pass

            try:
                result = await node_fn(state)
            except Exception as exc:
                # trace 記錄錯誤，但仍然 re-raise 讓 LangGraph 處理
                try:
                    if trace:
                        self._trace_collector.finish_trace(trace, error=str(exc)[:200])
                except Exception:
                    pass
                raise

            # 正常完成，記錄 trace
            try:
                if trace:
                    output_summary = (
                        result.get("final_response")
                        or result.get("aggregated_response")
                        or None
                    )
                    self._trace_collector.finish_trace(
                        trace, output_summary=output_summary
                    )
            except Exception:
                pass

            return result

        # 保留原始函數名稱，方便 debug
        traced_node.__name__ = node_fn.__name__
        traced_node.__wrapped__ = node_fn  # type: ignore[attr-defined]
        return traced_node

    def _log_trace_summary(self) -> None:
        """記錄完整 trace summary 到 logger。在 graph 執行完成後呼叫。"""
        try:
            log_text = self._trace_collector.format_trace_log()
            logger.info("[Trace Summary]\n%s", log_text)
            # 重置 collector 供下次請求使用
            self._trace_collector.reset()
            self._trace_collector.session_id = self.session_id
        except Exception:
            pass

    def _emit_progress(self, stage: str, message: str, **extra):
        """發送進度事件"""
        if self.progress_callback:
            payload = {
                "stage": stage,
                "message": message,
            }
            payload.update(extra)
            self.progress_callback(payload)
