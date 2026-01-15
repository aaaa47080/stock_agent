"""
工具初始化模組
負責初始化並註冊所有可用的工具
"""
from typing import List, Dict
from pathlib import Path
import sys

# 確保可以導入同目錄下的模組
sys.path.append(str(Path(__file__).parent))

from tools_config import (
    ToolConfig,
    get_all_tools,
    get_tool_functions,
    list_tools
)


def initialize_all_tools() -> Dict[str, ToolConfig]:
    """
    初始化並註冊所有可用的工具

    Returns:
        工具註冊表 {tool_id: ToolConfig}
    """
    print("🔧 初始化工具系統...")
    print("-" * 60)

    # ===== 註冊 CDC 即時搜尋工具 =====
    try:
        from tools.cdc_search_tool import register_cdc_tool
        register_cdc_tool()
    except Exception as e:
        print(f"⚠️ CDC 即時搜尋工具註冊失敗: {e}")

    # ===== 註冊 Google 即時搜尋工具 =====
    try:
        from tools.google_search_tool import register_google_tool
        register_google_tool()
    except Exception as e:
        print(f"⚠️ Google 即時搜尋工具註冊失敗: {e}")

    # ===== 註冊 DuckDuckGO 即時搜尋工具 =====
    try:
        from tools.duckduckgo import register_duckduckgo_tool
        register_duckduckgo_tool()
    except Exception as e:
        print(f"⚠️ DuckDuckGo 即時搜尋工具註冊失敗: {e}")



    # ===== 未來可以在這裡添加更多工具 =====
    # try:
    #     from some_other_tool import register_other_tool
    #     register_other_tool()
    # except Exception as e:
    #     print(f"⚠️ 其他工具註冊失敗: {e}")

    print("-" * 60)

    # 根據 config.py 中的 TOOLS_CONFIG 調整工具啟用狀態
    try:
        from core.config import TOOLS_CONFIG
        _apply_config_settings(TOOLS_CONFIG)
    except ImportError:
        print("⚠️ 無法導入 TOOLS_CONFIG，使用預設配置")

    # 返回所有已註冊的工具
    return get_all_tools()


def _apply_config_settings(config: dict) -> None:
    """
    根據配置調整工具啟用狀態

    Args:
        config: TOOLS_CONFIG 配置字典
    """
    if not config.get('enabled', True):
        # 如果工具系統被停用，停用所有工具
        print("⏭️ 工具系統已停用（TOOLS_CONFIG['enabled'] = False）")
        from tools_config import disable_tool, get_all_tools
        for tool_id in get_all_tools().keys():
            disable_tool(tool_id)
        return

    # 獲取預設啟用的工具列表
    default_tools = config.get('default_tools', [])

    if not default_tools:
        print("⚠️ 未指定預設工具（TOOLS_CONFIG['default_tools'] 為空）")
        return

    # 只啟用配置中指定的工具
    from tools_config import enable_tool, disable_tool, get_all_tools

    all_tool_ids = set(get_all_tools().keys())
    default_tool_ids = set(default_tools)

    # 啟用指定的工具
    for tool_id in default_tool_ids:
        if tool_id in all_tool_ids:
            enable_tool(tool_id)
        else:
            print(f"⚠️ 配置中的工具 '{tool_id}' 不存在，已忽略")

    # 停用未指定的工具
    tools_to_disable = all_tool_ids - default_tool_ids
    for tool_id in tools_to_disable:
        disable_tool(tool_id)


def get_active_tools() -> List:
    """
    獲取所有已啟用的工具函數（用於傳遞給 LangChain）

    Returns:
        已啟用的工具函數列表
    """
    return get_tool_functions(enabled_only=True)


def get_all_tool_configs(enabled_only: bool = False) -> Dict[str, ToolConfig]:
    """
    獲取所有工具配置

    Args:
        enabled_only: 是否只返回已啟用的工具

    Returns:
        工具配置字典
    """
    return get_all_tools(enabled_only=enabled_only)


# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("🧪 測試工具初始化系統\n")

    # 測試 1: 初始化所有工具
    print("測試 1: 初始化所有工具")
    print("=" * 80)
    registry = initialize_all_tools()
    print(f"\n✅ 成功註冊 {len(registry)} 個工具\n")

    # 測試 2: 列出所有工具
    print("測試 2: 列出所有工具（包含已停用的）")
    print("=" * 80)
    list_tools(enabled_only=False)

    # 測試 3: 獲取已啟用的工具
    print("\n測試 3: 獲取已啟用的工具函數")
    print("=" * 80)
    active_tools = get_active_tools()
    print(f"✅ 找到 {len(active_tools)} 個已啟用的工具")

    if active_tools:
        print("\n已啟用的工具列表:")
        for i, tool in enumerate(active_tools, 1):
            print(f"  {i}. {tool.name} - {tool.description[:50]}...")
    else:
        print("\n⚠️ 目前沒有已啟用的工具")

    print("\n" + "=" * 80)
    print("✅ 測試完成")