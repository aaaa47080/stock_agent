"""
測試 ManagerAgent V2 - Human-in-the-Loop 機制

更新後的 HITL 設計：
- 移除了 CLARIFY, NEGOTIATE, DISCUSS 類型
- 只保留 CONFIRM_PLAN（計劃確認）
- 澄清直接在回應中處理，不使用 interrupt

測試場景：
1. 簡單查詢 - Vending 模式快速回應
2. 複雜請求 - Restaurant 模式，需要確認計劃
3. 多輪對話 - 上下文保持
4. 邊界案例 - 無法處理的請求
5. 計劃確認 - 使用者確認/取消/修改計劃
"""
import os
import sys
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from utils.settings import Settings  # noqa: E402


def print_header(title: str):
    print()
    print("═" * 70)
    print(f"  {title}")
    print("═" * 70)


def print_result(query: str, response: str, execution_mode: str = None, duration: float = None, hitl: bool = False):
    print(f"\n📝 用戶: {query}")
    if execution_mode:
        print(f"🔧 執行模式: {execution_mode}")
    if hitl:
        print("🔄 HITL: 需要用戶回應")
    if duration:
        print(f"⏱️  耗時: {duration:.2f}s")
    print("\n🤖 回應:")
    print("-" * 70)
    print(response[:1500] + "..." if len(response) > 1500 else response)
    print("-" * 70)


async def run_query(manager, session_id: str, query: str, history: str = "") -> dict:
    """執行單個查詢"""
    config = {"configurable": {"thread_id": session_id}}

    start_time = time.time()
    result = await manager.graph.ainvoke(
        {
            "session_id": session_id,
            "query": query,
            "history": history,
            "language": "zh-TW",
        },
        config
    )
    duration = time.time() - start_time

    # 檢查是否有 HITL interrupt
    interrupt_events = result.get("__interrupt__", [])
    hitl_data = None
    if interrupt_events:
        hitl_data = interrupt_events[0].value

    return {
        "response": result.get("final_response", "無回應"),
        "execution_mode": result.get("execution_mode", "unknown"),
        "duration": duration,
        "hitl": hitl_data,
        "result": result,
    }


