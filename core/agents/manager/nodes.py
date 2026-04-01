"""
Manager Agent - Graph Node Implementations

Contains the LangGraph node functions for the ManagerAgent:
- _understand_intent_node: Unified planning entry point
- _execute_task_node: Task execution with parallel support
- _aggregate_results_node: Result aggregation
- _reflect_on_results_node: Quality review
- _synthesize_response_node: Final response generation
- _after_intent_understanding: Conditional routing after intent
- _after_task_execution: Conditional routing after task execution
"""

from __future__ import annotations

import asyncio
from typing import Dict

from api.utils import logger
from core.agents.prompt_guard import sanitize_user_input
from core.agents.prompt_registry import PromptRegistry

from .mixin_base import ManagerAgentMixin


class NodesMixin(ManagerAgentMixin):
    """Graph node implementations for ManagerAgent."""

    async def _understand_intent_node(self, state: Dict) -> Dict:
        """意圖理解節點 - 統一的規劃入口"""
        from ..models import CLEAR_SENTINEL, TaskGraph, TaskNode

        query = state["query"]
        query = sanitize_user_input(
            query
        )  # prompt injection 防護（不修改 state 原始 query）
        history = state.get("history", "")

        from ._main import _get_history_for_prompt

        history = _get_history_for_prompt(
            history,
            user_id=self.user_id or "anonymous",
            session_id=self.session_id,
        )

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
            from ._main import _run_background

            _run_background(self._background_memory_consolidation())

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
        from ..description_loader import get_agent_descriptions

        agents_info = get_agent_descriptions().get_routing_guide()

        # 使用 PromptRegistry 獲取 prompt
        # 讀取長期記憶注入 prompt（nanoclaw 設計：記憶實際作用於意圖理解）
        long_term_memory = self.get_long_term_memory_context()

        # Retrieve relevant past experiences for planner hint
        experience_hint = ""
        try:
            from ._main import _experience_store

            experiences = _experience_store.retrieve_relevant(
                user_id=self.user_id,
                task_family="chat",  # default before intent parsed
                query=query,
                llm=self.llm,
            )
            experience_hint = _experience_store.format_for_prompt(experiences)
        except Exception:
            pass

        long_term_memory_with_hints = long_term_memory or "（尚無長期記憶）"
        if experience_hint:
            long_term_memory_with_hints += f"\n\n{experience_hint}"

        prompt = PromptRegistry.render(
            "manager",
            "intent_understanding",
            agents_info=agents_info,
            query=query,
            history=history or "（無歷史記錄）",
            long_term_memory=long_term_memory_with_hints,
        )

        try:
            response = await self._llm_invoke(prompt, task_type="simple_qa")
            intent_data = self._parse_json_response(
                response, context="intent", fallback_query=query
            )

            status = intent_data.get("status", "ready")

            # 如果需要澄清
            if status == "clarify":
                clarification = intent_data.get(
                    "clarification_question", "請問您想查詢什麼？"
                )
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
                text = intent_data.get(
                    "direct_response_text", "你好！請問有什麼我可以幫忙的？"
                )
                # ✅ 修復：direct_response 也要追蹤對話，確保閒聊也能 extract_facts
                from ._main import _run_background

                _run_background(
                    self._track_conversation(
                        user_message=query,
                        assistant_response=text,
                    )
                )
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
                tasks = [
                    {
                        "id": "task_1",
                        "name": "處理請求",
                        "agent": "chat",
                        "description": query,
                        "dependencies": [],
                    }
                ]

            reconciled_entities = self._reconcile_market_entities(
                query,
                history,
                intent_data.get("entities", {}),
            )
            prior_entities = state.get("intent_understanding", {}).get("entities", {})
            reconciled_entities = self._apply_pronoun_entity_carryover(
                query=query,
                current_entities=reconciled_entities,
                prior_entities=prior_entities
                if isinstance(prior_entities, dict)
                else {},
            )
            query_profile = self.analysis_policy_resolver.build_query_profile(
                query,
                self._extract_symbol_candidates(self._normalize_query_text(query)),
            )
            tasks = self._apply_structural_task_overrides(
                tasks,
                query=query,
                history=history,
                entities=reconciled_entities,
                query_profile=query_profile,
            )

            # 構建任務圖
            root_node = self._build_task_tree(tasks)
            task_graph = TaskGraph(root=root_node)

            return {
                **state_reset,
                "intent_understanding": {
                    "status": "ready",
                    "user_intent": intent_data.get("user_intent", query),
                    "entities": reconciled_entities,
                    "aggregation_strategy": intent_data.get(
                        "aggregation_strategy", "combine_all"
                    ),
                },
                "task_graph": self._task_graph_to_dict(task_graph),
                "execution_mode": "restaurant" if len(tasks) > 1 else "vending",
                "hitl_confirmed": False,
                "_processed_query": query,
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
                "_processed_query": query,
            }

    async def _execute_task_node(self, state: Dict) -> Dict:
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
        all_task_ids = {
            node.id for node in task_graph.all_nodes.values() if node.type == "task"
        }
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
                    dep_id in current_results for dep_id in task.dependencies
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
                    return (
                        task.id,
                        await self._execute_single_task(task, state, results),
                    )

                # 使用 asyncio.gather 並行執行
                results_list = await asyncio.gather(
                    *[
                        execute_with_context(task, current_results)
                        for task in executable_tasks
                    ]
                )

                # 合併結果
                new_results = {**current_results}
                executed_ids = []
                for task_id, result in results_list:
                    new_results[task_id] = result
                    executed_ids.append(task_id)
                    task = next(
                        (item for item in executable_tasks if item.id == task_id), None
                    )
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

    async def _aggregate_results_node(self, state: Dict) -> Dict:
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
            final_result = (
                last_result.get("message", "執行完成，但無有效結果")
                if last_result
                else "執行完成，但無有效結果"
            )
        else:
            # combine_all: 收集所有結果，格式化供 manager 統整
            combined = []
            for task_id, result in task_results.items():
                if result.get("success"):
                    agent_name = result.get("agent_name", "Agent")
                    message = result.get("message", "")
                    task_id_short = task_id.replace("task_", "")
                    combined.append(
                        f"### 任務 {task_id_short} [{agent_name}]\n{message}"
                    )

            if combined:
                final_result = "# Sub-Agent 執行結果\n\n" + "\n\n---\n\n".join(combined)
            else:
                final_result = "執行完成，但無有效結果"

        return {"aggregated_response": final_result}

    async def _reflect_on_results_node(self, state: Dict) -> Dict:
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

        # 快速異常檢查：如果沒有明顯異常就跳過 LLM 審查（節省成本）
        if not self._quick_anomaly_check(task_results):
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
            results_text.append(
                f"[{task_id}] agent={agent}, success={success}\n{msg[:500]}..."
            )  # 截斷避免過長

        if not results_text:
            return {}

        # 調用 LLM 進行審查
        prompt = PromptRegistry.render(
            "manager",
            "reflect_on_results",
            query=query,
            results="\n\n".join(results_text),
        )

        try:
            response = await self._llm_invoke(prompt, task_type="simple_qa")
            reflection_data = self._parse_json_response(response, context="reflection")

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

    async def _synthesize_response_node(self, state: Dict) -> Dict:
        """生成最終回應節點

        修復：檢查是否為新查詢，避免重複返回舊的 final_response
        """
        # 獲取當前查詢和已處理的查詢
        current_query = state.get("query", "")
        processed_query = state.get("_processed_query", "")
        final_response = state.get("final_response")
        analysis_mode = state.get("analysis_mode", "quick")

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
                    k: v for k, v in task_results.items() if k in valid_task_ids
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
                        k: v for k, v in task_results.items() if k in valid_task_ids
                    }

        # 檢查是否有有效的結果
        if not task_results:
            if state.get("tool_failure_detected"):
                issues = state.get("tool_failure_issues") or []
                reason = (
                    issues[0].get("problem")
                    if issues and isinstance(issues[0], dict)
                    else None
                )
                fallback = "目前工具未能取得有效資料，請稍後再試。"
                if reason:
                    fallback = f"{fallback} 原因：{reason}"
                await self._track_conversation(
                    user_message=current_query,
                    assistant_response=fallback,
                    tools_used=[],
                )
                return {
                    "final_response": fallback,
                    "_processed_query": current_query,
                }

            # 沒有執行結果，直接生成回應（注入長期記憶）
            lt_memory = self.get_long_term_memory_context()
            memory_section = f"\n\n## 用戶長期記憶\n{lt_memory}" if lt_memory else ""
            history = state.get("history", "")
            prompt = PromptRegistry.render(
                "manager",
                "synthesize_fallback",
                include_time=False,
                query=current_query,
                memory_section=memory_section,
                history=history or "（無歷史記錄）",
            )
            try:
                response = await self._llm_invoke(prompt, task_type="deep_analysis")
                await self._track_conversation(
                    user_message=current_query,
                    assistant_response=response,
                    tools_used=[],
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

        evidence = self._collect_response_evidence(task_results)
        response_contract = self._build_mode_response_contract(
            analysis_mode=analysis_mode,
            query=current_query,
            evidence=evidence,
        )
        response_format_guidance = self._build_response_format_guidance(
            analysis_mode=analysis_mode,
            query=current_query,
        )

        num_results = len(results_text)

        lt_memory = self.get_long_term_memory_context()
        memory_block = (
            f"\n\n## 用戶長期記憶（偏好與歷史）\n{lt_memory}" if lt_memory else ""
        )

        prompt = PromptRegistry.render(
            "manager",
            "synthesize_runtime",
            include_time=False,
            query=current_query,
            memory_block=memory_block,
            history=state.get("history", "") or "（無歷史記錄）",
            analysis_mode=analysis_mode,
            num_results=num_results,
            results=chr(10).join(results_text),
            evidence=self._format_response_evidence(evidence),
            response_contract=response_contract,
            response_format_guidance=response_format_guidance,
        )

        try:
            response = await self._llm_invoke(prompt, task_type="deep_analysis")
            response = self._finalize_mode_response(
                response=response,
                analysis_mode=analysis_mode,
                evidence=evidence,
                query=current_query,
            )

            # 追蹤對話歷史並觸發記憶整合
            await self._track_conversation(
                user_message=current_query,
                assistant_response=response,
                tools_used=list(task_results.keys()) if task_results else [],
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
                tools_used=[],
            )

            return {
                "final_response": "\n".join(results_text),
                "_processed_query": current_query,
            }

    def _after_intent_understanding(self, state: Dict) -> str:
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

    def _after_task_execution(self, state: Dict) -> str:
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
