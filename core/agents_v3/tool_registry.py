"""
Agent V3 工具註冊表

管理工作具的註冊、獲取和執行
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .tools import BaseTool, ToolResult, create_default_tools
from .models import ToolInfo


@dataclass
class ToolUsageRecord:
    """工具使用記錄"""
    tool_name: str
    agent_name: str
    parameters: Dict[str, Any]
    result: ToolResult
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time_ms: int = 0


class ToolRegistry:
    """
    工具註冊表

    職責：
    - 管理所有可用工具
    - 按領域分配工具給 Agent
    - 記錄工具使用歷史
    """

    def __init__(self):
        # 按領域分類的工具
        self._tools_by_domain: Dict[str, Dict[str, BaseTool]] = {}
        # 所有工具的映射
        self._all_tools: Dict[str, BaseTool] = {}
        # 使用記錄
        self._usage_log: List[ToolUsageRecord] = []
        # 最大記錄數
        self._max_log_size = 1000

    def register(self, tool: BaseTool) -> None:
        """
        註冊工具

        Args:
            tool: 要註冊的工具實例
        """
        # 添加到全局映射
        self._all_tools[tool.name] = tool

        # 添加到各個領域
        for domain in tool.domains:
            if domain not in self._tools_by_domain:
                self._tools_by_domain[domain] = {}
            self._tools_by_domain[domain][tool.name] = tool

    def unregister(self, tool_name: str) -> bool:
        """
        取消註冊工具

        Args:
            tool_name: 工具名稱

        Returns:
            是否成功取消註冊
        """
        if tool_name not in self._all_tools:
            return False

        tool = self._all_tools[tool_name]

        # 從各領域移除
        for domain in tool.domains:
            if domain in self._tools_by_domain:
                self._tools_by_domain[domain].pop(tool_name, None)

        # 從全局移除
        del self._all_tools[tool_name]
        return True

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        獲取指定工具

        Args:
            tool_name: 工具名稱

        Returns:
            工具實例或 None
        """
        return self._all_tools.get(tool_name)

    def get_tools_for_domain(self, domain: str) -> Dict[str, BaseTool]:
        """
        獲取指定領域的所有工具

        Args:
            domain: 領域名稱（如 'news', 'technical', 'general'）

        Returns:
            工具名稱到工具實例的映射
        """
        tools = {}

        # 先添加通用工具
        if "general" in self._tools_by_domain:
            tools.update(self._tools_by_domain["general"])

        # 再添加領域特定工具
        if domain in self._tools_by_domain:
            tools.update(self._tools_by_domain[domain])

        return tools

    def get_tool_schemas_for_domain(self, domain: str) -> List[dict]:
        """
        獲取指定領域所有工具的 schema

        Args:
            domain: 領域名稱

        Returns:
            工具 schema 列表（供 LLM 參考）
        """
        tools = self.get_tools_for_domain(domain)
        return [tool.get_schema() for tool in tools.values()]

    def execute(
        self,
        tool_name: str,
        agent_name: str = "unknown",
        **kwargs
    ) -> ToolResult:
        """
        執行工具

        Args:
            tool_name: 工具名稱
            agent_name: 調用工具的 agent 名稱
            **kwargs: 工具參數

        Returns:
            工具執行結果
        """
        import time

        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"工具 '{tool_name}' 不存在"
            )

        start_time = time.time()

        try:
            result = tool.execute(**kwargs)

            # 記錄使用
            execution_time = int((time.time() - start_time) * 1000)
            self._log_usage(
                tool_name=tool_name,
                agent_name=agent_name,
                parameters=kwargs,
                result=result,
                execution_time_ms=execution_time
            )

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"工具執行錯誤: {str(e)}"
            )

    def _log_usage(
        self,
        tool_name: str,
        agent_name: str,
        parameters: Dict[str, Any],
        result: ToolResult,
        execution_time_ms: int
    ):
        """記錄工具使用"""
        record = ToolUsageRecord(
            tool_name=tool_name,
            agent_name=agent_name,
            parameters=parameters,
            result=result,
            execution_time_ms=execution_time_ms
        )

        self._usage_log.append(record)

        # 限制日誌大小
        if len(self._usage_log) > self._max_log_size:
            self._usage_log = self._usage_log[-self._max_log_size:]

    def get_usage_stats(self, limit: int = 100) -> List[dict]:
        """
        獲取工具使用統計

        Args:
            limit: 返回記錄數量限制

        Returns:
            使用記錄列表
        """
        recent = self._usage_log[-limit:]
        return [
            {
                "tool": r.tool_name,
                "agent": r.agent_name,
                "success": r.result.success,
                "time_ms": r.execution_time_ms,
                "timestamp": r.timestamp.isoformat()
            }
            for r in recent
        ]

    def list_all_tools(self) -> List[ToolInfo]:
        """
        列出所有已註冊的工具

        Returns:
            工具資訊列表
        """
        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                domains=tool.domains
            )
            for tool in self._all_tools.values()
        ]

    def clear_usage_log(self) -> int:
        """
        清除使用日誌

        Returns:
            清除的記錄數
        """
        count = len(self._usage_log)
        self._usage_log.clear()
        return count


def create_default_registry(llm_client=None) -> ToolRegistry:
    """
    創建包含預設工具的註冊表

    Args:
        llm_client: LLM 客戶端（可選）

    Returns:
        配置好的 ToolRegistry 實例
    """
    registry = ToolRegistry()

    for tool in create_default_tools(llm_client):
        registry.register(tool)

    return registry
