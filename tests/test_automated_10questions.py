"""
自動化 10 題測試 - 從簡單到困難

執行方式:
    python tests/test_automated_10questions.py
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

# 10 個測試題目（由簡到難）
TEST_QUESTIONS = [
    # 🟢 Level 1: 基礎價格查詢
    {
        "id": "1.1",
        "level": "簡單",
        "query": "BTC 價格",
        "expected": "回傳 BTC 當前價格數值",
    },
    {
        "id": "1.2",
        "level": "簡單",
        "query": "台積電股價",
        "expected": "識別「台積電」=「2330」並回傳價格",
    },
    {
        "id": "1.3",
        "level": "簡單",
        "query": "TSLA 價格",
        "expected": "回傳 TSLA 當前價格",
    },
    # 🟡 Level 2: 單一市場分析
    {
        "id": "2.1",
        "level": "中等",
        "query": "ETH 技術分析",
        "expected": "包含 RSI、MACD 等技術指標",
    },
    {
        "id": "2.2",
        "level": "中等",
        "query": "鴻海的本益比和 EPS",
        "expected": "識別「鴻海」=「2317」並回傳數據",
    },
    {
        "id": "2.3",
        "level": "中等",
        "query": "比特幣最新新聞",
        "expected": "回傳近期相關新聞",
    },
    # 🟠 Level 3: 多市場與上下文
    {
        "id": "3.1",
        "level": "困難",
        "query": "台積電 ADR 和台股的價差",
        "expected": "同時查詢 TSM 和 2330 並比較",
    },
    {
        "id": "3.2",
        "level": "困難",
        "query": "黃金價格",
        "expected": "識別為大宗商品並回傳價格",
    },
    # 🔴 Level 4: 複雜綜合分析
    {
        "id": "4.1",
        "level": "專家",
        "query": "我想投資輝達，給我完整分析",
        "expected": "多維度分析（技術面、基本面、新聞）",
    },
    {
        "id": "4.2",
        "level": "專家",
        "query": "現在加密貨幣市場整體情緒如何？",
        "expected": "包含恐慌貪婪指數和市場分析",
    },
]


class AutomatedTestSession:
    """自動化測試 Session"""

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

        # 判斷是否為確認詞
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

    def save_results(self, test_results: list):
        """儲存測試結果"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"automated_test_10questions_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        result = {
            "test_date": datetime.now().isoformat(),
            "total_questions": len(test_results),
            "test_results": test_results,
            "conversation": self.conversation_log,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n💾 測試結果已儲存: {filepath}")
        return filepath


def evaluate_response(test_case: dict, response: str, mode: str) -> dict:
    """評估回應品質"""
    query = test_case["query"]
    expected = test_case["expected"]
    test_id = test_case["id"]

    score = 0
    notes = []
    issues = []

    # 基本檢查：是否有回應
    if not response or response == "無回應":
        return {
            "test_id": test_id,
            "query": query,
            "expected": expected,
            "actual": response,
            "score": 0,
            "notes": "無回應",
            "issues": ["no_response"],
        }

    # 檢查是否包含數值（針對價格類問題）
    if any(kw in query for kw in ["價格", "多少錢", "股價"]):
        import re

        has_number = bool(re.search(r"\$?[\d,]+\.?\d*", response))
        if has_number:
            score += 3
            notes.append("✓ 包含價格數值")
        else:
            issues.append("missing_price_value")

    # 檢查技術指標（針對技術分析問題）
    if "技術" in query:
        tech_indicators = ["RSI", "MACD", "MA", "均線", "KD", "布林"]
        found_indicators = [
            ind for ind in tech_indicators if ind in response.upper() or ind in response
        ]
        if len(found_indicators) >= 2:
            score += 4
            notes.append(f"✓ 包含技術指標: {', '.join(found_indicators)}")
        elif len(found_indicators) == 1:
            score += 2
            notes.append(f"△ 僅包含一個指標: {found_indicators[0]}")
        else:
            issues.append("missing_technical_indicators")

    # 檢查基本面數據（針對基本面問題）
    if any(kw in query for kw in ["本益比", "EPS", "基本面"]):
        fundamentals = ["本益比", "P/E", "EPS", "ROE", "營收", "淨值"]
        found_fundamentals = [f for f in fundamentals if f in response]
        if found_fundamentals:
            score += 3
            notes.append(f"✓ 包含基本面數據: {', '.join(found_fundamentals)}")
        else:
            issues.append("missing_fundamentals")

    # 檢查新聞（針對新聞問題）
    if "新聞" in query:
        if any(kw in response for kw in ["新聞", "消息", "報導", "宣布"]):
            score += 3
            notes.append("✓ 包含新聞內容")
        else:
            issues.append("missing_news_content")

    # 檢查市場識別
    if "台積電" in query or "鴻海" in query:
        if "2330" in response or "2317" in response or "台股" in response:
            score += 2
            notes.append("✓ 正確識別為台股")
        else:
            issues.append("market_misidentification")

    if "輝達" in query:
        if "NVDA" in response.upper() or "美股" in response:
            score += 2
            notes.append("✓ 正確識別為美股")
        else:
            issues.append("market_misidentification")

    # 檢查商品識別
    if "黃金" in query:
        if any(kw in response for kw in ["黃金", "XAU", "商品", "GOLD"]):
            score += 3
            notes.append("✓ 正確識別為大宗商品")
        else:
            issues.append("commodity_misidentification")

    # 檢查恐慌貪婪指數
    if "情緒" in query or "市場整體" in query:
        if any(kw in response for kw in ["恐慌", "貪婪", "Fear", "Greed", "指數"]):
            score += 3
            notes.append("✓ 包含市場情緒指標")
        else:
            issues.append("missing_sentiment_indicator")

    # 基礎分數（有回應就給分）
    score += 3

    # 長度檢查
    if len(response) < 50:
        score -= 1
        notes.append("△ 回應過短")
        issues.append("response_too_short")
    elif len(response) > 100:
        score += 1
        notes.append("✓ 回應詳細")

    # 確保分數在 0-10 範圍內
    score = max(0, min(10, score))

    return {
        "test_id": test_id,
        "level": test_case["level"],
        "query": query,
        "expected": expected,
        "actual": response[:500] + "..." if len(response) > 500 else response,
        "mode": mode,
        "score": score,
        "notes": " | ".join(notes) if notes else "基本通過",
        "issues": issues if issues else [],
    }


async def run_automated_tests():
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

    print("\n" + "=" * 70)
    print("🎯 開始自動化測試 - 10 題（由簡到難）")
    print("=" * 70)

    session = AutomatedTestSession(manager, f"auto_test_{int(time.time())}")
    test_results = []

    for i, test_case in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'─' * 70}")
        print(f"[Test {test_case['id']}] {test_case['level']} - 第 {i}/10 題")
        print(f"問題: {test_case['query']}")
        print(f"預期: {test_case['expected']}")
        print(f"{'─' * 70}")

        try:
            # 發送問題
            is_resume = session.pending_hitl is not None
            result = await session.send(test_case["query"], is_resume=is_resume)

            # 如果有 HITL，自動確認
            if result.get("hitl"):
                print("\n⏳ 系統規劃了任務，自動確認執行...")
                confirm_result = await session.send("好", is_resume=True)
                result = confirm_result

            response = result["assistant"]
            mode = result["mode"]

            # 評估結果
            evaluation = evaluate_response(test_case, response, mode)
            test_results.append(evaluation)

            # 顯示結果
            score = evaluation["score"]
            score_emoji = "✅" if score >= 8 else "⚠️" if score >= 6 else "❌"
            print(f"\n{score_emoji} 得分: {score}/10")
            print(f"模式: {mode}")
            print(f"評語: {evaluation['notes']}")

            if evaluation["issues"]:
                print(f"問題: {', '.join(evaluation['issues'])}")

            print("\n回應預覽:")
            print(f"{response[:300]}{'...' if len(response) > 300 else ''}")

            # 短暫延遲避免 API 限流
            await asyncio.sleep(1)

        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            import traceback

            traceback.print_exc()
            test_results.append(
                {
                    "test_id": test_case["id"],
                    "query": test_case["query"],
                    "expected": test_case["expected"],
                    "actual": f"ERROR: {str(e)}",
                    "score": 0,
                    "notes": "測試執行失敗",
                    "issues": ["execution_error"],
                }
            )

    # 計算總分
    print("\n" + "=" * 70)
    print("📊 測試結果總結")
    print("=" * 70)

    total_score = sum(r["score"] for r in test_results)
    max_score = len(test_results) * 10
    percentage = (total_score / max_score) * 100

    # 評級
    if percentage >= 90:
        grade = "A+"
        grade_emoji = "🏆"
    elif percentage >= 80:
        grade = "A"
        grade_emoji = "🥇"
    elif percentage >= 70:
        grade = "B"
        grade_emoji = "🥈"
    elif percentage >= 60:
        grade = "C"
        grade_emoji = "🥉"
    else:
        grade = "F"
        grade_emoji = "❌"

    print(f"\n總分: {total_score}/{max_score} ({percentage:.1f}%)")
    print(f"等級: {grade_emoji} {grade}")

    # 各等級統計
    level_stats = {}
    for result in test_results:
        level = result.get("level", "未知")
        if level not in level_stats:
            level_stats[level] = {"total": 0, "score": 0, "passed": 0}
        level_stats[level]["total"] += 1
        level_stats[level]["score"] += result["score"]
        if result["score"] >= 6:
            level_stats[level]["passed"] += 1

    print("\n各等級表現:")
    for level, stats in level_stats.items():
        avg = stats["score"] / stats["total"]
        pass_rate = (stats["passed"] / stats["total"]) * 100
        print(f"  {level}: 平均 {avg:.1f}/10, 通過率 {pass_rate:.0f}%")

    # 失敗的測試
    failed_tests = [r for r in test_results if r["score"] < 6]
    if failed_tests:
        print(f"\n❌ 失敗的測試 ({len(failed_tests)} 題):")
        for test in failed_tests:
            print(f"  [{test['test_id']}] {test['query']}")
            print(f"    問題: {', '.join(test['issues'])}")

    # 儲存結果
    session.save_results(test_results)

    return test_results


if __name__ == "__main__":
    asyncio.run(run_automated_tests())
