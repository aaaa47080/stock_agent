"""Tool Registry for managing agent tools"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolInfo:
    """工具資訊"""
    name: str
    description: str
    category: str
    tool_object: Any
    parameters: Dict = None
    required_params: List[str] = None


class ToolRegistry:
    """工具註冊中心"""

    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}

    def register(self, name: str, description: str, category: str,
                 tool_object: Any, parameters: Dict = None,
                 required_params: List[str] = None) -> None:
        self._tools[name] = ToolInfo(
            name=name, description=description, category=category,
            tool_object=tool_object, parameters=parameters,
            required_params=required_params or []
        )

    def get(self, name: str) -> Optional[ToolInfo]:
        return self._tools.get(name)

    def get_tool_object(self, name: str) -> Optional[Any]:
        info = self._tools.get(name)
        return info.tool_object if info else None

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_by_category(self, category: str) -> List[ToolInfo]:
        return [info for info in self._tools.values() if info.category == category]

    def get_descriptions(self) -> Dict[str, str]:
        return {name: info.description for name, info in self._tools.items()}

    @classmethod
    def from_tool_dict(cls, tools: Dict[str, Dict[str, Any]],
                       tool_objects: Dict[str, Any] = None) -> "ToolRegistry":
        registry = cls()
        tool_objects = tool_objects or {}
        for name, info in tools.items():
            registry.register(
                name=name,
                description=info.get("description", ""),
                category=info.get("category", "general"),
                tool_object=tool_objects.get(name)
            )
        return registry
