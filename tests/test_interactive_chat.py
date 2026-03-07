"""
即時交互對話測試 - 模擬真實使用者行為

這個測試會根據 AI 的回答動態決定下一個問題
就像真正的使用者在對話一樣。

使用方式:
    python tests/test_interactive_chat.py
"""
import os
import sys
import asyncio
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from utils.settings import Settings  # noqa: E402

# 測試結果目錄
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results")


class InteractiveChatSession:
    """即時對話 session - 支援 HITL resume"""

    def __init__(self, manager, session_id: str):
        self.manager = manager
        self.session_id = session_id
        self.history = []
        self.conversation_log = []
        self.pending_hitl = None  # 存儲待處理的 HITL

    async def send(self, message: str, is_resume: bool = False) -> dict:
        """發送訊息並獲取回應

        Args:
            message: 使用者訊息
            is_resume: 是否是 HITL resume（確認計劃）
        """
        from langgraph.types import Command

        config = {"configurable": {"thread_id": self.session_id}}
        history_text = "\n".join(self.history[-10:]) if self.history else ""

        start_time = time.time()

        if is_resume and self.pending_hitl:
            # HITL resume: 使用 Command(resume=...) 繼續執行
            graph_input = Command(resume=message)
            self.pending_hitl = None  # 清除 pending HITL
        else:
            # 新請求
            graph_input = {
                "session_id": self.session_id,
                "query": message,
                "history": history_text,
                "language": "zh-TW",
            }

        result = await self.manager.graph.ainvoke(graph_input, config)
        duration = time.time() - start_time

        # 記錄到歷史
        self.history.append(f"使用者: {message}")

        # 檢查 HITL
        interrupt_events = result.get("__interrupt__", [])
        hitl_data = None
        if interrupt_events:
            hitl_data = interrupt_events[0].value
            self.pending_hitl = hitl_data  # 存儲待處理的 HITL

        # 記錄回應
        response = result.get("final_response", "無回應")
        if response and response != "無回應":
            self.history.append(f"助手: {response[:300]}...")

        # 記錄對話
        self.conversation_log.append({
            "user": message,
            "assistant": response,
            "mode": result.get("execution_mode", "unknown"),
            "hitl": hitl_data,
            "duration": duration,
            "is_resume": is_resume,
        })

        return {
            "response": response,
            "mode": result.get("execution_mode", "unknown"),
            "hitl": hitl_data,
            "duration": duration,
        }

    def print_log(self):
        """印出對話記錄"""
        print("\n" + "=" * 60)
        print("📋 對話記錄")
        print("=" * 60)
        for i, log in enumerate(self.conversation_log):
            print(f"\n[第 {i+1} 輪]{'(resume)' if log.get('is_resume') else ''}")
            print(f"👤 使用者: {log['user']}")
            print(f"🔧 模式: {log['mode']}")
            if log['hitl']:
                print(f"📋 HITL: {log['hitl'].get('type', 'unknown')}")
            print(f"🤖 助手: {log['assistant'][:200]}...")
        print("=" * 60)

    def save_results(self, scenario_name: str):
        """儲存測試結果到檔案"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scenario_name}_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "scenario": scenario_name,
                "session_id": self.session_id,
                "timestamp": timestamp,
                "conversation": self.conversation_log,
            }, f, ensure_ascii=False, indent=2)

        print(f"💾 結果已儲存: {filepath}")
        return filepath


async def simulate_crypto_investor(session: InteractiveChatSession):
    """模擬一個加密貨幣投資者的對話流程"""
    print("\n" + "═" * 60)
    print("📊 模擬加密貨幣投資者")
    print("═" * 60)

    # 第 1 輪：問價格
    print("\n[第 1 輪] 我想知道 BTC 的價格...")
    result = await session.send("BTC 現在多少錢？")
    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")
    print(f"   {result['response'][:400]}...")

    # 第 2 輪：問投資建議
    print("\n[第 2 輪] 價格收到了，問投資建議...")
    result = await session.send("這個價格值得投資嗎？幫我分析一下")
    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")

    # 檢查是否有 HITL 計劃確認
    if result['hitl'] and result['hitl'].get('type') == 'confirm_plan':
        plan = result['hitl'].get('plan', [])
        print(f"📋 系統提出計劃確認 ({len(plan)} 個任務):")
        for task in plan:
            print(f"   - {task.get('name', '未知')}")

        # 第 3 輪：確認執行（使用 resume）
        print("\n[第 3 輪] 同意計劃，執行...")
        result = await session.send("好，請執行這個計劃", is_resume=True)
        print(f"🤖 系統回應 ({result['mode']} 模式):")
        print(f"   {result['response'][:400]}...")
    else:
        print("   (沒有 HITL 計劃確認)")
        print(f"   {result['response'][:400]}...")

    session.save_results("crypto_investor")
    return session


async def simulate_us_stock_investor(session: InteractiveChatSession):
    """模擬一個美股投資者的對話流程"""
    print("\n" + "═" * 60)
    print("📈 模擬美股投資者")
    print("═" * 60)

    # 第 1 輪
    print("\n[第 1 輪] 我對 Apple 股票有興趣...")
    result = await session.send("AAPL 股價現在多少？")
    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")
    print(f"   {result['response'][:400]}...")

    # 根據回應決定下一步
    if "無法" in result['response'] or "抱歉" in result['response']:
        print("\n[第 2 輪] 好像無法取得數據，試試 TSLA...")
        result = await session.send("那 TSLA 特斯拉股價呢？")
    else:
        print("\n[第 2 輪] 收到價格了，問技術分析...")
        result = await session.send("可以幫我做技術分析嗎？")

    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")
    print(f"   {result['response'][:400]}...")

    # 第 3 輪：處理 HITL
    if result['hitl'] and result['hitl'].get('type') == 'confirm_plan':
        plan = result['hitl'].get('plan', [])
        print(f"\n📋 系統提出計劃確認 ({len(plan)} 個任務)")
        print("\n[第 3 輪] 同意計劃...")
        result = await session.send("執行計劃", is_resume=True)
    else:
        print("\n[第 3 輪] 繼續問...")
        result = await session.send("可以幫我看看財報嗎？")

    print(f"🤖 系統回應 ({result['mode']} 模式):")
    print(f"   {result['response'][:400]}...")

    session.save_results("us_stock_investor")
    return session


async def simulate_tw_stock_investor(session: InteractiveChatSession):
    """模擬一個台股投資者的對話流程"""
    print("\n" + "═" * 60)
    print("💹 模擬台股投資者")
    print("═" * 60)

    # 第 1 輪
    print("\n[第 1 輪] 我想了解台積電...")
    result = await session.send("台積電 (2330) 今天股價多少？")
    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")
    print(f"   {result['response'][:400]}...")

    # 第 2 輪
    print("\n[第 2 輪] 想了解外資動向...")
    result = await session.send("外資最近是買還是賣？這檔值得投資嗎？")
    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")

    # 處理 HITL
    if result['hitl'] and result['hitl'].get('type') == 'confirm_plan':
        plan = result['hitl'].get('plan', [])
        print(f"📋 系統提出計劃確認 ({len(plan)} 個任務)")

        # 第 3 輪：根據計劃內容決定
        print("\n[第 3 輪] 同意計劃...")
        result = await session.send("好，開始執行", is_resume=True)
    else:
        print(f"   {result['response'][:400]}...")
        print("\n[第 3 輪] 繼續問...")
        result = await session.send("那聯發科呢？")

    print(f"🤖 系統回應 ({result['mode']} 模式):")
    print(f"   {result['response'][:400]}...")

    session.save_results("tw_stock_investor")
    return session


async def simulate_investment_advisor(session: InteractiveChatSession):
    """模擬投資顧問對話（用戶原始問題）"""
    print("\n" + "═" * 60)
    print("💰 模擬投資顧問對話（用戶原始場景）")
    print("═" * 60)

    # 用戶原始問題
    print("\n[第 1 輪] 用戶提出投資需求...")
    result = await session.send(
        "我有 100 萬台幣的閒置資金想做投資，"
        "我目前的資產配置是 60% 股票、30% 加密貨幣、10% 現金"
    )
    print(f"🤖 系統回應 ({result['mode']} 模式, {result['duration']:.1f}s):")
    print(f"   {result['response'][:400]}...")

    # 檢查 HITL
    if result['hitl'] and result['hitl'].get('type') == 'confirm_plan':
        plan = result['hitl'].get('plan', [])
        print(f"\n📋 系統提出計劃確認 ({len(plan)} 個任務):")
        for task in plan:
            print(f"   - {task.get('name', '未知')} ({task.get('agent', '未知')})")

        # 第 2 輪：確認執行
        print("\n[第 2 輪] 同意計劃...")
        result = await session.send("好，請執行這個計劃", is_resume=True)
        print(f"🤖 系統回應 ({result['mode']} 模式):")
        print(f"   {result['response'][:500]}...")
    else:
        print("\n[第 2 輪] 沒有計劃確認，繼續對話...")
        result = await session.send("那你會建議我怎麼配置？")
        print(f"🤖 系統回應: {result['response'][:500]}...")

    session.save_results("investment_advisor")
    return session


async def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║     即時交互對話測試 - 模擬真實使用者行為               ║")
    print("╚" + "═" * 58 + "╝")

    # 確保結果目錄存在
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"\n📁 測試結果目錄: {RESULTS_DIR}")

    # 檢查環境
    print(f"\nENABLE_MANAGER_V2: {Settings.ENABLE_MANAGER_V2}")

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
    print(f"\n初始化 LLM ({provider})...")
    llm = create_user_llm_client(
        provider=provider,
        api_key=api_key,
        model="gpt-4o-mini",
    )

    print("初始化 ManagerAgent V2...")
    manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")

    # 執行測試
    print("\n" + "=" * 60)
    print("開始執行對話測試...")
    print("=" * 60)

    # 場景 1: 加密貨幣投資者
    session1 = InteractiveChatSession(manager, f"crypto_{int(time.time())}")
    await simulate_crypto_investor(session1)

    # 場景 2: 美股投資者
    session2 = InteractiveChatSession(manager, f"usstock_{int(time.time())}")
    await simulate_us_stock_investor(session2)

    # 場景 3: 台股投資者
    session3 = InteractiveChatSession(manager, f"twstock_{int(time.time())}")
    await simulate_tw_stock_investor(session3)

    # 場景 4: 投資顧問（用戶原始問題）
    session4 = InteractiveChatSession(manager, f"invest_{int(time.time())}")
    await simulate_investment_advisor(session4)

    # 總結
    print("\n" + "═" * 60)
    print("📊 測試總結")
    print("═" * 60)

    print("\n✅ 所有測試完成!")
    print(f"\n📁 測試結果已儲存至: {RESULTS_DIR}")
    print("\n請檢查:")
    print("  1. vending 模式 → 簡單查詢快速回答")
    print("  2. restaurant 模式 → 複雜請求需要計劃確認")
    print("  3. confirm_plan HITL → 計劃確認視窗")
    print("  4. resume 後 → 真正執行計劃並返回結果")


if __name__ == "__main__":
    asyncio.run(main())
