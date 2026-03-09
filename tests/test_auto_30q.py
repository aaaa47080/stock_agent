"""
自動化 30 題測試 - 包含簡單、複雜、推理、深入問題
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

# 30 題測試問題 - 涵蓋簡單(5)、複雜(10)、推理(10)、深入(5)
TEST_QUESTIONS = [
    # === 簡單問題 (1-5) - 快速驗證基本功能 ===
    {"id": 1, "category": "簡單", "question": "BTC 現在多少錢？", "expected": "價格查詢"},
    {"id": 2, "category": "簡單", "question": "ETH 的價格是多少？", "expected": "價格查詢"},
    {"id": 3, "category": "簡單", "question": "今天加密貨幣市場整體表現如何？", "expected": "市場概況"},
    {"id": 4, "category": "簡單", "question": "SOL 是什麼幣？", "expected": "幣種介紹"},
    {"id": 5, "category": "簡單", "question": "目前比特幣市值多少？", "expected": "市值查詢"},

    # === 複雜問題 (6-15) - 需要多步驟思考 ===
    {"id": 6, "category": "複雜", "question": "比較 BTC 和 ETH 過去一週的價格走勢，哪個表現更好？", "expected": "多幣比較分析"},
    {"id": 7, "category": "複雜", "question": "分析 DOGE 最近有什麼重大新聞，這些新聞對價格有什麼影響？", "expected": "新聞+價格關聯分析"},
    {"id": 8, "category": "複雜", "question": "請幫我查詢 BTC、ETH、SOL 三種幣的技術指標（RSI、MACD），並分析哪個最適合現在買入？", "expected": "技術分析+比較"},
    {"id": 9, "category": "複雜", "question": "列出目前漲幅前 5 的加密貨幣，並分析它們上漲的可能原因", "expected": "排行榜+原因分析"},
    {"id": 10, "category": "複雜", "question": "XRP 最近的法律訴訟進展如何？這對價格有什麼影響？", "expected": "法律事件+價格影響"},
    {"id": 11, "category": "複雜", "question": "請分析比特幣的鏈上數據，包括活躍地址數和交易量趨勢", "expected": "鏈上數據分析"},
    {"id": 12, "category": "複雜", "question": "穩定幣 USDT 和 USDC 有什麼區別？哪個更安全？", "expected": "穩定幣比較"},
    {"id": 13, "category": "複雜", "question": "以太坊的 Gas 費用現在是多少？跟昨天相比是漲還是跌？", "expected": "Gas費用分析"},
    {"id": 14, "category": "複雜", "question": "分析目前加密貨幣市場的恐懼貪婪指數，這代表什麼意思？", "expected": "情緒指標解讀"},
    {"id": 15, "category": "複雜", "question": "DeFi 協議中目前 TVL 最高的三個是什麼？它們的特點是什麼？", "expected": "DeFi TVL 分析"},

    # === 推理問題 (16-25) - 需要邏輯推導 ===
    {"id": 16, "category": "推理", "question": "如果美國聯準會下週宣布升息，你認為這對 BTC 價格會有什麼影響？為什麼？", "expected": "宏觀經濟推理"},
    {"id": 17, "category": "推理", "question": "比特幣減半事件預計在什麼時候發生？根據歷史數據，減半前後價格通常會如何變化？", "expected": "歷史規律推理"},
    {"id": 18, "category": "推理", "question": "如果我有 10000 美元要投資加密貨幣，你會建議我如何配置？請考慮風險和回報", "expected": "投資組合建議"},
    {"id": 19, "category": "推理", "question": "根據 BTC 的歷史價格數據，目前是否處於牛市還是熊市？你的判斷依據是什麼？", "expected": "市場週期判斷"},
    {"id": 20, "category": "推理", "question": "以太坊轉 POS 之後，對 ETH 的長期價值有什麼影響？請分析優缺點", "expected": "技術變革影響"},
    {"id": 21, "category": "推理", "question": "如果某個國家宣布禁止加密貨幣交易，這會對全球市場造成什麼影響？", "expected": "政策影響推理"},
    {"id": 22, "category": "推理", "question": "機構投資者進入加密貨幣市場，這對散戶投資者是好事還是壞事？", "expected": "市場結構分析"},
    {"id": 23, "category": "推理", "question": "NFT 市場目前的狀況如何？未來還有發展潛力嗎？", "expected": "市場趨勢預測"},
    {"id": 24, "category": "推理", "question": "Layer 2 解決方案（如 Arbitrum、Optimism）對以太坊有什麼意義？", "expected": "技術架構分析"},
    {"id": 25, "category": "推理", "question": "如果比特幣 ETF 獲得批准，這會如何改變加密貨幣市場？", "expected": "金融產品影響"},

    # === 深入問題 (26-30) - 多輪對話/深入探討 ===
    {"id": 26, "category": "深入", "question": "請詳細解釋區塊鏈的三難困境（Trilemma），以及各種項目是如何嘗試解決這個問題的", "expected": "技術深入探討"},
    {"id": 27, "category": "深入", "question": "分析加密貨幣的監管趨勢，全球各國的態度有什麼不同？這對行業發展有什麼影響？", "expected": "監管環境分析"},
    {"id": 28, "category": "深入", "question": "Web3 的核心理念是什麼？它與 Web2 有什麼根本性的區別？目前有哪些成功的 Web3 應用？", "expected": "Web3 概念探討"},
    {"id": 29, "category": "深入", "question": "加密貨幣市場存在哪些操縱行為？投資者應該如何識別和避免？", "expected": "市場操縱分析"},
    {"id": 30, "category": "深入", "question": "從技術角度分析比特幣和以太坊的根本差異，它們各自的優缺點是什麼？", "expected": "技術深度比較"},
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

    async def send(self, message: str, is_resume: bool = False) -> dict:
        """發送訊息"""
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

    def save_results(self, scores: list):
        """儲存測試結果"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auto_test_30q_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        # 計算統計
        category_scores = {}
        for s in scores:
            cat = s["category"]
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(s["score"])

        avg_by_category = {cat: round(sum(s)/len(s), 2) for cat, s in category_scores.items()}
        total_avg = round(sum(s["score"] for s in scores) / len(scores), 2) if scores else 0

        result = {
            "scenario": "auto_30q_test",
            "session_id": self.session_id,
            "total_rounds": self.round_count,
            "total_score": total_avg,
            "category_avg": avg_by_category,
            "scores": scores,
            "conversation": self.conversation_log,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
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
    print("🚀 開始自動化 30 題測試")
    print("=" * 70)

    session = AutoTestSession(manager, f"auto_30q_{int(time.time())}")
    scores = []

    for i, q in enumerate(TEST_QUESTIONS):
        print(f"\n{'─' * 70}")
        print(f"[{i+1}/30] 【{q['category']}】問題 {q['id']}")
        print(f"📝 {q['question']}")
        print(f"🎯 期望: {q['expected']}")
        print(f"{'─' * 70}")

        try:
            # 發送問題
            result = await session.send(q['question'])

            # 如果有 HITL 確認，自動確認
            while result.get('hitl'):
                print("📋 偵測到 HITL，自動確認執行...")
                result = await session.send("好", is_resume=True)

            # 顯示回應
            response = result.get('assistant', '無回應')
            print(f"\n🤖 AI 回應 ({result['duration']}s, 模式: {result['mode']}):")
            print("-" * 50)

            # 截取顯示（避免太長）
            if len(response) > 800:
                print(response[:800] + "\n... (回應已截斷)")
            else:
                print(response)

            # 評分提示（這裡可以根據回應內容自動評分或讓使用者輸入）
            # 目前先給預設分數，實際可以更智能地評分
            score = 7  # 預設分數
            comment = "待評估"

            scores.append({
                "id": q['id'],
                "category": q['category'],
                "question": q['question'],
                "expected": q['expected'],
                "response_preview": response[:500] if response else "",
                "duration": result['duration'],
                "mode": result['mode'],
                "score": score,
                "comment": comment,
            })

            print(f"\n📊 暫定評分: {score}/10")

            # 短暫暫停避免 API 限流
            await asyncio.sleep(1)

        except Exception as e:
            print(f"\n❌ 問題 {q['id']} 發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            scores.append({
                "id": q['id'],
                "category": q['category'],
                "question": q['question'],
                "expected": q['expected'],
                "response_preview": f"ERROR: {str(e)}",
                "duration": 0,
                "mode": "error",
                "score": 0,
                "comment": f"執行錯誤: {str(e)}",
            })

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
    print(f"\n  總平均: {total_avg:.1f}/10")


if __name__ == "__main__":
    asyncio.run(run_auto_test())