async def test_hitl_scenarios():
    """測試 HITL 場景"""

    print_header("Feature Flag 狀態")
    print(f"  ENABLE_MANAGER_V2: {Settings.ENABLE_MANAGER_V2}")

    if not Settings.ENABLE_MANAGER_V2:
        print("\n⚠️  請先在 .env 中設置 ENABLE_MANAGER_V2=true")
        return

    print("  ✅ V2 已啟用")

    # 初始化
    from core.agents.bootstrap_v2 import bootstrap_v2  # noqa: E402
    from utils.user_client_factory import create_user_llm_client  # noqa: E402

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 缺少 API Key")
        return

    provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"

    print(f"\n🔧 初始化 LLM ({provider})...")
    llm = create_user_llm_client(
        provider=provider,
        api_key=api_key,
        model="gpt-4o-mini",
    )

    print("🔧 初始化 ManagerAgent V2...")
    manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")
    print("  ✅ 初始化完成")

    # ========================================
    # 測試 1: 簡單查詢 - Vending 模式快速回應
    # ========================================
    print_header("測試 1: 簡單查詢 - Vending 模式")

    result = await run_query(manager, "test_hitl_1", "2330 現在多少？")
    print_result(
        "2330 現在多少？（未指明市場）",
        result["response"],
        result["execution_mode"],
        result["duration"],
        hitl=result["hitl"] is not None
    )
    if result["hitl"]:
        print(f"\n❓ HITL 問題: {result['hitl']}")

    # ========================================
    # 測試 2: 過於複雜的請求
    # ========================================
    print_header("測試 2: 複雜請求 - 多市場多任務")

    result = await run_query(
        manager,
        "test_hitl_2",
        "幫我分析 BTC、ETH、台積電、Apple 的技術面、基本面、最新新聞，然後給我投資組合建議"
    )
    print_result(
        "幫我分析 BTC、ETH、台積電、Apple 的技術面、基本面、最新新聞，然後給我投資組合建議",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 3: 資訊不足
    # ========================================
    print_header("測試 3: 資訊不足 - 需要澄清")

    result = await run_query(manager, "test_hitl_3", "幫我查價格")
    print_result(
        "幫我查價格（未指明標的）",
        result["response"],
        result["execution_mode"],
        result["duration"],
        hitl=result["hitl"] is not None
    )
    if result["hitl"]:
        print(f"\n❓ HITL 問題: {result['hitl']}")

    # ========================================
    # 測試 4: 多輪對話 - 上下文保持
    # ========================================
    print_header("測試 4: 多輪對話 - 上下文測試")

    # 第一輪
    history = ""
    result1 = await run_query(manager, "test_hitl_4", "BTC 現在多少？", history)
    print_result("第一輪: BTC 現在多少？", result1["response"], result1["execution_mode"], result1["duration"])

    # 模擬上下文
    history = f"用戶: BTC 現在多少？\n助手: {result1['response'][:200]}..."

    # 第二輪 - 應該要記得 BTC
    result2 = await run_query(manager, "test_hitl_4", "那 ETH 呢？", history)
    print_result("第二輪: 那 ETH 呢？（應該理解是問價格）", result2["response"], result2["execution_mode"], result2["duration"])

    # 第三輪 - 更進一步的問題
    history += f"\n用戶: 那 ETH 呢？\n助手: {result2['response'][:200]}..."
    result3 = await run_query(manager, "test_hitl_4", "哪一個比較值得投資？", history)
    print_result("第三輪: 哪一個比較值得投資？（應該記得 BTC 和 ETH）", result3["response"], result3["execution_mode"], result3["duration"])

    # ========================================
    # 測試 5: 超出能力範圍
    # ========================================
    print_header("測試 5: 超出能力範圍")

    result = await run_query(manager, "test_hitl_5", "幫我預測明天的樂透號碼")
    print_result(
        "幫我預測明天的樂透號碼",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 6: 混合語言
    # ========================================
    print_header("測試 6: 混合語言")

    result = await run_query(manager, "test_hitl_6", "What is the current price of Bitcoin? 我也想知道技術分析")
    print_result(
        "What is the current price of Bitcoin? 我也想知道技術分析",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 7: 錯誤的標的符號
    # ========================================
    print_header("測試 7: 錯誤/不存在的標的")

    result = await run_query(manager, "test_hitl_7", "XYZ123ABC 這個幣現在多少？")
    print_result(
        "XYZ123ABC 這個幣現在多少？（不存在的標的）",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 8: 需要專業判斷的問題
    # ========================================
    print_header("測試 8: 需要專業判斷 - 投資建議免責聲明")

    result = await run_query(
        manager,
        "test_hitl_8",
        "我有 100 萬台幣，應該全部買 BTC 嗎？"
    )
    print_result(
        "我有 100 萬台幣，應該全部買 BTC 嗎？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試總結
    # ========================================
    print_header("測試完成")
    print("""
✅ HITL 測試已完成！

更新後的 HITL 設計：
- 移除了 CLARIFY, NEGOTIATE, DISCUSS 類型
- 只保留 CONFIRM_PLAN（計劃確認）
- 澄清直接在回應中處理，不使用 interrupt

測試場景：
1. 簡單查詢 - Vending 模式快速回應
2. 複雜請求 - Restaurant 模式，需要確認計劃
3. 資訊不足 - 直接在回應中詢問
4. 多輪對話 - 上下文理解和保持
5. 超出能力 - 如何處理無法完成的請求
6. 混合語言 - 多語言處理能力
7. 錯誤標的 - 如何處理不存在的標的
8. 專業判斷 - 投資建議的免責處理
""")


def main():
    asyncio.run(test_hitl_scenarios())


if __name__ == "__main__":
    main()
