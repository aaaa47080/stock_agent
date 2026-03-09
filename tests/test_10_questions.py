"""
自動化 10 問測試 - 從簡單到複雜
測試範圍：價格查詢 → 深度分析 → 跨主題對話
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

# 10 個測試問題：從簡單到複雜
TEST_QUESTIONS = [
    # Level 1: 簡單價格查詢 (2題)
    {
        "level": 1,
        "category": "價格查詢",
        "question": "BTC 現在多少錢？",
        "expected": "返回 BTC 價格",
    },
    {
        "level": 1,
        "category": "價格查詢",
        "question": "ETH 和 SOL 的價格是多少？",
        "expected": "返回 ETH 和 SOL 價格",
    },

    # Level 2: 基礎資訊 (2題)
    {
        "level": 2,
        "category": "基礎資訊",
        "question": "比特幣的市值排名是多少？",
        "expected": "返回市值排名資訊",
    },
    {
        "level": 2,
        "category": "基礎資訊",
        "question": "最近有什麼加密貨幣新聞？",
        "expected": "返回加密貨幣相關新聞",
    },

    # Level 3: 多幣種比較 (2題)
    {
        "level": 3,
        "category": "多幣種比較",
        "question": "比較 BTC、ETH、SOL 最近 7 天的漲跌幅",
        "expected": "返回比較分析",
    },
    {
        "level": 3,
        "category": "多幣種比較",
        "question": "哪個 Layer 2 代幣最近表現最好？分析 ARB 和 OP",
        "expected": "返回 Layer 2 比較分析",
    },

    # Level 4: 深度分析 (2題)
    {
        "level": 4,
        "category": "深度分析",
        "question": "分析 BTC 的技術面和基本面，給我投資建議",
        "expected": "返回技術面+基本面分析",
    },
    {
        "level": 4,
        "category": "深度分析",
        "question": "以太坊最近的鏈上活動如何？Gas 費用趨勢是什麼？",
        "expected": "返回鏈上數據分析",
    },

    # Level 5: 綜合分析 + 跨主題 (2題)
    {
        "level": 5,
        "category": "綜合分析",
        "question": "給我一份完整的加密貨幣市場報告，包括大盤走勢、熱門板塊、風險提示",
        "expected": "返回完整市場報告",
    },
    {
        "level": 5,
        "category": "跨主題追問",
        "question": "基於剛才的分析，如果我現在有 10000 美元，你會建議如何配置？請考慮風險分散",
        "expected": "返回資產配置建議（需記住前文）",
    },
]


class AutoTestSession:
    """自動化測試 Session"""

    def __init__(self, manager, session_id: str):
        self.manager = manager
        self.session_id = session_id
        self.history = []
        self.conversation_log = []
        self.pending_hitl = None
        self.round_count = 0
        self.errors = []

    async def send(self, message: str, is_resume: bool = False) -> dict:
        """發送訊息"""
        from langgraph.types import Command

        config = {"configurable": {"thread_id": self.session_id}}
        history_text = "\n".join(self.history[-12:]) if self.history else ""

        self.round_count += 1
        start_time = time.time()

        # 判斷是否為確認詞
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

            # 檢查 HITL
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
            self.errors.append({
                "round": self.round_count,
                "question": message,
                "error": error_msg,
            })
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

    def save_results(self, filename_suffix=""):
        """儲存測試結果"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auto_test_10q_{timestamp}{filename_suffix}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        result = {
            "scenario": "auto_10_questions_test",
            "session_id": self.session_id,
            "total_rounds": self.round_count,
            "errors_count": len(self.errors),
            "errors": self.errors,
            "conversation": self.conversation_log,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return filepath


async def run_auto_test():
    """執行自動化測試"""

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
    llm = create_user_llm_client(
        provider=provider,
        api_key=api_key,
        model="gpt-4o-mini",
    )

    print("🔧 初始化 ManagerAgent...")
    manager = bootstrap(llm, web_mode=False, language="zh-TW")

    # 建立新的 session
    session = AutoTestSession(manager, f"auto_test_{int(time.time())}")

    print("\n" + "=" * 60)
    print("🎮 自動化 10 問測試開始")
    print("=" * 60)

    for i, test_case in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'─' * 60}")
        print(f"[Q{i}] Level {test_case['level']} - {test_case['category']}")
        print(f"問題: {test_case['question']}")
        print(f"預期: {test_case['expected']}")
        print(f"{'─' * 60}")

        # 發送問題
        result = await session.send(test_case['question'])

        # 如果有 HITL，自動確認
        if result.get('hitl'):
            print("📋 偵測到 HITL，自動確認...")
            await asyncio.sleep(0.5)
            result = await session.send("確認", is_resume=True)

        # 顯示結果
        if result.get('error'):
            print(f"❌ 錯誤: {result['error']}")
        else:
            print(f"✅ 完成 ({result['duration']}s) - 模式: {result['mode']}")
            response_preview = result['assistant'][:200] if result['assistant'] else "無回應"
            print(f"📝 回應預覽: {response_preview}...")

        # 間隔一下避免太快
        await asyncio.sleep(1)

    # 儲存結果
    filepath = session.save_results()

    print("\n" + "=" * 60)
    print("📊 測試完成")
    print("=" * 60)
    print(f"總測試數: {session.round_count}")
    print(f"錯誤數: {len(session.errors)}")

    if session.errors:
        print("\n❌ 發現的錯誤:")
        for err in session.errors:
            print(f"  - Round {err['round']}: {err['error'][:100]}")

    print(f"\n💾 結果已儲存: {filepath}")

    return session


if __name__ == "__main__":
    asyncio.run(run_auto_test())
