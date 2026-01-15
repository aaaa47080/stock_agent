"""
工具配置管理系統
提供工具註冊、管理和查詢功能
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any


@dataclass
class ToolConfig:
    """工具配置類"""
    id: str  # 工具唯一識別碼
    name: str  # 工具名稱（顯示用）
    description: str  # 工具描述
    tool_func: Callable  # 工具函數（LangChain @tool 裝飾的函數）
    enabled: bool = True  # 是否啟用
    support_medical: bool = True  # 是否支援醫療查詢
    support_general: bool = False  # 是否支援一般查詢
    timeout: int = 30  # 執行超時時間（秒）
    retry_on_failure: bool = False  # 失敗時是否重試
    metadata: Dict[str, Any] = field(default_factory=dict)  # 額外的元數據


# 全域工具註冊表
_TOOL_REGISTRY: Dict[str, ToolConfig] = {}


def register_tool(tool_config: ToolConfig) -> None:
    """
    註冊工具到全域註冊表

    Args:
        tool_config: 工具配置物件
    """
    if tool_config.id in _TOOL_REGISTRY:
        print(f"⚠️ 工具 '{tool_config.id}' 已存在，將覆蓋原有配置")

    _TOOL_REGISTRY[tool_config.id] = tool_config
    status = "✅ 啟用" if tool_config.enabled else "🔒 停用"
    #print(f"  📦 註冊工具: {tool_config.name} (ID: {tool_config.id}) [{status}]")


def get_tool(tool_id: str) -> Optional[ToolConfig]:
    """
    獲取指定 ID 的工具配置

    Args:
        tool_id: 工具 ID

    Returns:
        工具配置物件，如果不存在則返回 None
    """
    return _TOOL_REGISTRY.get(tool_id)


def get_all_tools(enabled_only: bool = False) -> Dict[str, ToolConfig]:
    """
    獲取所有工具

    Args:
        enabled_only: 是否只返回已啟用的工具

    Returns:
        工具字典 {tool_id: ToolConfig}
    """
    if enabled_only:
        return {
            tool_id: config
            for tool_id, config in _TOOL_REGISTRY.items()
            if config.enabled
        }
    return _TOOL_REGISTRY.copy()


def enable_tool(tool_id: str) -> bool:
    """
    啟用指定工具

    Args:
        tool_id: 工具 ID

    Returns:
        成功返回 True，失敗返回 False
    """
    tool = get_tool(tool_id)
    if not tool:
        print(f"❌ 工具 '{tool_id}' 不存在")
        return False

    tool.enabled = True
    print(f"✅ 工具 '{tool.name}' (ID: {tool_id}) 已啟用")
    return True


def disable_tool(tool_id: str) -> bool:
    """
    停用指定工具

    Args:
        tool_id: 工具 ID

    Returns:
        成功返回 True，失敗返回 False
    """
    tool = get_tool(tool_id)
    if not tool:
        print(f"❌ 工具 '{tool_id}' 不存在")
        return False

    tool.enabled = False
    print(f"🔒 工具 '{tool.name}' (ID: {tool_id}) 已停用")
    return True


def list_tools(enabled_only: bool = True) -> None:
    """
    列出所有工具及其狀態

    Args:
        enabled_only: 是否只顯示已啟用的工具
    """
    tools = get_all_tools(enabled_only=enabled_only)

    if not tools:
        print("📋 目前沒有已註冊的工具")
        return

    print("\n" + "=" * 80)
    print("📋 已註冊的工具")
    print("=" * 80)

    for tool_id, config in tools.items():
        status = "✅ 啟用" if config.enabled else "🔒 停用"
        print(f"\n{status} {config.name}")
        print(f"  ID: {tool_id}")
        print(f"  描述: {config.description}")
        print(f"  支援醫療: {'是' if config.support_medical else '否'}")
        print(f"  支援一般: {'是' if config.support_general else '否'}")
        print(f"  超時: {config.timeout}秒")
        if config.metadata:
            print(f"  元數據: {config.metadata}")

    print("=" * 80)


def get_tool_functions(enabled_only: bool = True) -> List[Callable]:
    """
    獲取工具函數列表（用於傳遞給 LangChain）

    Args:
        enabled_only: 是否只返回已啟用的工具

    Returns:
        工具函數列表
    """
    tools = get_all_tools(enabled_only=enabled_only)
    return [config.tool_func for config in tools.values()]


def clear_registry() -> None:
    """清空工具註冊表（主要用於測試）"""
    global _TOOL_REGISTRY
    _TOOL_REGISTRY.clear()
    print("🧹 工具註冊表已清空")


# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("🧪 測試工具配置管理系統\n")

    # 創建假的工具函數用於測試
    def dummy_tool_1(query: str) -> str:
        """假工具 1"""
        return f"處理查詢: {query}"

    def dummy_tool_2(query: str) -> str:
        """假工具 2"""
        return f"處理查詢: {query}"

    # 測試註冊工具
    print("測試 1: 註冊工具")
    print("-" * 80)
    tool1_config = ToolConfig(
        id="test_tool_1",
        name="測試工具 1",
        description="這是測試工具 1",
        tool_func=dummy_tool_1,
        enabled=True
    )
    register_tool(tool1_config)

    tool2_config = ToolConfig(
        id="test_tool_2",
        name="測試工具 2",
        description="這是測試工具 2",
        tool_func=dummy_tool_2,
        enabled=False
    )
    register_tool(tool2_config)

    # 測試列出工具
    print("\n測試 2: 列出所有工具")
    print("-" * 80)
    list_tools(enabled_only=False)

    # 測試啟用/停用工具
    print("\n測試 3: 停用工具 1")
    print("-" * 80)
    disable_tool("test_tool_1")

    print("\n測試 4: 啟用工具 2")
    print("-" * 80)
    enable_tool("test_tool_2")

    # 測試獲取已啟用的工具
    print("\n測試 5: 列出已啟用的工具")
    print("-" * 80)
    list_tools(enabled_only=True)

    print("\n✅ 測試完成")