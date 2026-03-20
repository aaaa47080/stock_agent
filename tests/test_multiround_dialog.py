"""
即時多輪對話測試 - 模擬真實使用者行為

這個測試會即時顯示每次對話的回應，讓你可以根據回應內容決定下一個問題。

使用方式:
    python tests/test_multiround_dialog.py
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from utils.settings import Settings  # noqa: E402


class MultiRoundDialogTester:
    """多輪對話測試器"""

    def __init__(self, manager):
        self.manager = manager
        self.session_id = f"test_{int(time.time())}"
        self.history = []

    async def chat(self, user_input: str) -> dict:
        """執行一輪對話"""
        config = {"configurable": {"thread_id": self.session_id}}

        # 組合歷史
        history_text = "\n".join(self.history[-10:]) if self.history else ""

        start_time = time.time()
        result = await self.manager.graph.ainvoke(
            {
                "session_id": self.session_id,
                "query": user_input,
                "history": history_text,
                "language": "zh-TW",
            },
            config,
        )
        duration = time.time() - start_time

        # 更新歷史
        self.history.append(f"使用者: {user_input}")

        # 檢查 HITL
        interrupt_events = result.get("__interrupt__", [])
        hitl_data = None
        if interrupt_events:
            hitl_data = interrupt_events[0].value

        # 記錄回應到歷史
        response = result.get("final_response", "無回應")
        if response and response != "無回應":
            self.history.append(f"助手: {response[:300]}...")

        return {
            "response": response,
            "execution_mode": result.get("execution_mode", "unknown"),
            "duration": duration,
            "hitl": hitl_data,
        }

    def print_result(self, user_input: str, result: dict):
        """即時顯示結果"""
        print()
        print("─" * 60)
        print(f"👤 使用者: {user_input}")
        print(f"🔧 模式: {result['execution_mode']}")
        print(f"⏱️ 耗時: {result['duration']:.2f}s")

        if result["hitl"]:
            hitl = result["hitl"]
            print(f"📋 HITL 類型: {hitl.get('type', 'unknown')}")
            if hitl.get("plan"):
                print("📋 計劃任務:")
                for i, task in enumerate(hitl["plan"], 1):
                    print(
                        f"   {i}. {task.get('name', '未知')} ({task.get('agent', '未知')})"
                    )

        print()
        print("🤖 助手回應:")
        print("─" * 60)
        response = result["response"]
        print(response[:1500] if len(response) > 1500 else response)
        print("─" * 60)


async def run_crypto_dialog(tester: MultiRoundDialogTester):
    """加密貨幣多輪對話測試"""
    print()
    print("=" * 60)
    print("📊 加密貨幣 (BTC) 多輪對話測試")
    print("=" * 60)

    # 第 1 輪：問價格
    result1 = await tester.chat("BTC 目前價格多少？")
    tester.print_result("BTC 目前價格多少？", result1)

    # 第 2 輪：問投資建議
    result2 = await tester.chat("這個價格值得投資嗎？你有什麼建議？")
    tester.print_result("這個價格值得投資嗎？你有什麼建議？", result2)

    # 第 3 輪：根據回應調整
    if result2.get("hitl"):
        result3 = await tester.chat("好，我同意這個計劃，請執行")
    else:
        result3 = await tester.chat("可以幫我也分析一下 ETH 和 SOL 寢？")
    tester.print_result("根據前文調整...", result3)


async def run_usstock_dialog(tester: MultiRoundDialogTester):
    """美股多輪對話測試"""
    print()
    print("=" * 60)
    print("📊 美股 (AAPL) 多輪對話測試")
    print("=" * 60)

    # 重置 session
    tester.session_id = f"test_usstock_{int(time.time())}"
    tester.history = []

    # 第 1 輪
    result1 = await tester.chat("AAPL 股價現在多少？")
    tester.print_result("AAPL 股價現在多少？", result1)

    # 第 2 輪
    result2 = await tester.chat("現在是買入的好時機嗎？幫我分析一下")
    tester.print_result("現在是買入的好時機嗎？幫我分析一下", result2)

    # 第 3 輪
    if result2.get("hitl"):
        result3 = await tester.chat("不用做基本面分析，只需要技術分析和新聞")
    else:
        result3 = await tester.chat("可以幫我也看看 TSLA 嗎？")
    tester.print_result("根據前文調整...", result3)


async def run_twstock_dialog(tester: MultiRoundDialogTester):
    """台股多輪對話測試"""
    print()
    print("=" * 60)
    print("📊 台股 (台積電) 多輪對話測試")
    print("=" * 60)

    # 重置 session
    tester.session_id = f"test_twstock_{int(time.time())}"
    tester.history = []

    # 第 1 輪
    result1 = await tester.chat("台積電今天股價多少？")
    tester.print_result("台積電今天股價多少？", result1)

    # 第 2 輪
    result2 = await tester.chat("這檔股票值得長期持有嗎？幫我分析一下優缺點")
    tester.print_result("這檔股票值得長期持有嗎？幫我分析一下優缺點", result2)

    # 第 3 輪
    if result2.get("hitl"):
        result3 = await tester.chat("執行計劃")
    else:
        result3 = await tester.chat("可以幫我也看看聯發科嗎？")
    tester.print_result("根據前文調整...", result3)


async def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║     即時多輪對話測試 - 模擬真實使用者行為               ║")
    print("╚" + "═" * 58 + "╝")

    # 檢查環境
    print()
    print(f"ENABLE_MANAGER_V2: {Settings.ENABLE_MANAGER_V2}")

    if not Settings.ENABLE_MANAGER_V2:
        print("請先在 .env 中設置 ENABLE_MANAGER_V2=true")
        return

    # 初始化
    from core.agents.bootstrap_v2 import bootstrap_v2  # noqa: E402

    from utils.user_client_factory import create_user_llm_client  # noqa: E402

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("缺少 API Key")
        return

    provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"

    print(f"初始化 LLM ({provider})...")
    llm = create_user_llm_client(
        provider=provider,
        api_key=api_key,
        model="gpt-4o-mini",
    )

    print("初始化 ManagerAgent V2...")
    manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")

    # 建立測試器
    tester = MultiRoundDialogTester(manager)

    # 執行測試
    await run_crypto_dialog(tester)
    await run_usstock_dialog(tester)
    await run_twstock_dialog(tester)

    print()
    print("=" * 60)
    print("測試完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
