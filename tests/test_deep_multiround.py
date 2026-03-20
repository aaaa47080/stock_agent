"""
深度多輪對話測試 - 模擬真實使用者完整諮詢流程

每個場景至少 5 輪對話，真正測試：
1. 上下文記憶
2. HITL 計劃確認
3. 計劃修改/協商
4. 結果追問
5. 跨主題切換

使用方式:
    python tests/test_deep_multiround.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from utils.settings import Settings  # noqa: E402

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results"
)


class DeepChatSession:
    """深度對話 session"""

    def __init__(self, manager, session_id: str, scenario_name: str):
        self.manager = manager
        self.session_id = session_id
        self.scenario_name = scenario_name
        self.history = []
        self.conversation_log = []
        self.pending_hitl = None
        self.round_count = 0

    async def send(self, message: str, is_resume: bool = False) -> dict:
        """發送訊息

        Args:
            message: 使用者訊息
            is_resume: 是否是 HITL resume（確認計劃）

        重要：
        - 如果使用者在 HITL 視窗中輸入「確認」、「執行」、「好」等確認詞 → is_resume=True
        - 如果使用者輸入新需求（如「我只想看技術分析」）→ is_resume=False（這是新查詢）
        """
        from langgraph.types import Command

        config = {"configurable": {"thread_id": self.session_id}}
        history_text = "\n".join(self.history[-12:]) if self.history else ""

        self.round_count += 1
        start_time = time.time()

        # 判斷是否為確認詞（使用包含匹配，而非精确匹配）
        confirm_keywords = [
            "好",
            "確認",
            "執行",
            "同意",
            "可以",
            "ok",
            "OK",
            "Yes",
            "yes",
            "開始分析",
            "開始",
            "計劃",
        ]
        is_confirm_message = any(kw in message for kw in confirm_keywords)

        if is_resume and self.pending_hitl and is_confirm_message:
            # 使用者確認計劃 → resume graph 執行
            graph_input = Command(resume=message)
            self.pending_hitl = None
        else:
            # 新請求或修改需求 → 重新開始
            if self.pending_hitl:
                # 有 pending HITL 但使用者輸入新需求 → 取消舊計劃
                self.pending_hitl = None
            graph_input = {
                "session_id": self.session_id,
                "query": message,
                "history": history_text,
                "language": "zh-TW",
            }

        result = await self.manager.graph.ainvoke(graph_input, config)
        duration = time.time() - start_time

        self.history.append(f"使用者: {message}")

        interrupt_events = result.get("__interrupt__", [])
        hitl_data = None
        if interrupt_events:
            hitl_data = interrupt_events[0].value
            self.pending_hitl = hitl_data

        response = result.get("final_response", "無回應")
        if response and response != "無回應":
            self.history.append(f"助手: {response[:400]}...")

        log_entry = {
            "round": self.round_count,
            "user": message,
            "assistant": response,
            "mode": result.get("execution_mode", "unknown"),
            "hitl": hitl_data,
            "duration": round(duration, 2),
            "is_resume": is_resume and is_confirm_message,
        }
        self.conversation_log.append(log_entry)

        return log_entry

    def print_round(self, log: dict):
        """印出單輪對話"""
        print(f"\n{'─' * 60}")
        print(f"[第 {log['round']} 輪]{'(resume確認)' if log.get('is_resume') else ''}")
        print(f"👤 使用者: {log['user']}")
        print(f"🔧 模式: {log['mode']} | ⏱️ {log['duration']}s")

        if log["hitl"]:
            hitl = log["hitl"]
            print(f"📋 HITL: {hitl.get('type', 'unknown')}")
            if hitl.get("plan"):
                for task in hitl["plan"]:
                    print(f"   → {task.get('name', '?')} ({task.get('agent', '?')})")

        print("\n🤖 助手回應:")
        resp = log["assistant"]
        if resp is None:
            print("(等待 HITL 確認)")
        elif len(resp) > 600:
            print(resp[:600] + "...")
        else:
            print(resp)

    def save_results(self):
        """儲存結果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.scenario_name}_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "scenario": self.scenario_name,
                    "session_id": self.session_id,
                    "total_rounds": self.round_count,
                    "conversation": self.conversation_log,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"\n💾 已儲存: {filepath}")


