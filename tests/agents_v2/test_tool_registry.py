"""Tests for Tool Registry"""
import pytest
from core.agents_v2.tool_registry import ToolRegistry, ToolInfo


class TestToolInfo:
    def test_tool_info_creation(self):
        info = ToolInfo(name="rsi", description="RSI", category="technical", tool_object=lambda: None)
        assert info.name == "rsi"
        assert info.category == "technical"


class TestToolRegistry:
    def test_registry_creation(self):
        registry = ToolRegistry()
        assert len(registry.list_tools()) == 0

    def test_register_tool(self):
        registry = ToolRegistry()
        registry.register("rsi", "RSI", "technical", lambda x: {"rsi": 65})
        assert "rsi" in registry.list_tools()

    def test_get_tool(self):
        registry = ToolRegistry()
        registry.register("rsi", "RSI", "technical", lambda x: {"rsi": 65})
        tool = registry.get("rsi")
        assert tool.name == "rsi"

    def test_get_by_category(self):
        registry = ToolRegistry()
        registry.register("rsi", "RSI", "technical", lambda: None)
        registry.register("news", "News", "sentiment", lambda: None)
        tech_tools = registry.get_by_category("technical")
        assert len(tech_tools) == 1

    def test_from_tool_dict(self):
        existing = {
            "technical_analysis_tool": {"description": "技術分析", "category": "technical"},
            "news_analysis_tool": {"description": "新聞分析", "category": "news"}
        }
        registry = ToolRegistry.from_tool_dict(existing)
        assert len(registry.list_tools()) == 2
        assert registry.get("technical_analysis_tool") is not None
