"""
Agent V4 — Router

Routes tasks to the correct agent, handles collaboration requests.
"""
from typing import Optional
from .agent_registry import AgentRegistry
from .models import CollaborationRequest


class AgentRouter:
    def __init__(self, registry: AgentRegistry):
        self._registry = registry

    def route(self, agent_hint: str):
        agent = self._registry.get(agent_hint)
        if agent is not None:
            return agent
        print(f"[Router] '{agent_hint}' not found, fallback to 'chat'")
        return self._registry.get("chat")

    def route_collaboration(self, request: CollaborationRequest):
        agent = self._registry.get(request.needed_agent)
        if agent is not None:
            return agent
        matches = self._registry.find_by_capability(request.needed_agent)
        if matches:
            best = max(matches, key=lambda m: m.priority)
            return self._registry.get(best.name)
        return None