async def scenario_crypto_deep_dive(session: DeepChatSession):
    """場景 1: 加密貨幣深度分析（6 輪對話）"""
    print("\n" + "═" * 60)
    print("📊 場景 1: 加密貨幣深度分析")
    print("═" * 60)

    # 第 1 輪：問價格
    result = await session.send("BTC 現在多少錢？")
    session.print_round(result)

    # 第 2 輪：問投資建議（複雜請求）
    result = await session.send("這個價格值得投資嗎？幫我分析一下技術面和市場情緒")
    session.print_round(result)

    # 第 3 輪：如果有 HITL，確認計劃
    if result["hitl"] and result["hitl"].get("type") == "confirm_plan":
        # 使用確認詞來執行計劃
        result = await session.send("好，執行計劃", is_resume=True)
        session.print_round(result)
    else:
        # 沒有 HITL，繼續對話
        result = await session.send("那 RSI 和 MACD 怎麼樣？")
        session.print_round(result)

    # 第 4 輪：根據結果追問
    if (
        "RSI" in result["assistant"]
        or "MACD" in result["assistant"]
        or "技術" in result["assistant"]
    ):
        result = await session.send("那現在是超買還是超賣？適合進場嗎？")
    else:
        result = await session.send("根據這些分析，你會建議我現在買入嗎？")
    session.print_round(result)

    # 第 5 輪：問其他幣種（上下文切換）
    result = await session.send("那 ETH 呢？跟 BTC 比起來哪個比較好？")
    session.print_round(result)

    # 第 6 輪：風險評估
    result = await session.send("如果我有 50 萬台幣，你會建議怎麼配置在這兩個幣之間？")
    session.print_round(result)

    session.save_results()
    return session


async def scenario_tw_stock_analysis(session: DeepChatSession):
    """場景 2: 台股投資分析（7 輪對話）"""
    print("\n" + "═" * 60)
    print("💹 場景 2: 台股投資分析")
    print("═" * 60)

    # 第 1 輪：問台積電
    result = await session.send("台積電 (2330) 今天股價多少？")
    session.print_round(result)

    # 第 2 輪：問外資動向
    result = await session.send("外資最近在買還是賣？三大法人動向如何？")
    session.print_round(result)

    # 第 3 輪：處理 HITL
    if result["hitl"] and result["hitl"].get("type") == "confirm_plan":
        result = await session.send("好，開始分析", is_resume=True)
        session.print_round(result)

    # 第 4 輪：問技術面
    result = await session.send("那技術分析呢？KD 值和均線怎麼樣？")
    session.print_round(result)

    # 第 5 輪：問基本面
    result = await session.send("這家公司基本面好嗎？本益比和 EPS 如何？")
    session.print_round(result)

    # 第 6 輪：問競爭對手
    result = await session.send("跟聯發科 (2454) 比起來，哪個比較值得投資？")
    session.print_round(result)

    # 第 7 輪：投資決策
    result = await session.send("如果我現在進場，你會建議買哪一檔？為什麼？")
    session.print_round(result)

    session.save_results()
    return session


