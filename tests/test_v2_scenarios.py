"""
完整測試 ManagerAgent V2

測試場景：
1. 加密貨幣簡單查詢
2. 台股簡單查詢
3. 美股簡單查詢
4. 複雜查詢（多任務）
5. 有順序性的問題（垂直任務）
6. 並行問題（水平任務）

使用方式：
    # 在 .env 中設置
    ENABLE_MANAGER_V2=true

    # 運行測試
    python tests/test_v2_scenarios.py
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


def print_result(query: str, response: str, execution_mode: str = None, duration: float = None):
    print(f"\n📝 用戶: {query}")
    if execution_mode:
        print(f"🔧 執行模式: {execution_mode}")
    if duration:
        print(f"⏱️  耗時: {duration:.2f}s")
    print("\n🤖 回應:")
    print("-" * 70)
    print(response[:1000] + "..." if len(response) > 1000 else response)
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

    return {
        "response": result.get("final_response", "無回應"),
        "execution_mode": result.get("execution_mode", "unknown"),
        "duration": duration,
        "result": result,
    }


async def test_scenarios():
    """運行所有測試場景"""

    # 檢查環境
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
    # 測試 1: 加密貨幣簡單查詢
    # ========================================
    print_header("測試 1: 加密貨幣簡單查詢 (Vending Mode)")
    result = await run_query(manager, "test_crypto_1", "BTC 現在多少錢？")
    print_result(
        "BTC 現在多少錢？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 2: 台股簡單查詢
    # ========================================
    print_header("測試 2: 台股簡單查詢 (Vending Mode)")
    result = await run_query(manager, "test_tw_1", "台積電今天股價多少？")
    print_result(
        "台積電今天股價多少？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 3: 美股簡單查詢
    # ========================================
    print_header("測試 3: 美股簡單查詢 (Vending Mode)")
    result = await run_query(manager, "test_us_1", "Apple 股價多少？")
    print_result(
        "Apple 股價多少？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 4: 複雜查詢（多任務）
    # ========================================
    print_header("測試 4: 複雜查詢 - 多任務分析 (Restaurant Mode)")
    result = await run_query(
        manager,
        "test_complex_1",
        "幫我分析 BTC 的技術面和最新新聞，然後給我投資建議"
    )
    print_result(
        "幫我分析 BTC 的技術面和最新新聞，然後給我投資建議",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 5: 有順序性的問題（垂直任務）
    # ========================================
    print_header("測試 5: 順序性問題 - 垂直任務 (Restaurant Mode)")
    result = await run_query(
        manager,
        "test_vertical_1",
        "先查 ETH 價格，然後根據價格判斷現在是否適合買入"
    )
    print_result(
        "先查 ETH 價格，然後根據價格判斷現在是否適合買入",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 6: 並行問題（水平任務）
    # ========================================
    print_header("測試 6: 並行問題 - 水平任務 (Restaurant Mode)")
    result = await run_query(
        manager,
        "test_parallel_1",
        "同時幫我查 BTC、ETH、SOL 的價格，然後比較它們今天的漲跌幅"
    )
    print_result(
        "同時幫我查 BTC、ETH、SOL 的價格，然後比較它們今天的漲跌幅",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 7: 多市場混合查詢
    # ========================================
    print_header("測試 7: 多市場混合查詢 (Restaurant Mode)")
    result = await run_query(
        manager,
        "test_mixed_1",
        "幫我查台積電 ADR 在美股的價格，以及台股台積電的價格"
    )
    print_result(
        "幫我查台積電 ADR 在美股的價格，以及台股台積電的價格",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 8: 外匯查詢
    # ========================================
    print_header("測試 8: 外匯查詢 (Vending Mode)")
    result = await run_query(manager, "test_forex_1", "現在美元對台幣匯率多少？")
    print_result(
        "現在美元對台幣匯率多少？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 9: 經濟數據查詢
    # ========================================
    print_header("測試 9: 經濟數據查詢 (Vending Mode)")
    result = await run_query(manager, "test_economic_1", "現在 VIX 恐慌指數多少？")
    print_result(
        "現在 VIX 恐慌指數多少？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試 10: 閒聊
    # ========================================
    print_header("測試 10: 閒聊 (Vending Mode)")
    result = await run_query(manager, "test_chat_1", "你好，你會做什麼？")
    print_result(
        "你好，你會做什麼？",
        result["response"],
        result["execution_mode"],
        result["duration"]
    )

    # ========================================
    # 測試總結
    # ========================================
    print_header("測試完成")
    print("""
✅ 所有測試已完成！

切換版本：
  V2 (實驗版): ENABLE_MANAGER_V2=true
  V1 (穩定版): ENABLE_MANAGER_V2=false
""")


def main():
    asyncio.run(test_scenarios())


if __name__ == "__main__":
    main()
