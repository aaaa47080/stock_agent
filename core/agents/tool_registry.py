from dataclasses import dataclass, field
from typing import List, Callable, Optional, Dict, Any


@dataclass
class ToolMetadata:
    name: str
    description: str
    input_schema: dict
    handler: Callable
    allowed_agents: List[str] = field(default_factory=list)  # [] = all allowed
    domains: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._usage_log: list = []

    def register(self, metadata: ToolMetadata) -> None:
        self._tools[metadata.name] = metadata

    def get(self, name: str, caller_agent: str = "") -> Optional[ToolMetadata]:
        tool = self._tools.get(name)
        if tool is None:
            return None
        # [] means unrestricted
        if tool.allowed_agents and caller_agent not in tool.allowed_agents:
            return None
        return tool

    def list_for_agent(self, agent_name: str) -> List[ToolMetadata]:
        return [t for t in self._tools.values()
                if not t.allowed_agents or agent_name in t.allowed_agents]

    def list_all_tools(self) -> List[ToolMetadata]:
        """For planning prompts only — no permission check."""
        return list(self._tools.values())

    def execute(self, tool_name: str, caller_agent: str = "", **kwargs) -> ToolResult:
        import time
        tool = self.get(tool_name, caller_agent)
        if tool is None:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found or not permitted for '{caller_agent}'")
        start = time.time()
        try:
            # Check if handler is a LangChain tool (has .invoke) or a callable
            if hasattr(tool.handler, "invoke"):
                data = tool.handler.invoke(kwargs)
            else:
                data = tool.handler(**kwargs)
            
            # Record usage (optional)
            self._usage_log.append({
                "tool": tool_name,
                "agent": caller_agent,
                "time": time.time() - start,
                "success": True
            })
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
