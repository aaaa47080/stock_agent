"""
自動化交互測試 - 使用原本的 InteractiveSession 邏輯
測試 15+ 輪複雜/推理/深入問題
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

from utils.settings import Settings

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results"
)

# 測試問題 - 15+ 輪，包含複雜、推理、深入問題
TEST_QUESTIONS = [
    # 第 1 輪 - 複雜問題
    {
        "round": 1,
        "category": "複雜",
        "question": "請分析 BTC 目前價格和過去 7 天的價格走勢",
        "expected": "價格分析",
    },
    # 第 2 輪 - 追問
    {
        "round": 2,
        "category": "推理",
        "question": "根據剛才的分析，你認為現在是買入的好時機嗎？為什麼？",
        "expected": "投資建議推理",
    },
    # 第 3 輪 - 深入
    {
        "round": 3,
        "category": "深入",
        "question": "那如果我現在投入 5000 美元，根據歷史數據，預期收益和風險分別是多少？",
        "expected": "風險收益分析",
    },
    # 第 4 輪 - 複雜
    {
        "round": 4,
        "category": "複雜",
        "question": "請比較 ETH 和 SOL 的技術優勢和缺點",
        "expected": "技術比較",
    },
    # 第 5 輪 - 推理
    {
        "round": 5,
        "category": "推理",
        "question": "考慮到以太坊的 Gas 費問題，你認為 Layer 2 解決方案會完全取代以太坊主網嗎？",
        "expected": "技術趨勢推理",
    },
    # 第 6 輪 - 深入
    {
        "round": 6,
        "category": "深入",
        "question": "解釋一下什麼是 DeFi 樂高（Composability），並舉個實際例子",
        "expected": "DeFi 概念解釋",
    },
    # 第 7 輪 - 複雜
    {
        "round": 7,
        "category": "複雜",
        "question": "目前 TVL 最高的 DeFi 協議是哪些？它們各有什麼風險？",
        "expected": "DeFi TVL 分析",
    },
    # 第 8 輪 - 推理
    {
        "round": 8,
        "category": "推理",
        "question": "如果 USDT 發生脫鉤事件，會對整個加密貨幣市場造成什麼影響？",
        "expected": "系統性風險推理",
    },
    # 第 9 輪 - 深入
    {
        "round": 9,
        "category": "深入",
        "question": "分析加密貨幣交易所的中心化風險，FTX 事件給我們什麼教訓？",
        "expected": "交易所風險分析",
    },
    # 第 10 輪 - 複雜
    {
        "round": 10,
        "category": "複雜",
        "question": "請查詢最近的加密貨幣市場新聞，有哪些重大事件？",
        "expected": "新聞查詢",
    },
    # 第 11 輪 - 推理
    {
        "round": 11,
        "category": "推理",
        "question": "這些新聞事件對市場情緒有什麼影響？恐懼貪婪指數現在是多少？",
        "expected": "市場情緒分析",
    },
    # 第 12 輪 - 深入
    {
        "round": 12,
        "category": "深入",
        "question": "從技術角度解釋比特幣的工作量證明（PoW）機制，它為什麼耗能這麼大？",
        "expected": "技術原理解釋",
    },
    # 第 13 輪 - 複雜
    {
        "round": 13,
        "category": "複雜",
        "question": "比特幣的能源消耗問題有哪些解決方案？這些方案可行嗎？",
        "expected": "能源問題分析",
    },
    # 第 14 輪 - 推理
    {
        "round": 14,
        "category": "推理",
        "question": "如果我要長期持有加密貨幣，應該選擇哪些幣種？請給出投資組合建議",
        "expected": "長期投資建議",
    },
    # 第 15 輪 - 深入
    {
        "round": 15,
        "category": "深入",
        "question": "解釋什麼是智能合約的安全審計，為什麼它這麼重要？",
        "expected": "安全審計解釋",
    },
    # 第 16 輪 - 複雜
    {
        "round": 16,
        "category": "複雜",
        "question": "列出最近發生智能合約漏洞的事件，損失了多少資金？",
        "expected": "安全事件查詢",
    },
    # 第 17 輪 - 推理
    {
        "round": 17,
        "category": "推理",
        "question": "根據我們之前的討論，總結一下投資加密貨幣的主要風險和應對策略",
        "expected": "風險總結",
    },
    # 第 18 輪 - 深入
    {
        "round": 18,
        "category": "深入",
        "question": "什麼是零知識證明？它在區塊鏈中有什麼應用？",
        "expected": "ZK 技術解釋",
    },
]


class InteractiveSession:
    """互動式測試 Session - 從原 test_interactive_user.py 複製"""

    def __init__(self, manager, session_id: str):
        self.manager = manager
        self.session_id = session_id
        self.history = []
        self.conversation_log = []
        self.pending_hitl = None
        self.round_count = 0

    async def send(self, message: str, is_resume: bool = False) -> dict:
        """發送訊息"""
        from langgraph.types import Command

        config = {"configurable": {"thread_id": self.session_id}}
        history_text = "\n".join(self.history[-12:]) if self.history else ""

        self.round_count += 1
        start_time = time.time()

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
            "開始",
            "請執行",
        ]
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
            "is_resume": is_resume,
        }
        self.conversation_log.append(log_entry)

        return log_entry

    def save_results(self, scores: list, filename_prefix: str = "auto_interactive"):
        """儲存測試結果"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        # 計算統計
        category_scores = {}
        for s in scores:
            cat = s["category"]
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(s["score"])

        avg_by_category = {
            cat: round(sum(s) / len(s), 2) for cat, s in category_scores.items()
        }
        total_avg = (
            round(sum(s["score"] for s in scores) / len(scores), 2) if scores else 0
        )

        result = {
            "scenario": "auto_interactive_test",
            "session_id": self.session_id,
            "total_rounds": self.round_count,
            "total_score": total_avg,
            "category_avg": avg_by_category,
            "scores": scores,
            "conversation": self.conversation_log,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n💾 測試結果已儲存: {filepath}")
        return filepath


async def run_auto_test():
    """自動化測試主程式"""

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

    print("\n" + "=" * 70)
    print("🚀 開始自動化交互測試 (18 輪對話)")
    print("=" * 70)

    session = InteractiveSession(manager, f"auto_interactive_{int(time.time())}")
    scores = []

    for i, q in enumerate(TEST_QUESTIONS):
        print(f"\n{'═' * 70}")
        print(f"[第 {q['round']} 輪] 【{q['category']}】")
        print(f"📝 問題: {q['question']}")
        print(f"🎯 期望: {q['expected']}")
        print(f"{'═' * 70}")

        try:
            # 發送問題
            result = await session.send(q["question"])

            # 如果有 HITL 確認，自動確認
            while result.get("hitl"):
                print("📋 偵測到 HITL，自動確認執行...")
                result = await session.send("好", is_resume=True)

            # 顯示回應
            response = result.get("assistant", "無回應")
            print(f"\n🤖 AI 回應 ({result['duration']}s | 模式: {result['mode']}):")
            print("-" * 60)

            # 顯示完整回應（最多1000字）
            if len(response) > 1000:
                print(response[:1000])
                print("\n... [回應已截斷，總長度: {} 字]".format(len(response)))
            else:
                print(response)

            # 等待用戶評分
            print("\n" + "-" * 60)
            print("📊 請為此回應評分 (0-10 分):")
            print("   評分標準:")
            print("   9-10: 完美回答，深入且準確")
            print("   7-8: 良好，基本正確但可改進")
            print("   5-6: 及格，有遺漏或小錯誤")
            print("   3-4: 不佳，重要資訊缺失或錯誤")
            print("   0-2: 完全錯誤或無回應")

            # 自動評分（根據回應質量）
            auto_score = 7  # 預設分數
            auto_comment = "待評估"

            # 簡單的自動評分邏輯
            if response and response != "無回應":
                if len(response) > 500:
                    auto_score = 7
                    auto_comment = "回應內容較詳細"
                if len(response) > 800:
                    auto_score = 8
                    auto_comment = "回應內容詳細且結構完整"
                if "錯誤" in response or "error" in response.lower():
                    auto_score = 4
                    auto_comment = "回應包含錯誤訊息"
                if response == "無回應" or len(response) < 50:
                    auto_score = 2
                    auto_comment = "回應過短或無效"
            else:
                auto_score = 1
                auto_comment = "無回應"

            scores.append(
                {
                    "round": q["round"],
                    "category": q["category"],
                    "question": q["question"],
                    "expected": q["expected"],
                    "response_preview": response[:500] if response else "",
                    "response_length": len(response) if response else 0,
                    "duration": result["duration"],
                    "mode": result["mode"],
                    "score": auto_score,
                    "comment": auto_comment,
                }
            )

            print(f"\n📊 自動評分: {auto_score}/10 - {auto_comment}")

            # 短暫暫停
            await asyncio.sleep(1)

        except Exception as e:
            print(f"\n❌ 第 {q['round']} 輪發生錯誤: {e}")
            import traceback

            traceback.print_exc()
            scores.append(
                {
                    "round": q["round"],
                    "category": q["category"],
                    "question": q["question"],
                    "expected": q["expected"],
                    "response_preview": f"ERROR: {str(e)}",
                    "response_length": 0,
                    "duration": 0,
                    "mode": "error",
                    "score": 0,
                    "comment": f"執行錯誤: {str(e)}",
                }
            )

    # 儲存結果
    print("\n" + "=" * 70)
    print("📊 測試完成！統計結果：")
    print("=" * 70)

    session.save_results(scores)

    # 按類別統計
    category_scores = {}
    for s in scores:
        cat = s["category"]
        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(s["score"])

    for cat, sc_list in category_scores.items():
        avg = sum(sc_list) / len(sc_list)
        print(f"  {cat}: {avg:.1f}/10 ({len(sc_list)} 題)")

    total_avg = sum(s["score"] for s in scores) / len(scores) if scores else 0
    print(f"\n  🏆 總平均: {total_avg:.1f}/10")

    # 列出每題得分
    print("\n📋 各題得分明細:")
    for s in scores:
        print(
            f"  第 {s['round']:2d} 輪 [{s['category']:2s}]: {s['score']}/10 - {s['comment']}"
        )


if __name__ == "__main__":
    asyncio.run(run_auto_test())
