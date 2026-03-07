"""
測試 ManagerAgent V2

使用方式：
    # 啟用 V2（在 .env 中設置）
    ENABLE_MANAGER_V2=true

    # 運行測試
    python tests/test_manager_v2.py
"""
import os
import sys
import asyncio

# 添加項目根目錄到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from utils.settings import Settings  # noqa: E402


def check_feature_flag():
    """檢查 Feature Flag 狀態"""
    print("=" * 60)
    print("Feature Flag 狀態")
    print("=" * 60)
    print(f"  ENABLE_MANAGER_V2: {Settings.ENABLE_MANAGER_V2}")
    print(f"  MANAGER_V2_OPEN_INTENT: {Settings.MANAGER_V2_OPEN_INTENT}")
    print(f"  MANAGER_V2_DAG_EXECUTION: {Settings.MANAGER_V2_DAG_EXECUTION}")
    print(f"  MANAGER_V2_PARALLEL_GROUPS: {Settings.MANAGER_V2_PARALLEL_GROUPS}")
    print(f"  MANAGER_V2_SHORT_MEMORY: {Settings.MANAGER_V2_SHORT_MEMORY}")
    print(f"  MANAGER_V2_SUBAGENT_CONTEXT: {Settings.MANAGER_V2_SUBAGENT_CONTEXT}")
    print()

    if not Settings.ENABLE_MANAGER_V2:
        print("⚠️  ENABLE_MANAGER_V2=false，將使用 V1（穩定版）")
        print("   要啟用 V2，請在 .env 中設置：")
        print("   ENABLE_MANAGER_V2=true")
        print()
    else:
        print("✅ ENABLE_MANAGER_V2=true，將使用 V2（實驗版）")
        print()


async def test_v2_simple_query():
    """測試 V2 簡單查詢"""
    print("=" * 60)
    print("測試：簡單查詢 (Vending Mode)")
    print("=" * 60)

    if not Settings.ENABLE_MANAGER_V2:
        print("⚠️  V2 未啟用，跳過測試")
        return

    from core.agents.bootstrap_v2 import bootstrap_v2  # noqa: E402
    from utils.user_client_factory import create_user_llm_client  # noqa: E402

    # 創建 LLM 客戶端
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 缺少 OPENAI_API_KEY")
        return

    llm = create_user_llm_client(
        provider="openai",
        api_key=api_key,
        model="gpt-4o-mini",
    )

    manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")

    # 測試查詢
    query = "BTC 現在多少錢？"
    print(f"用戶: {query}")
    print()

    config = {"configurable": {"thread_id": "test_simple"}}

    result = await manager.graph.ainvoke(
        {
            "session_id": "test_simple",
            "query": query,
            "history": "",
            "language": "zh-TW",
        },
        config
    )

    print(f"回應: {result.get('final_response', '無回應')}")
    print()


async def test_v2_complex_query():
    """測試 V2 複雜查詢"""
    print("=" * 60)
    print("測試：複雜查詢 (Restaurant Mode)")
    print("=" * 60)

    if not Settings.ENABLE_MANAGER_V2:
        print("⚠️  V2 未啟用，跳過測試")
        return

    from core.agents.bootstrap_v2 import bootstrap_v2  # noqa: E402
    from utils.user_client_factory import create_user_llm_client  # noqa: E402

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 缺少 OPENAI_API_KEY")
        return

    llm = create_user_llm_client(
        provider="openai",
        api_key=api_key,
        model="gpt-4o-mini",
    )

    manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")

    # 測試查詢
    query = "幫我分析 BTC 的技術面和最新新聞"
    print(f"用戶: {query}")
    print()

    config = {"configurable": {"thread_id": "test_complex"}}

    result = await manager.graph.ainvoke(
        {
            "session_id": "test_complex",
            "query": query,
            "history": "",
            "language": "zh-TW",
        },
        config
    )

    print(f"回應: {result.get('final_response', '無回應')}")
    print()


def main():
    """主測試入口"""
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║          ManagerAgent V2 測試工具                          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    # 檢查 Feature Flag
    check_feature_flag()

    # 運行測試
    print("運行測試...")
    print()

    asyncio.run(test_v2_simple_query())
    asyncio.run(test_v2_complex_query())

    print("=" * 60)
    print("測試完成")
    print("=" * 60)
    print()
    print("要切換 V1/V2，請修改 .env 文件：")
    print("  ENABLE_MANAGER_V2=true   # 使用 V2（實驗版）")
    print("  ENABLE_MANAGER_V2=false  # 使用 V1（穩定版）")
    print()


if __name__ == "__main__":
    main()
