"""
Manager Agent — 多 Agent 協調中心

核心功能：
1. 開放式意圖理解 - 不使用硬編碼類別/關鍵字
2. Vending vs Restaurant 模式 - 簡單任務快速路由
3. DAG 執行引擎 - 支援垂直/水平任務
4. 選擇性上下文傳輸 - Sub-Agent 只接收必要資訊
5. 短期記憶整合 - 對話上下文管理
6. 長期記憶整合 - 持久化用戶偏好與歷史
"""
from __future__ import annotations

import json
import time
import asyncio
import re
import unicodedata
from typing import Optional, List, Dict, Callable

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from api.utils import logger
from core.config import TEST_MODE

from .models import (
    ManagerState,
    TaskNode,
    TaskGraph,
    AgentContext,
    ShortTermMemory,
    CLEAR_SENTINEL,
)
from .agent_registry import AgentRegistry
from .tool_registry import ToolRegistry
from .tool_access_resolver import ToolAccessResolver
from .analysis_policy import AnalysisPolicyResolver
from .router import AgentRouter
from .prompt_registry import PromptRegistry
from core.tools.universal_resolver import UniversalSymbolResolver
from utils.user_client_factory import explain_llm_exception

# 模組級共用 checkpointer
_checkpointer = MemorySaver()

# Memory consolidation trigger threshold
MEMORY_CONSOLIDATION_THRESHOLD = 12  # 降到 12 則（約 6 輪對話）
MEMORY_IDLE_TIMEOUT = 300  # 閒置 5 分鐘後整合
MANAGER_GRAPH_RECURSION_LIMIT = 60
MAX_GRAPH_TASKS = 8


# ============================================================================
# ManagerAgent
# ============================================================================

