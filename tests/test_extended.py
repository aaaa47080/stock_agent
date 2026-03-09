"""
擴展測試 - 30 題全面測試
覆蓋：價格、新聞、技術分析、基本面、跨主題、壓力測試

使用方式:
    python tests/test_extended.py
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

from utils.settings import Settings

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results")

# 30 題測試問題
QUESTIONS = [
    # ========== Level 1: 簡單價格查詢 (5題) ==========
    {"q": "BTC 現在多少錢？", "cat": "價格"},
    {"q": "ETH 價格是多少？", "cat": "價格"},
    {"q": "DOGE 和 SHIB 的價格？", "cat": "價格"},
    {"q": "XRP 現在多少？", "cat": "價格"},
    {"q": "BNB 價格查詢", "cat": "價格"},

    # ========== Level 2: 基礎資訊 (5題) ==========
    {"q": "比特幣市值排名？", "cat": "資訊"},
    {"q": "加密貨幣總市值是多少？", "cat": "資訊"},
    {"q": "最近加密貨幣新聞", "cat": "新聞"},
    {"q": "比特幣恐慌貪婪指數", "cat": "情緒"},
    {"q": "今天漲幅最大的幣是什麼？", "cat": "資訊"},

    # ========== Level 3: 技術分析 (5題) ==========
    {"q": "BTC 的 RSI 和 MACD 是多少？", "cat": "技術"},
    {"q": "ETH 技術指標分析", "cat": "技術"},
    {"q": "SOL 支撐位和壓力位在哪裡？", "cat": "技術"},
    {"q": "BTC 7天均線趨勢", "cat": "技術"},
    {"q": "ARB 和 OP 的技術面比較", "cat": "技術"},

    # ========== Level 4: 深度分析 (5題) ==========
    {"q": "BTC 值得投資嗎？技術面和基本面分析", "cat": "分析"},
    {"q": "ETH 鏈上活動和 Gas 費用趨勢", "cat": "分析"},
    {"q": "SOL 和 ETH 哪個更有潛力？", "cat": "分析"},
    {"q": "Layer 2 賽道分析，推薦哪個？", "cat": "分析"},
    {"q": "DeFi 項目風險評估", "cat": "分析"},

    # ========== Level 5: 綜合分析 + 跨主題 (5題) ==========
    {"q": "給我一份完整的加密貨幣市場報告", "cat": "綜合"},
    {"q": "如果我有一萬美元，如何配置？", "cat": "配置"},
    {"q": "現在是進場時機嗎？", "cat": "時機"},
    {"q": "風險最大的幣是哪個？", "cat": "風險"},
    {"q": "未來一個月市場走勢預測", "cat": "預測"},
]


class ExtendedTestSession:
    def __init__(self, manager, session_id):
        self.manager = manager
        self.session_id = session_id
        self.history = []
        self.conversation_log = []
        self.pending_hitl = None
        self.round_count = 0
        self.errors = []

    async def send(self, message, is_resume=False):
        from langgraph.types import Command

        config = {"configurable": {"thread_id": self.session_id}}
        history_text = "\n".join(self.history[-12:]) if self.history else ""

        self.round_count += 1
        start_time = time.time()

        confirm_keywords = ["好", "確認", "執行", "同意", "可以", "ok", "OK", "Yes", "yes", "開始", "請執行"]
        is_confirm_message = any(kw in message for kw in confirm_keywords)

        if is_resume and self.pending_hitl and is_confirm_message:
            graph_input = Command(resume=message)
            self.pending_hitl = None
        else:
            if self.pending_hitl:
                self.pending_hitl = None
            graph_input = {
                "session_id": self.session_id,
                "query": message,
                "history": history_text,
                "language": "zh-TW",
            }

        try:
            result = await self.manager.graph.ainvoke(graph_input, config)
            duration = time.time() - start_time

            response = result.get("final_response", "無回應")
            if response and response != "無回應":
                self.history.append(f"助手: {response[:400]}...")

            interrupt_events = result.get("__interrupt__", [])
            hitl_data = None
            if interrupt_events:
                hitl_data = interrupt_events[0].value if interrupt_events else None
                self.pending_hitl = hitl_data

            log_entry = {
                "round": self.round_count,
                "user": message,
                "assistant": response,
                "mode": result.get("execution_mode", "unknown"),
                "hitl": hitl_data,
                "duration": round(duration, 2),
                "is_resume": is_resume,
                "error": None,
            }

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            self.errors.append({"round": self.round_count, "question": message, "error": error_msg})
            log_entry = {
                "round": self.round_count,
                "user": message,
                "assistant": f"❌ 錯誤: {error_msg}",
                "mode": "error",
                "hitl": None,
                "duration": round(duration, 2),
                "is_resume": is_resume,
                "error": error_msg,
            }

        self.conversation_log.append(log_entry)
        return log_entry

    def save_results(self):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(RESULTS_DIR, f"extended_test_{timestamp}.json")

        result = {
            "scenario": "extended_30_questions",
            "session_id": self.session_id,
            "total_rounds": self.round_count,
            "errors_count": len(self.errors),
            "errors": self.errors,
            "conversation": self.conversation_log,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return filepath


async def run_extended_test():
    if not Settings.ENABLE_MANAGER_V2:
        print("❌ 請先在 .env 中設置 ENABLE_MANAGER_V2=true")
        return

    from core.agents.bootstrap import bootstrap
    from utils.user_client_factory import create_user_llm_client

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 缺少 API Key")
        return

    provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"
    print(f"\n🔧 初始化 LLM ({provider})...")
    llm = create_user_llm_client(provider=provider, api_key=api_key, model="gpt-4o-mini")

    print("🔧 初始化 ManagerAgent...")
    manager = bootstrap(llm, web_mode=False, language="zh-TW")

    session = ExtendedTestSession(manager, f"extended_{int(time.time())}")

    print("\n" + "=" * 60)
    print("🎮 擴展測試開始 - 30 題")
    print("=" * 60)

    total = len(QUESTIONS)
    for i, test in enumerate(QUESTIONS, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}/{total}] {test['cat']}: {test['q']}")
        print(f"{'─' * 60}")

        result = await session.send(test['q'])

        if result.get('hitl'):
            print("📋 HITL確認...")
            await asyncio.sleep(0.3)
            result = await session.send("確認", is_resume=True)

        if result.get('error'):
            print(f"❌ 錯誤: {result['error'][:80]}")
        else:
            print(f"✅ 完成 ({result['duration']}s)")
            preview = result['assistant'][:100] if result['assistant'] else "無回應"
            print(f"📝 {preview}...")

        await asyncio.sleep(0.5)

    filepath = session.save_results()

    print("\n" + "=" * 60)
    print("📊 測試完成")
    print("=" * 60)
    print(f"總測試數: {session.round_count}")
    print(f"錯誤數: {len(session.errors)}")
    if session.errors:
        print("\n❌ 錯誤列表:")
        for err in session.errors:
            print(f"  - Q{err['round']}: {err['error'][:60]}")
    print(f"\n💾 結果: {filepath}")


if __name__ == "__main__":
    asyncio.run(run_extended_test())
