"""
Agent V4 — Agent Registry

Manages agent registration and capability-based discovery.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class AgentMetadata:
    name: str
    display_name: str
    description: str
    capabilities: List[str]
    allowed_tools: List[str]
    priority: int = 0


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, object] = {}
        self._metadata: Dict[str, AgentMetadata] = {}

    def register(self, agent, metadata: AgentMetadata) -> None:
        self._agents[metadata.name] = agent
        self._metadata[metadata.name] = metadata

    def get(self, name: str):
        return self._agents.get(name)

    def find_by_capability(self, capability: str) -> List[AgentMetadata]:
        return [m for m in self._metadata.values()
                if any(capability.lower() in cap.lower() for cap in m.capabilities)]

    def list_all(self) -> List[AgentMetadata]:
        return sorted(self._metadata.values(), key=lambda m: -m.priority)

    def agents_info_for_prompt(self) -> str:
        lines = []
        for m in self.list_all():
            caps = ", ".join(m.capabilities)
            lines.append(f"- {m.name}: {m.description} (capabilities: {caps})")
        return "\n".join(lines)