class ManagerAgent:
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
        self.tool_access_resolver = ToolAccessResolver(user_tier=self.user_tier, user_id=self.user_id)
        self.analysis_policy_resolver = AnalysisPolicyResolver()

        # 短期記憶（每個 session 獨立）
        self._memory_cache: Dict[str, ShortTermMemory] = {}

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

        # 建立 LangGraph
        self.graph = self._build_graph()
        self._symbol_resolver = UniversalSymbolResolver()

    def _get_memory_store(self):
        """
        延遲初始化 MemoryStore
        ✅ 跨 session 設計：記憶以 user_id 為主鍵，開新對話仍能讀到歷史記憶
        session_id 只用於 write_long_term 時標記來源，讀取時不過濾
        """
        if TEST_MODE:
            return False

        if self._memory_store is None:
            try:
                from core.database.memory import MemoryStore
                # 傳入 session_id 供寫入標記用，但讀取行為已改為跨 session
                self._memory_store = MemoryStore(self.user_id, self.session_id)
            except ImportError as e:
                import logging
                logging.getLogger(__name__).warning(f"Memory module not available: {e}")
                # 設置為 None 表示記憶功能不可用
                self._memory_store = False
        return self._memory_store

    def _build_graph(self) -> StateGraph:
        """建立 LangGraph 狀態圖 - 簡化版統一規劃流程"""
        builder = StateGraph(ManagerState)

        # 添加節點
        builder.add_node("understand_intent", self._understand_intent_node)
        builder.add_node("execute_task", self._execute_task_node)
        builder.add_node("aggregate_results", self._aggregate_results_node)
        builder.add_node("reflect_on_results", self._reflect_on_results_node)
        builder.add_node("synthesize_response", self._synthesize_response_node)

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
            }
        )

        # 任務執行循環
        builder.add_conditional_edges(
            "execute_task",
            self._after_task_execution,
            {
                "next_task": "execute_task",
                "aggregate": "aggregate_results",
            }
        )

        builder.add_edge("aggregate_results", "reflect_on_results")
        builder.add_edge("reflect_on_results", "synthesize_response")
        builder.add_edge("synthesize_response", END)

        return builder.compile(checkpointer=_checkpointer)

    # ========================================================================
    # 節點實現
    # ========================================================================

    async def _understand_intent_node(self, state: ManagerState) -> Dict:
        """意圖理解節點 - 統一的規劃入口"""
        query = state["query"]
        history = state.get("history", "")

        # ✅ 修復：每次請求開始時從 state 同步 session_id
        # bootstrap 複用 Manager 時 session_id 可能是上一個請求的
        state_session_id = state.get("session_id")
        if state_session_id and state_session_id != self.session_id:
            self.session_id = state_session_id
            self._memory_store = None  # 讓 MemoryStore 重新初始化
            logger.debug(f"[Manager] session_id synced to: {state_session_id}")

        # 閒置整合檢查（在新對話開始時自動檢查）
        if self.check_idle_consolidation():
            logger.info("[Manager] Auto-triggering idle consolidation")
            asyncio.create_task(self._background_memory_consolidation())

        self._emit_progress("understand_intent", "正在分析您的請求...")

        # 檢查是否為新查詢，清除舊的狀態
        processed_query = state.get("_processed_query", "")
        is_new_query = query != processed_query
        state_reset = {}
        if is_new_query and processed_query:
            state_reset = {
                "task_results": {CLEAR_SENTINEL: True},
                "final_response": None,
                "task_graph": None,
            }

        # 使用 description_loader 獲取 agent 資訊
        from .description_loader import get_agent_descriptions
        agents_info = get_agent_descriptions().get_routing_guide()

        # 使用 PromptRegistry 獲取 prompt
        # 讀取長期記憶注入 prompt（nanoclaw 設計：記憶實際作用於意圖理解）
        long_term_memory = self.get_long_term_memory_context()

        prompt = PromptRegistry.render(
            "manager", "intent_understanding",
            agents_info=agents_info,
            query=query,
            history=history or "（無歷史記錄）",
            long_term_memory=long_term_memory or "（尚無長期記憶）"
        )

        try:
            response = await self._llm_invoke(prompt)
            intent_data = self._parse_json_response(response)

            status = intent_data.get("status", "ready")

            # 如果需要澄清
            if status == "clarify":
                clarification = intent_data.get("clarification_question", "請問您想查詢什麼？")
                return {
                    **state_reset,
                    "intent_understanding": {
                        "status": "clarify",
                        "user_intent": intent_data.get("user_intent", query),
                        "clarification_question": clarification,
                    },
                    "execution_mode": "vending",
                    "final_response": clarification,
                    "_processed_query": query,
                }
            
            # 如果可以直接回應（打招呼、道謝等閒聊）
            if status == "direct_response":
                text = intent_data.get("direct_response_text", "你好！請問有什麼我可以幫忙的？")
                # ✅ 修復：direct_response 也要追蹤對話，確保閒聊也能 extract_facts
                asyncio.create_task(self._track_conversation(
                    user_message=query,
                    assistant_response=text,
                ))
                return {
                    **state_reset,
                    "intent_understanding": {
                        "status": "direct_response",
                        "user_intent": intent_data.get("user_intent", query),
                    },
                    "execution_mode": "vending",
                    "final_response": text,
                    "_processed_query": query,
                }

            # 直接從意圖理解獲取任務列表
            tasks = self._normalize_tasks(intent_data.get("tasks", []), query)
            if not tasks:
                tasks = [{
                    "id": "task_1",
                    "name": "處理請求",
                    "agent": "chat",
                    "description": query,
                    "dependencies": [],
                }]

            # 構建任務圖
            root_node = self._build_task_tree(tasks)
            task_graph = TaskGraph(root=root_node)

            return {
                **state_reset,
                "intent_understanding": {
                    "status": "ready",
                    "user_intent": intent_data.get("user_intent", query),
                    "entities": intent_data.get("entities", {}),
                    "aggregation_strategy": intent_data.get("aggregation_strategy", "combine_all"),
                },
                "task_graph": self._task_graph_to_dict(task_graph),
                "execution_mode": "restaurant" if len(tasks) > 1 else "vending",
                "hitl_confirmed": False,
            }

        except Exception as e:
            logger.error(f"[Manager]Intent understanding failed: {e}")
            # 錯誤時使用 fallback
            fallback_task = TaskNode(
                id="fallback_task",
                name="處理請求",
                type="task",
                agent="chat",
                description=query,
            )
            return {
                **state_reset,
                "intent_understanding": {
                    "status": "ready",
                    "user_intent": query,
                },
                "task_graph": self._task_graph_to_dict(TaskGraph(root=fallback_task)),
                "execution_mode": "vending",
            }

    async def _execute_task_node(self, state: ManagerState) -> Dict:
        """執行任務節點 - 支援真正的並行執行

        執行策略：
        - 並行任務（同一層級、無依賴）：使用 asyncio.gather 同時執行
        - 順序任務（有依賴）：按依賴順序執行
        """
        task_graph_dict = state.get("task_graph")
        if not task_graph_dict:
            return {"final_response": "規劃失敗，無法執行"}

        task_graph = self._dict_to_task_graph(task_graph_dict)
        execution_order = task_graph.get_execution_order()
        current_results = state.get("task_results", {})

        # 檢查是否為新查詢，如果是則清除舊結果
        processed_query = state.get("_processed_query", "")
        current_query = state.get("query", "")
        if processed_query and current_query != processed_query:
            current_results = {}

        # 檢查所有任務是否已完成
        all_task_ids = {node.id for node in task_graph.all_nodes.values() if node.type == "task"}
        completed_task_ids = set(current_results.keys())

        if all_task_ids.issubset(completed_task_ids):
            # 所有任務已完成
            return {"current_task_id": None}

        # 找出當前可執行的任務（同一層級、依賴已滿足、尚未執行）
        for level_idx, level in enumerate(execution_order):
            # 過濾出可執行的任務
            executable_tasks = []
            for task in level:
                if task.type == "group":
                    continue
                if task.id in current_results:
                    continue
                deps_completed = all(
                    dep_id in current_results
                    for dep_id in task.dependencies
                )
                if deps_completed:
                    executable_tasks.append(task)

            if not executable_tasks:
                continue

            # 並行執行同一層級的所有任務
            if len(executable_tasks) == 1:
                # 單一任務，直接執行
                task = executable_tasks[0]
                self._emit_progress(
                    "execute_task",
                    f"正在執行: {task.name}",
                    type="agent_start",
                    step=level_idx + 1,
                    task_id=task.id,
                    task_name=task.name,
                    agent=task.agent,
                    parallel=False,
                )
                result = await self._execute_single_task(task, state, current_results)
                self._emit_progress(
                    "execute_task",
                    f"{task.name} {'完成' if result.get('success') else '失敗'}",
                    type="agent_finish",
                    step=level_idx + 1,
                    task_id=task.id,
                    task_name=task.name,
                    agent=task.agent,
                    success=result.get("success", False),
                    parallel=False,
                )
                new_results = {**current_results, task.id: result}
                return {
                    "task_results": new_results,
                    "current_task_id": task.id,
                }
            else:
                # 多個任務，並行執行
                task_names = ", ".join([t.name for t in executable_tasks])
                self._emit_progress(
                    "execute_task",
                    f"並行執行 {len(executable_tasks)} 個任務: {task_names}",
                    type="parallel_group_start",
                    step=level_idx + 1,
                    task_ids=[task.id for task in executable_tasks],
                    task_names=[task.name for task in executable_tasks],
                    parallel=True,
                )

                for task in executable_tasks:
                    self._emit_progress(
                        "execute_task",
                        f"開始執行: {task.name}",
                        type="agent_start",
                        step=level_idx + 1,
                        task_id=task.id,
                        task_name=task.name,
                        agent=task.agent,
                        parallel=True,
                    )

                # 創建並行任務
                async def execute_with_context(task, results):
                    return (task.id, await self._execute_single_task(task, state, results))

                # 使用 asyncio.gather 並行執行
                results_list = await asyncio.gather(*[
                    execute_with_context(task, current_results)
                    for task in executable_tasks
                ])

                # 合併結果
                new_results = {**current_results}
                executed_ids = []
                for task_id, result in results_list:
                    new_results[task_id] = result
                    executed_ids.append(task_id)
                    task = next((item for item in executable_tasks if item.id == task_id), None)
                    self._emit_progress(
                        "execute_task",
                        f"{task.name if task else task_id} {'完成' if result.get('success') else '失敗'}",
                        type="agent_finish",
                        step=level_idx + 1,
                        task_id=task_id,
                        task_name=task.name if task else task_id,
                        agent=task.agent if task else None,
                        success=result.get("success", False),
                        parallel=True,
                    )

                self._emit_progress(
                    "execute_task",
                    f"並行任務已完成: {task_names}",
                    type="parallel_group_finish",
                    step=level_idx + 1,
                    task_ids=executed_ids,
                    parallel=True,
                )

                return {
                    "task_results": new_results,
                    "current_task_id": executed_ids[-1] if executed_ids else None,
                }

        return {"current_task_id": None}

    async def _aggregate_results_node(self, state: ManagerState) -> Dict:
        """彙總結果節點 - 根據聚合策略處理

        聚合策略：
        - combine_all: 收集所有 sub-agent 結果，供 manager 統整
        - last_only: 只取最後一個結果（適用於順序任務）
        """
        task_results = state.get("task_results", {})
        intent = state.get("intent_understanding", {})
        aggregation_strategy = intent.get("aggregation_strategy", "combine_all")

        self._emit_progress("aggregate_results", "正在彙總結果...")

        # 根據聚合策略處理
        if aggregation_strategy == "last_only":
            # 只取最後一個結果
            last_result = None
            for task_id, result in task_results.items():
                if result.get("success"):
                    last_result = result
            final_result = last_result.get("message", "執行完成，但無有效結果") if last_result else "執行完成，但無有效結果"
        else:
            # combine_all: 收集所有結果，格式化供 manager 統整
            combined = []
            for task_id, result in task_results.items():
                if result.get("success"):
                    agent_name = result.get("agent_name", "Agent")
                    message = result.get("message", "")
                    task_id_short = task_id.replace("task_", "")
                    combined.append(f"### 任務 {task_id_short} [{agent_name}]\n{message}")

            if combined:
                final_result = "# Sub-Agent 執行結果\n\n" + "\n\n---\n\n".join(combined)
            else:
                final_result = "執行完成，但無有效結果"

        return {"final_response": final_result}

    async def _reflect_on_results_node(self, state: ManagerState) -> Dict:
        """結果品質審查節點

        檢查 agent 執行結果，過濾異常訊息（如 XXX、N/A、error 等），
        決定是否需要重試或清理結果。
        """
        query = state.get("query", "")
        task_results = state.get("task_results", {})

        self._emit_progress("reflect_on_results", "正在檢查結果品質...")

        # 如果沒有任務結果，直接返回
        if not task_results:
            return {}

        # 格式化結果供 LLM 審查
        results_text = []
        for task_id, result in task_results.items():
            # 防禦性編程：確保 result 是 dict
            if isinstance(result, str):
                result = {"agent_name": "unknown", "message": result, "success": False}
            agent = result.get("agent_name", "unknown")
            msg = result.get("message", "")
            success = result.get("success", False)
            results_text.append(f"[{task_id}] agent={agent}, success={success}\n{msg[:500]}...")  # 截斷避免過長

        if not results_text:
            return {}

        # 調用 LLM 進行審查
        prompt = PromptRegistry.render(
            "manager", "reflect_on_results",
            query=query,
            results="\n\n".join(results_text)
        )

        try:
            response = await self._llm_invoke(prompt)
            reflection_data = self._parse_json_response(response)

            if not reflection_data:
                return {}

            issues = reflection_data.get("issues", [])
            needs_retry = reflection_data.get("needs_retry", False)
            cleaned_results = reflection_data.get("cleaned_results")

            # 如果需要重試，記錄日誌（目前不實現自動重試，避免複雜度）
            if needs_retry:
                logger.warning(f"[Reflection] 檢測到問題需要重試: {issues}")
                # TODO: 未來可以實現自動重試邏輯

            # 如果有清理後的結果，更新 task_results
            if cleaned_results:
                updated_task_results = dict(task_results)
                removed_task_ids = []
                for task_id, cleaned in cleaned_results.items():
                    if task_id in updated_task_results:
                        if cleaned is None:
                            # 移除有問題的結果
                            del updated_task_results[task_id]
                            removed_task_ids.append(task_id)
                            logger.info(f"[Reflection] 移除異常結果: {task_id}")
                        else:
                            # 更新為清理後的結果
                            updated_task_results[task_id]["message"] = cleaned
                state_update = {"task_results": updated_task_results}
                if needs_retry and removed_task_ids:
                    state_update["tool_failure_detected"] = True
                    state_update["tool_failure_issues"] = issues
                return state_update

            return {}

        except Exception as e:
            logger.error(f"[Reflection] 審查失敗: {e}")
            return {}  # 失敗時不影響流程，繼續使用原始結果

    async def _synthesize_response_node(self, state: ManagerState) -> Dict:
        """生成最終回應節點

        修復：檢查是否為新查詢，避免重複返回舊的 final_response
        """
        # 獲取當前查詢和已處理的查詢
        current_query = state.get("query", "")
        processed_query = state.get("_processed_query", "")
        final_response = state.get("final_response")

        # 只有在相同查詢且已有回應時才復用
        if final_response and current_query == processed_query:
            return {}

        # 清除舊的 task_results（新查詢時）
        task_results = state.get("task_results", {})
        is_new_query = current_query != processed_query

        # 如果是新查詢且有舊的 task_results，只保留當前任務相關的結果
        if is_new_query and task_results:
            # 對於 vending 模式，檢查 task_results 是否屬於當前任務圖
            # 對於 restaurant 模式，應該已經在 planning 階段清除了
            task_graph = state.get("task_graph")
            if task_graph:
                # 獲取當前任務圖中的有效 task_ids
                valid_task_ids = set()
                for node in self._dict_to_task_graph(task_graph).all_nodes.values():
                    valid_task_ids.add(node.id)
                # 只保留屬於當前任務圖的結果
                task_results = {
                    k: v for k, v in task_results.items()
                    if k in valid_task_ids
                }
            else:
                # 沒有 task_graph，清空結果（舊查詢的殘留）
                task_results = {}
                # Restaurant 模式：檢查 task_results 是否屬於當前任務圖
                task_graph = state.get("task_graph")
                if task_graph:
                    valid_task_ids = set()
                    for node in self._dict_to_task_graph(task_graph).all_nodes.values():
                        valid_task_ids.add(node.id)
                    task_results = {
                        k: v for k, v in task_results.items()
                        if k in valid_task_ids
                    }

        # 檢查是否有有效的結果
        if not task_results:
            if state.get("tool_failure_detected"):
                issues = state.get("tool_failure_issues") or []
                reason = issues[0].get("problem") if issues and isinstance(issues[0], dict) else None
                fallback = "目前工具未能取得有效資料，請稍後再試。"
                if reason:
                    fallback = f"{fallback} 原因：{reason}"
                await self._track_conversation(
                    user_message=current_query,
                    assistant_response=fallback,
                    tools_used=[]
                )
                return {
                    "final_response": fallback,
                    "_processed_query": current_query,
                }

            # 沒有執行結果，直接生成回應（注入長期記憶）
            lt_memory = self.get_long_term_memory_context()
            memory_section = f"\n\n## 用戶長期記憶\n{lt_memory}" if lt_memory else ""
            prompt = f"""用戶問題：{current_query}{memory_section}

請直接回答用戶的問題。如果是投資相關問題，請提供專業但中立的建議，並包含風險提示。"""
            try:
                response = await self._llm_invoke(prompt)
                await self._track_conversation(
                    user_message=current_query,
                    assistant_response=response,
                    tools_used=[]
                )
                return {
                    "final_response": response,
                    "_processed_query": current_query,
                }
            except Exception as e:
                logger.error(f"[Manager]Synthesis failed: {e}")
                return {
                    "final_response": "抱歉，無法處理您的請求。",
                    "_processed_query": current_query,
                }

        results_text = []
        for task_id, result in task_results.items():
            agent = result.get("agent_name", "unknown")
            msg = result.get("message", "")
            if msg:  # 只添加有內容的結果
                results_text.append(f"[{agent}] {msg}")

        if not results_text:
            return {
                "final_response": "執行完成，但沒有有效結果。請嘗試更具體的問題。",
                "_processed_query": current_query,
            }

        # 改進 prompt：讓 Manager 能夠綜合分析多個 sub-agent 的結果
        num_results = len(results_text)

        lt_memory = self.get_long_term_memory_context()
        memory_block = f"\n\n## 用戶長期記憶（偏好與歷史）\n{lt_memory}" if lt_memory else ""

        prompt = f"""你是 Manager Agent，負責綜合分析多個專業 Agent 的執行結果，回答用戶的問題。

## 用戶問題
{current_query}{memory_block}

## Sub-Agent 執行結果（共 {num_results} 個）
{chr(10).join(results_text)}

---

## 你的任務

作為 Manager，你需要：
1. **綜合分析**所有 sub-agent 返回的結果
2. **直接回答**用戶的問題，不要說「無法」或「抱歉」
3. **比較分析**（如果用戶問的是比較問題）：
   - 列出各標的的關鍵數據對比
   - 分析各自的優缺點
   - 給出客觀的總結
4. **預算計算**（如果用戶提到預算限制）：
   - 計算該預算能購買多少數量
   - 說明進入門檻（如股票整股 vs 零股）
   - 分析小額投資的可行性
5. **投資分析**（如果用戶問投資建議）：
   - 分析各標的的風險與潛在報酬
   - 說明適合的投資者類型
   - 提供客觀建議，但不提供具體買賣信號

## 回應格式

請用自然、友善的語氣生成完整的回應。如果是比較問題，建議使用以下結構：

### 標的比較
| 項目 | 標的A | 標的B |
|------|-------|-------|
| 價格 | ... | ... |
| 你的預算可購買 | ... | ... |
| 風險等級 | ... | ... |

### 分析結論
（綜合分析與建議）

---

請生成回應："""

        try:
            response = await self._llm_invoke(prompt)

            # 追蹤對話歷史並觸發記憶整合
            await self._track_conversation(
                user_message=current_query,
                assistant_response=response,
                tools_used=list(task_results.keys()) if task_results else []
            )

            return {
                "final_response": response,
                "_processed_query": current_query,
            }
        except Exception as e:
            logger.error(f"[Manager]Synthesis failed: {e}")

            # 即使失敗也追蹤
            await self._track_conversation(
                user_message=current_query,
                assistant_response="\n".join(results_text),
                tools_used=[]
            )

            return {
                "final_response": "\n".join(results_text),
                "_processed_query": current_query,
            }

    # ========================================================================
    # 條件路由
    # ========================================================================

    def _after_intent_understanding(self, state: ManagerState) -> str:
        """意圖理解後的路由

        - clarify: 需要向用戶詢問更多資訊
        - direct_response: 直接產生回應（打招呼等跳過任務執行）
        - execute: 可以直接執行任務
        """
        intent = state.get("intent_understanding", {})
        status = intent.get("status", "ready")

        if status == "clarify":
            return "clarify"
        if status == "direct_response":
            return "direct_response"

        return "execute"

    def _after_task_execution(self, state: ManagerState) -> str:
        """任務執行後的路由"""
        current_task_id = state.get("current_task_id")

        if current_task_id is None:
            return "aggregate"

        task_graph_dict = state.get("task_graph")
        if task_graph_dict:
            task_graph = self._dict_to_task_graph(task_graph_dict)
            task_results = state.get("task_results", {})

            for node in task_graph.all_nodes.values():
                # 跳過 group 類型的節點
                if node.type == "group":
                    continue
                if node.id not in task_results:
                    return "next_task"

        return "aggregate"

    # ========================================================================
    # 輔助方法
    # ========================================================================

    def _emit_progress(self, stage: str, message: str, **extra):
        """發送進度事件"""
        if self.progress_callback:
            payload = {
                "stage": stage,
                "message": message,
            }
            payload.update(extra)
            self.progress_callback(payload)

    def _detect_boundary_route(self, query: str) -> Optional[Dict]:
        """用結構化邊界條件處理明確的單市場查詢。"""
        if not query or not query.strip():
            return None

        entity_info = self._extract_market_entities(query)
        matched = {market: value for market, value in entity_info.items() if value}
        if len(matched) != 1:
            return None

        market, symbol = next(iter(matched.items()))
        agent_name = self._resolve_boundary_agent_name(market)
        if not agent_name:
            return None

        display_symbol = symbol.replace(".TW", "") if market == "tw" else symbol
        return {
            "task": {
                "id": "task_1",
                "name": f"處理 {display_symbol} 相關查詢",
                "agent": agent_name,
                "description": query,
                "dependencies": [],
            },
            "entities": entity_info,
        }

    def _extract_market_entities(self, query: str) -> Dict[str, Optional[str]]:
        """從 query 擷取單市場實體，避免把 routing 綁死在 prompt。"""
        normalized = self._normalize_query_text(query)
        result = {"crypto": None, "tw": None, "us": None}

        candidates = self._extract_symbol_candidates(normalized)
        for candidate in candidates:
            resolution = self._symbol_resolver.resolve(candidate)
            for market, value in resolution.items():
                if value and result.get(market) is None:
                    result[market] = value

        return result

    def _build_market_resolution_metadata(
        self,
        query: str,
        entities: Optional[Dict[str, Optional[str]]] = None,
    ) -> Dict[str, object]:
        """建立市場解析狀態，供後續 policy 與 tool selection 使用。"""
        normalized = self._normalize_query_text(query)
        entities = entities or {"crypto": None, "tw": None, "us": None}
        candidates = self._extract_symbol_candidates(normalized)
        unresolved_candidates: List[str] = []
        ambiguous_candidates: List[str] = []

        for candidate in candidates:
            resolution = self._symbol_resolver.resolve(candidate)
            matched_markets = self._symbol_resolver.matched_markets(resolution)
            if not matched_markets:
                unresolved_candidates.append(candidate)
            elif len(matched_markets) > 1:
                ambiguous_candidates.append(candidate)

        matched_entities = {market: value for market, value in entities.items() if value}
        requires_discovery_lookup = bool(candidates) and (
            not matched_entities or bool(ambiguous_candidates)
        )

        return {
            "candidates": candidates,
            "matched_entities": matched_entities,
            "unresolved_candidates": unresolved_candidates,
            "ambiguous_candidates": ambiguous_candidates,
            "requires_discovery_lookup": requires_discovery_lookup,
        }

    def _build_query_policy_metadata(self, query: str, market_resolution: Dict[str, object]) -> Dict[str, object]:
        candidates = market_resolution.get("candidates", []) if isinstance(market_resolution, dict) else []
        if not isinstance(candidates, list):
            candidates = []
        return self.analysis_policy_resolver.build_query_profile(query, candidates)

    def _extract_symbol_candidates(self, query: str) -> List[str]:
        """抽取可能的市場符號候選，保持順序與去重。"""
        raw_candidates = re.findall(r"[A-Za-z]{1,10}|\d{2,6}", query)
        seen = set()
        candidates: List[str] = []
        for candidate in raw_candidates:
            normalized = candidate.strip()
            if not normalized:
                continue
            key = normalized.upper()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(normalized)
        return candidates

    def _normalize_query_text(self, query: str) -> str:
        """先做 Unicode 正規化，降低全形/半形混用造成的 routing 偏差。"""
        return unicodedata.normalize("NFKC", query or "").strip()

    def _resolve_boundary_agent_name(self, market: str) -> Optional[str]:
        """根據 registry metadata 反查對應 agent，避免在 manager 維護名稱映射表。"""
        matched_metadata = []
        for metadata in self.agent_registry.list_all():
            tokens = metadata.name.lower().split("_")
            if market in tokens:
                matched_metadata.append(metadata)

        if not matched_metadata:
            return None

        matched_metadata.sort(key=lambda metadata: (-metadata.priority, metadata.name))
        for metadata in matched_metadata:
            if self.agent_registry.get(metadata.name) is not None:
                return metadata.name
        return None

    def _normalize_tasks(self, tasks: List[dict], query: str) -> List[dict]:
        """清理 LLM 產生的 task plan，避免 graph 因過長或壞資料失控。"""
        if not isinstance(tasks, list):
            return []

        normalized: List[dict] = []
        retained_ids = set()

        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                continue

            task_id = str(task.get("id") or f"task_{index}")
            agent = task.get("agent") or "chat"
            name = str(task.get("name") or task.get("description") or f"任務 {index}")
            description = str(task.get("description") or name)
            dependencies = task.get("dependencies") or []
            if not isinstance(dependencies, list):
                dependencies = []

            normalized.append({
                "id": task_id,
                "name": name,
                "agent": agent,
                "description": description,
                "dependencies": [dep for dep in dependencies if dep in retained_ids],
            })
            retained_ids.add(task_id)

        if len(normalized) > MAX_GRAPH_TASKS:
            logger.warning(
                f"[Manager] Task plan too large ({len(normalized)} tasks), truncating to {MAX_GRAPH_TASKS}"
            )
            normalized = normalized[:MAX_GRAPH_TASKS]
            valid_ids = {task["id"] for task in normalized}
            for task in normalized:
                task["dependencies"] = [dep for dep in task["dependencies"] if dep in valid_ids]

        if not normalized and query:
            return [{
                "id": "task_1",
                "name": "處理請求",
                "agent": "chat",
                "description": query,
                "dependencies": [],
            }]

        return normalized

    async def _llm_invoke(self, prompt: str) -> str:
        """調用 LLM"""
        messages = [HumanMessage(content=prompt)]
        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(messages)
            else:
                response = await asyncio.to_thread(self.llm.invoke, messages)
            return response.content
        except Exception as e:
            raise RuntimeError(explain_llm_exception(e)) from e

    def _parse_json_response(self, response: str) -> dict:
        """解析 JSON 回應"""
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            response = json_match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _get_memory(self, session_id: str) -> ShortTermMemory:
        """獲取或創建短期記憶"""
        if session_id not in self._memory_cache:
            self._memory_cache[session_id] = ShortTermMemory()
        return self._memory_cache[session_id]

    def get_long_term_memory_context(self) -> str:
        """獲取長期記憶上下文（用於 LLM prompt）"""
        try:
            memory_store = self._get_memory_store()
            if not memory_store:
                return ""
            return memory_store.get_memory_context(include_history=True, history_limit=10)
        except Exception as e:
            logger.warning(f"[Manager] Failed to get long-term memory: {e}")
            return ""

    async def _track_conversation(
        self,
        user_message: str,
        assistant_response: str,
        tools_used: Optional[List[str]] = None
    ) -> None:
        """
        追蹤對話歷史並在達到閾值時自動觸發記憶整合（nanoclaw 風格雙層）

        Args:
            user_message: 用戶訊息
            assistant_response: 助手回應
            tools_used: 使用的工具列表
        """
        # 更新活動時間
        self._last_activity_time = time.time()

        # 添加到短期記憶
        memory = self._get_memory(self.session_id)
        memory.add_message("user", user_message)
        memory.add_message("assistant", assistant_response)

        self._message_count += 2
        turn_index = self._message_count // 2  # 輪次編號（1 輪 = 1 user + 1 assistant）

        # ✅ nanoclaw extract_memory：每輪對話立即萃取結構化事實（背景執行）
        # 輕量操作，不需等到 consolidation threshold
        asyncio.create_task(self._extract_facts_background(user_message, assistant_response, turn_index))

        # 計算未整合的消息數量
        unconsolidated = self._message_count - self._last_consolidated_index

        # 達到閾值才觸發重量級 consolidation（摘要 + 長期記憶更新）
        if unconsolidated >= MEMORY_CONSOLIDATION_THRESHOLD and not self._consolidating:
            logger.info(
                f"[Manager] Triggering memory consolidation: "
                f"{unconsolidated} unconsolidated messages"
            )
            # 創建背景任務進行整合
            self._consolidation_task = asyncio.create_task(
                self._background_memory_consolidation()
            )

    async def _extract_facts_background(
        self,
        user_message: str,
        assistant_response: str,
        turn_index: int
    ) -> None:
        """背景執行 nanoclaw 事實萃取，不阻塞對話回應"""
        try:
            memory_store = self._get_memory_store()
            if not memory_store:
                return
            await memory_store.extract_facts_from_turn(
                user_message=user_message,
                assistant_message=assistant_response,
                turn_index=turn_index,
                llm=self.llm,
            )
        except Exception as e:
            logger.warning(f"[Manager] extract_facts_background failed: {e}")

    def check_idle_consolidation(self) -> bool:
        """
        檢查是否需要因閒置而整合記憶

        Returns:
            True 如果需要整合
        """
        if self._consolidating:
            return False

        idle_time = time.time() - self._last_activity_time
        unconsolidated = self._message_count - self._last_consolidated_index

        # 閒置超過 5 分鐘且有未整合消息
        if idle_time >= MEMORY_IDLE_TIMEOUT and unconsolidated > 0:
            logger.info(
                f"[Manager] Idle consolidation triggered: "
                f"idle={idle_time:.0f}s, unconsolidated={unconsolidated}"
            )
            return True
        return False

    async def switch_session(self, new_session_id: str) -> None:
        """
        切換會話並整合舊會話記憶

        Args:
            new_session_id: 新會話 ID
        """
        # 整合舊會話的所有記憶
        if self._message_count > self._last_consolidated_index:
            logger.info(
                f"[Manager] Session switch: consolidating {self._message_count - self._last_consolidated_index} messages"
            )
            await self.consolidate_session_memory()

        # 切換到新會話
        old_session_id = self.session_id
        self.session_id = new_session_id

        # 重置新會話的計數器
        self._message_count = 0
        self._last_consolidated_index = 0
        self._memory_store = None  # 重置記憶存儲以使用新 session_id

        logger.info(f"[Manager] Switched session: {old_session_id} -> {new_session_id}")

    async def _background_memory_consolidation(self) -> bool:
        """
        背景記憶整合（nanobot 風格）

        - 異步執行，不阻塞對話
        - 使用鎖防止重複整合
        - 追蹤已整合的索引

        Returns:
            True 如果整合成功
        """
        if self._consolidating:
            return False

        async with self._consolidation_lock:
            self._consolidating = True
            try:
                return await self._do_consolidation(archive_all=False)
            finally:
                self._consolidating = False

    async def _do_consolidation(self, archive_all: bool = False) -> bool:
        """
        執行實際的記憶整合

        Args:
            archive_all: 是否整合所有消息

        Returns:
            True 如果成功
        """
        try:
            memory = self._get_memory(self.session_id)
            memory_store = self._get_memory_store()
            if not memory_store:
                return False

            if not memory.conversation_history:
                return True

            # 計算要整合的消息範圍
            if archive_all:
                messages_to_consolidate = memory.conversation_history
                keep_count = 0
            else:
                keep_count = MEMORY_CONSOLIDATION_THRESHOLD // 2
                start_idx = self._last_consolidated_index
                end_idx = len(memory.conversation_history) - keep_count

                if end_idx <= start_idx:
                    return True  # 沒有新消息需要整合

                messages_to_consolidate = memory.conversation_history[start_idx:end_idx]

                if not messages_to_consolidate:
                    return True

            logger.info(
                f"[Manager] Consolidating {len(messages_to_consolidate)} messages, "
                f"keeping {keep_count} recent"
            )

            # 準備訊息格式
            messages = []
            for i, msg in enumerate(messages_to_consolidate):
                from datetime import datetime
                messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "tools_used": [],
                })

            # 執行整合
            success = await memory_store.consolidate(
                messages=messages,
                llm=self.llm,
                memory_window=keep_count,
                archive_all=archive_all,
            )

            if success:
                # 更新整合索引
                if archive_all:
                    self._last_consolidated_index = len(memory.conversation_history)
                else:
                    self._last_consolidated_index = len(memory.conversation_history) - keep_count

                logger.info(
                    f"[Manager] Memory consolidation done: "
                    f"last_consolidated_index={self._last_consolidated_index}"
                )

            return success

        except Exception as e:
            logger.error(f"[Manager] Memory consolidation failed: {e}")
            return False

    async def consolidate_session_memory(self) -> bool:
        """
        會話結束時整合所有記憶（手動調用或 /new 命令）

        Returns:
            True 如果整合成功
        """
        async with self._consolidation_lock:
            return await self._do_consolidation(archive_all=True)

    def _get_agents_description(self) -> str:
        """獲取所有 agents 的描述"""
        return self.agent_registry.agents_info_for_prompt()

    def _extract_tasks_from_graph(self, task_graph: dict) -> List[dict]:
        """從任務圖中提取任務列表（用於前端顯示）"""
        tasks = []
        root = task_graph.get("root", {})

        def extract_from_node(node: dict):
            """遞迴提取任務"""
            if node.get("type") == "task":
                tasks.append({
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "agent": node.get("agent"),
                    "description": node.get("description"),
                })
            for child in node.get("children", []):
                extract_from_node(child)

        extract_from_node(root)
        return tasks

    async def _execute_agent(self, agent, context: AgentContext) -> Dict[str, object]:
        """執行單個 agent"""
        from .models import SubTask

        resolved_symbols = {
            market: symbol
            for market, symbol in (context.symbols or {}).items()
            if symbol
        }

        task = SubTask(
            step=0,
            description=context.task_description,
            agent="",
            context={
                "original_query": context.original_query,
                "symbols": resolved_symbols,
                "dependency_results": context.dependency_results,
                "history": context.history_summary,
                "language": "zh-TW",
                "analysis_mode": context.analysis_mode,
                "tool_required": bool(resolved_symbols),
                "allowed_tools": context.allowed_tools,
                "metadata": context.metadata,
            },
        )

        if hasattr(agent, 'execute'):
            result = await asyncio.to_thread(agent.execute, task)
            if hasattr(result, 'message'):
                return {
                    "message": result.message,
                    "success": getattr(result, "success", True),
                    "data": getattr(result, "data", {}),
                    "quality": getattr(result, "quality", "pass"),
                    "quality_fail_reason": getattr(result, "quality_fail_reason", None),
                }
            return {
                "message": str(result),
                "success": True,
                "data": {},
                "quality": "pass",
                "quality_fail_reason": None,
            }
        else:
            messages = [HumanMessage(content=context.task_description)]
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(messages)
            else:
                response = await asyncio.to_thread(self.llm.invoke, messages)
            return {
                "message": response.content,
                "success": True,
                "data": {},
                "quality": "pass",
                "quality_fail_reason": None,
            }

    async def _execute_single_task(self, task: TaskNode, state: ManagerState, completed_results: Dict) -> Dict:
        """執行單個任務"""
        agent = self.agent_registry.get(task.agent)
        if not agent:
            return {
                "success": False,
                "message": f"Agent '{task.agent}' not found",
                "agent_name": task.agent,
                "task_id": task.id,
            }

        dep_results = {}
        for dep_id in task.dependencies:
            if dep_id in completed_results:
                dep_results[dep_id] = completed_results[dep_id]

        market_resolution = self._build_market_resolution_metadata(
            state["query"],
            state.get("intent_understanding", {}).get("entities", {}),
        )
        context = AgentContext(
            history_summary=state.get("history"),
            original_query=state["query"],
            task_description=task.description or task.name,
            symbols=state.get("intent_understanding", {}).get("entities", {}),
            analysis_mode=state.get("analysis_mode", "quick"),
            dependency_results=dep_results,
            allowed_tools=self.tool_access_resolver.resolve_for_agent(task.agent),
            metadata={
                "market_resolution": market_resolution,
                "query_profile": self._build_query_policy_metadata(state["query"], market_resolution),
            },
        )

        try:
            result = await self._execute_agent(agent, context)
            return {
                "success": result.get("success", True),
                "message": result.get("message", ""),
                "agent_name": task.agent,
                "task_id": task.id,
                "data": result.get("data", {}),
                "quality": result.get("quality", "pass"),
                "quality_fail_reason": result.get("quality_fail_reason"),
            }
        except Exception as e:
            logger.error(f"[Manager]Task {task.id} failed: {e}")
            return {
                "success": False,
                "message": f"執行失敗: {str(e)}",
                "agent_name": task.agent,
                "task_id": task.id,
            }

    def _build_task_tree(self, tasks: List[dict]) -> TaskNode:
        """從任務列表構建任務樹"""
        children = []
        for t in tasks:
            node = TaskNode(
                id=t["id"],
                name=t["name"],
                type="task",
                agent=t.get("agent"),
                description=t.get("description"),
                dependencies=t.get("dependencies", []),
                parallel_group=t.get("parallel_group"),
            )
            children.append(node)

        root = TaskNode(
            id="root",
            name="Root",
            type="group",
            children=children,
        )
        return root

    def _task_graph_to_dict(self, graph: TaskGraph) -> dict:
        """將 TaskGraph 轉換為 dict"""
        def node_to_dict(node: TaskNode) -> dict:
            return {
                "id": node.id,
                "name": node.name,
                "type": node.type,
                "agent": node.agent,
                "description": node.description,
                "dependencies": node.dependencies,
                "parallel_group": node.parallel_group,
                "children": [node_to_dict(c) for c in node.children],
            }
        return {"root": node_to_dict(graph.root)}

    def _dict_to_task_graph(self, data: dict) -> TaskGraph:
        """從 dict 重建 TaskGraph"""
        def dict_to_node(d: dict) -> TaskNode:
            return TaskNode(
                id=d["id"],
                name=d["name"],
                type=d["type"],
                agent=d.get("agent"),
                description=d.get("description"),
                dependencies=d.get("dependencies", []),
                parallel_group=d.get("parallel_group"),
                children=[dict_to_node(c) for c in d.get("children", [])],
            )
        root = dict_to_node(data["root"])
        return TaskGraph(root=root)