async def scenario_investment_consultation(session: DeepChatSession):
    """場景 3: 完整投資諮詢（用戶原始場景，8 輪對話）"""
    print("\n" + "═" * 60)
    print("💰 場景 3: 完整投資諮詢（用戶原始場景）")
    print("═" * 60)

    # 第 1 輪：用戶原始問題
    result = await session.send(
        "我有 100 萬台幣的閒置資金想做投資，"
        "我目前的資產配置是 60% 股票、30% 加密貨幣、10% 現金"
    )
    session.print_round(result)

    # 第 2 輪：處理 HITL
    if result["hitl"] and result["hitl"].get("type") == "confirm_plan":
        plan = result["hitl"].get("plan", [])
        print(f"\n📋 計劃有 {len(plan)} 個任務")

        # 第 2 輪：確認執行計劃
        result = await session.send("好，請執行這個計劃", is_resume=True)
        session.print_round(result)

    # 第 3 輪：追問股票建議
    result = await session.send("那在股票部分，你會建議我配置在台股還是美股？為什麼？")
    session.print_round(result)

    # 第 4 輪：追問加密貨幣
    result = await session.send("加密貨幣部分，除了 BTC 和 ETH 還有什麼建議嗎？")
    session.print_round(result)

    # 第 5 輪：風險評估
    result = await session.send("現在市場風險大嗎？有什麼需要特別注意的？")
    session.print_round(result)

    # 第 6 輪：進場時機
    result = await session.send("你覺得現在是進場的好時機嗎？還是應該再等等？")
    session.print_round(result)

    # 第 7 輪：資產配置調整
    result = await session.send("根據你的分析，我應該怎麼調整我的 60/30/10 配置？")
    session.print_round(result)

    # 第 8 輪：總結建議
    result = await session.send("可以給我一個具體的行動建議嗎？下一步該做什麼？")
    session.print_round(result)

    session.save_results()
    return session


async def scenario_cross_market_comparison(session: DeepChatSession):
    """場景 4: 跨市場比較（6 輪對話）"""
    print("\n" + "═" * 60)
    print("🌐 場景 4: 跨市場比較分析")
    print("═" * 60)

    # 第 1 輪：台積電 ADR vs 台股
    result = await session.send("台積電 ADR 在美股的價格跟台股台積電的價格差多少？")
    session.print_round(result)

    # 第 2 輪：處理 HITL
    if result["hitl"]:
        result = await session.send("好，執行分析", is_resume=True)
        session.print_round(result)

    # 第 3 輪：問匯率影響
    result = await session.send("匯率會影響這兩者的價差嗎？現在美元對台幣多少？")
    session.print_round(result)

    # 第 4 輪：問投資選擇
    result = await session.send(
        "如果我想投資台積電，應該買 ADR 還是台股？哪個比較划算？"
    )
    session.print_round(result)

    # 第 5 輪：問風險差異
    result = await session.send("買 ADR 和買台股有什麼風險上的差異嗎？")
    session.print_round(result)

    # 第 6 輪：稅務考量
    result = await session.send("稅務方面呢？哪個比較有利？")
    session.print_round(result)

    session.save_results()
    return session


async def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║     深度多輪對話測試 - 完整投資諮詢流程                    ║")
    print("╚" + "═" * 58 + "╝")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"\n📁 測試結果目錄: {RESULTS_DIR}")

    print(f"\nENABLE_MANAGER_V2: {Settings.ENABLE_MANAGER_V2}")

    if not Settings.ENABLE_MANAGER_V2:
        print("請先在 .env 中設置 ENABLE_MANAGER_V2=true")
        return

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

    print("\n" + "=" * 60)
    print("開始執行深度多輪對話測試...")
    print("=" * 60)

    # 執行所有場景
    session1 = DeepChatSession(manager, f"crypto_{int(time.time())}", "crypto_deep")
    await scenario_crypto_deep_dive(session1)

    session2 = DeepChatSession(manager, f"twstock_{int(time.time())}", "tw_stock_deep")
    await scenario_tw_stock_analysis(session2)

    session3 = DeepChatSession(manager, f"invest_{int(time.time())}", "invest_consult")
    await scenario_investment_consultation(session3)

    session4 = DeepChatSession(manager, f"cross_{int(time.time())}", "cross_market")
    await scenario_cross_market_comparison(session4)

    # 總結
    print("\n" + "═" * 60)
    print("📊 測試總結")
    print("═" * 60)

    total_rounds = (
        session1.round_count
        + session2.round_count
        + session3.round_count
        + session4.round_count
    )
    print(f"\n✅ 總共執行 {total_rounds} 輪對話")
    print(f"   - 加密貨幣分析: {session1.round_count} 輪")
    print(f"   - 台股分析: {session2.round_count} 輪")
    print(f"   - 投資諮詢: {session3.round_count} 輪")
    print(f"   - 跨市場比較: {session4.round_count} 輪")

    print(f"\n📁 結果已儲存至: {RESULTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
