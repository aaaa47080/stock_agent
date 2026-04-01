"""
Manager Agent - Task Execution

Contains agent and task execution:
- _execute_agent: Execute a single agent
- _execute_single_task: Execute a single task node
- _extract_tasks_from_graph: Extract task list from graph (for frontend display)
"""

from __future__ import annotations

import asyncio
from typing import Dict, List

from langchain_core.messages import HumanMessage

from api.utils import logger

from ..models import AgentContext, TaskNode
from .mixin_base import ManagerAgentMixin


class ExecutionMixin(ManagerAgentMixin):
    """Task execution for ManagerAgent."""

    def _extract_tasks_from_graph(self, task_graph: dict) -> List[dict]:
        """從任務圖中提取任務列表（用於前端顯示）"""
        tasks = []
        root = task_graph.get("root", {})

        def extract_from_node(node: dict):
            """遞迴提取任務"""
            if node.get("type") == "task":
                tasks.append(
                    {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "agent": node.get("agent"),
                        "description": node.get("description"),
                    }
                )
            for child in node.get("children", []):
                extract_from_node(child)

        extract_from_node(root)
        return tasks

    async def _execute_agent(self, agent, context: AgentContext) -> Dict[str, object]:
        """執行單個 agent"""
        from ..models import SubTask

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

        if hasattr(agent, "execute"):
            result = await asyncio.to_thread(agent.execute, task)
            if hasattr(result, "message"):
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
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return {
                "message": content,
                "success": True,
                "data": {},
                "quality": "pass",
                "quality_fail_reason": None,
            }

    async def _execute_single_task(
        self, task: TaskNode, state: Dict, completed_results: Dict
    ) -> Dict:
        """執行單個任務"""
        from ._main import AGENT_EXECUTION_TIMEOUT

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
        query_profile = self._build_query_policy_metadata(
            state["query"], market_resolution
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
                "query_profile": query_profile,
            },
        )

        try:
            result = await asyncio.wait_for(
                self._execute_agent(agent, context),
                timeout=AGENT_EXECUTION_TIMEOUT,
            )
            result_data = result.get("data", {})
            if not isinstance(result_data, dict):
                result_data = {}
            result_data = {
                **self._build_response_trace_metadata(market_resolution, query_profile),
                **result_data,
            }
            return {
                "success": result.get("success", True),
                "message": result.get("message", ""),
                "agent_name": task.agent,
                "task_id": task.id,
                "data": result_data,
                "quality": result.get("quality", "pass"),
                "quality_fail_reason": result.get("quality_fail_reason"),
            }
        except asyncio.TimeoutError:
            logger.error(
                f"[Manager]Task {task.id} timed out after {AGENT_EXECUTION_TIMEOUT}s"
            )
            return {
                "success": False,
                "message": f"執行逾時: 任務超過 {AGENT_EXECUTION_TIMEOUT} 秒未完成",
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
