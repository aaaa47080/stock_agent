"""
Manager Agent - Routing and Task Management

Contains task routing, normalization, and task graph management:
- _detect_boundary_route: Structured boundary conditions for single-market queries
- _apply_structural_task_overrides: Structural market resolution correction
- _normalize_tasks: Clean LLM-generated task plans
- _build_task_tree: Build task tree from task list
- _task_graph_to_dict: Convert TaskGraph to dict
- _dict_to_task_graph: Rebuild TaskGraph from dict
"""

from __future__ import annotations

from typing import Dict, List, Optional

from api.utils import logger

from ..models import TaskGraph, TaskNode
from .mixin_base import ManagerAgentMixin


class RoutingMixin(ManagerAgentMixin):
    """Routing and task management for ManagerAgent."""

    def _detect_boundary_route(self, query: str, history: str = "") -> Optional[Dict]:
        """用結構化邊界條件處理明確的單市場查詢。"""
        if not query or not query.strip():
            return None

        entity_info = self._extract_market_entities(query, history=history)
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

    def _apply_structural_task_overrides(
        self,
        tasks: List[dict],
        query: str,
        history: str,
        entities: Dict[str, Optional[str]],
        query_profile: Dict[str, object],
    ) -> List[dict]:
        """Use structural market resolution to correct single-task routing."""
        if not tasks:
            return tasks
        if len(tasks) != 1:
            return tasks

        matched_entities = entities if isinstance(entities, dict) else {}
        matched_markets = [
            market for market, value in matched_entities.items() if value
        ]
        if len(matched_markets) == 1:
            market = matched_markets[0]
            target_agent = self._resolve_boundary_agent_name(market)
            if target_agent:
                normalized_task = dict(tasks[0])
                normalized_task["description"] = query
                if normalized_task.get("agent") != target_agent:
                    normalized_task["agent"] = target_agent
                    symbol = matched_entities.get(market, "")
                    display_symbol = (
                        symbol.replace(".TW", "")
                        if market == "tw" and isinstance(symbol, str)
                        else symbol
                    )
                    if isinstance(display_symbol, str) and display_symbol:
                        normalized_task["name"] = f"處理 {display_symbol} 相關查詢"
                if (
                    not isinstance(query_profile, dict)
                    or query_profile.get("query_type") != "price_lookup"
                ):
                    return [normalized_task]

        if (
            not isinstance(query_profile, dict)
            or query_profile.get("query_type") != "price_lookup"
        ):
            return tasks

        boundary_route = self._detect_boundary_route(query, history=history)
        if not boundary_route:
            return tasks

        route_entities = boundary_route.get("entities", {})
        if not isinstance(route_entities, dict):
            return tasks
        matched_markets = [market for market, value in route_entities.items() if value]
        if len(matched_markets) != 1:
            return tasks

        task_override = boundary_route.get("task", {})
        if not isinstance(task_override, dict):
            return tasks

        normalized_task = dict(tasks[0])
        override_agent = task_override.get("agent")
        if isinstance(override_agent, str) and override_agent:
            normalized_task["agent"] = override_agent
        normalized_task["description"] = query

        override_name = task_override.get("name")
        if isinstance(override_name, str) and override_name:
            normalized_task["name"] = override_name

        return [normalized_task]

    def _normalize_tasks(self, tasks: List[dict], query: str) -> List[dict]:
        """清理 LLM 產生的 task plan，避免 graph 因過長或壞資料失控。"""
        from ._main import MAX_GRAPH_TASKS

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

            normalized.append(
                {
                    "id": task_id,
                    "name": name,
                    "agent": agent,
                    "description": description,
                    "dependencies": [
                        dep for dep in dependencies if dep in retained_ids
                    ],
                }
            )
            retained_ids.add(task_id)

        if len(normalized) > MAX_GRAPH_TASKS:
            logger.warning(
                f"[Manager] Task plan too large ({len(normalized)} tasks), truncating to {MAX_GRAPH_TASKS}"
            )
            normalized = normalized[:MAX_GRAPH_TASKS]
            valid_ids = {task["id"] for task in normalized}
            for task in normalized:
                task["dependencies"] = [
                    dep for dep in task["dependencies"] if dep in valid_ids
                ]

        if not normalized and query:
            return [
                {
                    "id": "task_1",
                    "name": "處理請求",
                    "agent": "chat",
                    "description": query,
                    "dependencies": [],
                }
            ]

        return normalized

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
