"""
Manager Agent — 多 Agent 協調中心

核心功能：
1. 開放式意圖理解 - 不使用硬編碼類別/關鍵字
2. Vending vs Restaurant 模式 - 簡單任務快速路由
3. DAG 執行引擎 - 支援垂直/水平任務
4. 選擇性上下文傳輸 - Sub-Agent 只接收必要資訊
5. 短期記憶整合 - 對話上下文管理
"""
from __future__ import annotations
import json
import asyncio
from typing import Optional, List, Dict, Callable

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from api.utils import logger

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
from .router import AgentRouter
from .prompt_registry import PromptRegistry

# 模組級共用 checkpointer
_checkpointer = MemorySaver()


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
    """

    def __init__(
        self,
        llm_client,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        web_mode: bool = False,
    ):
        self.llm = llm_client
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.web_mode = web_mode
        self.router = AgentRouter(agent_registry)

        # 短期記憶（每個 session 獨立）
        self._memory_cache: Dict[str, ShortTermMemory] = {}

        # 進度回調
        self.progress_callback: Optional[Callable] = None

        # 建立 LangGraph
        self.graph = self._build_graph()

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
        prompt = PromptRegistry.render(
            "manager", "intent_understanding",
            agents_info=agents_info,
            query=query,
            history=history or "（無歷史記錄）"
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
                    "final_response": clarification,
                    "_processed_query": query,
                }
            
            # 如果可以直接回應（打招呼、道謝等閒聊）
            if status == "direct_response":
                text = intent_data.get("direct_response_text", "你好！請問有什麼我可以幫忙的？")
                return {
                    **state_reset,
                    "intent_understanding": {
                        "status": "direct_response",
                        "user_intent": intent_data.get("user_intent", query),
                    },
                    "final_response": text,
                    "_processed_query": query,
                }

            # 直接從意圖理解獲取任務列表
            tasks = intent_data.get("tasks", [])
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
                self._emit_progress("execute_task", f"正在執行: {task.name}")
                result = await self._execute_single_task(task, state, current_results)
                new_results = {**current_results, task.id: result}
                return {
                    "task_results": new_results,
                    "current_task_id": task.id,
                }
            else:
                # 多個任務，並行執行
                task_names = ", ".join([t.name for t in executable_tasks])
                self._emit_progress("execute_task", f"並行執行 {len(executable_tasks)} 個任務: {task_names}")

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
                for task_id, cleaned in cleaned_results.items():
                    if task_id in updated_task_results:
                        if cleaned is None:
                            # 移除有問題的結果
                            del updated_task_results[task_id]
                            logger.info(f"[Reflection] 移除異常結果: {task_id}")
                        else:
                            # 更新為清理後的結果
                            updated_task_results[task_id]["message"] = cleaned
                return {"task_results": updated_task_results}

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
            # 對於 vending 模式，保留 vending_task
            # 對於 restaurant 模式，應該已經在 planning 階段清除了
            if state.get("execution_mode") == "vending":
                task_results = {}
            else:
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
            # 沒有執行結果，直接生成回應
            prompt = f"""用戶問題：{current_query}

請直接回答用戶的問題。如果是投資相關問題，請提供專業但中立的建議，並包含風險提示。"""
            try:
                response = await self._llm_invoke(prompt)
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

        prompt = f"""你是 Manager Agent，負責綜合分析多個專業 Agent 的執行結果，回答用戶的問題。

## 用戶問題
{current_query}

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
            return {
                "final_response": response,
                "_processed_query": current_query,
            }
        except Exception as e:
            logger.error(f"[Manager]Synthesis failed: {e}")
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

    def _emit_progress(self, stage: str, message: str):
        """發送進度事件"""
        if self.progress_callback:
            self.progress_callback({
                "stage": stage,
                "message": message,
            })

    async def _llm_invoke(self, prompt: str) -> str:
        """調用 LLM"""
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return response.content

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

    async def _execute_agent(self, agent, context: AgentContext) -> str:
        """執行單個 agent"""
        from .models import SubTask

        task = SubTask(
            step=0,
            description=context.task_description,
            agent="",
            context={
                "original_query": context.original_query,
                "symbols": context.symbols,
                "dependency_results": context.dependency_results,
                "history": context.history_summary,
                "language": "zh-TW",
            },
        )

        if hasattr(agent, 'execute'):
            result = agent.execute(task)
            if hasattr(result, 'message'):
                return result.message
            return str(result)
        else:
            messages = [HumanMessage(content=context.task_description)]
            response = self.llm.invoke(messages)
            return response.content

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

        context = AgentContext(
            history_summary=state.get("history"),
            original_query=state["query"],
            task_description=task.description or task.name,
            symbols=state.get("intent_understanding", {}).get("entities", {}),
            dependency_results=dep_results,
        )

        try:
            result = await self._execute_agent(agent, context)
            return {
                "success": True,
                "message": result,
                "agent_name": task.agent,
                "task_id": task.id,
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
