"""
測試多輪辯論機制
"""
import os
from dotenv import load_dotenv
import openai
from agents import BullResearcher, BearResearcher
from models import AnalystReport
from settings import Settings

load_dotenv()

def test_multi_round_debate():
    """測試多輪辯論功能"""

    print("=" * 80)
    print("測試多輪辯論機制")
    print("=" * 80)

    # 設置辯論輪數
    Settings.DEBATE_ROUNDS = 2
    print(f"\n辯論輪數設置: {Settings.DEBATE_ROUNDS} 輪\n")

    # 創建 OpenAI 客戶端
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("❌ 錯誤：找不到 OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)

    # 創建模擬的分析師報告
    analyst_reports = [
        AnalystReport(
            analyst_type="技術分析師",
            summary="市場呈現上升趨勢，RSI 指標顯示超買，但 MACD 依然看漲。短期可能出現回調，但長期趨勢向上。價格突破了重要阻力位。",
            key_findings=["RSI 超買", "MACD 看漲", "突破阻力位"],
            bullish_points=["MACD 看漲", "突破阻力位", "成交量放大"],
            bearish_points=["RSI 超買", "短期可能回調"],
            confidence=75.0
        ),
        AnalystReport(
            analyst_type="情緒分析師",
            summary="市場情緒偏向樂觀，社交媒體討論熱度上升。投資者信心增強，但也出現部分獲利了結的跡象。整體市場氛圍積極。",
            key_findings=["情緒樂觀", "討論熱度上升", "部分獲利了結"],
            bullish_points=["情緒樂觀", "投資者信心增強"],
            bearish_points=["部分獲利了結"],
            confidence=70.0
        )
    ]

    # 創建研究員
    print("🔧 初始化研究員...")
    bull_researcher = BullResearcher(client)
    bear_researcher = BearResearcher(client)

    # 進行多輪辯論
    bull_argument = None
    bear_argument = None

    for round_num in range(1, Settings.DEBATE_ROUNDS + 1):
        print("\n" + "=" * 80)
        print(f"第 {round_num}/{Settings.DEBATE_ROUNDS} 輪辯論")
        print("=" * 80)

        # 多頭發言
        print(f"\n🐂 多頭研究員發言（第 {round_num} 輪）...")
        if bear_argument:
            print(f"   💡 多頭看到了空頭的觀點: {bear_argument.argument[:100]}...")

        bull_argument = bull_researcher.debate(
            analyst_reports=analyst_reports,
            opponent_argument=bear_argument,
            round_number=round_num
        )

        print(f"\n✅ 多頭論點:")
        print(f"   信心度: {bull_argument.confidence}%")
        print(f"   論點: {bull_argument.argument[:150]}...")
        print(f"   關鍵點: {bull_argument.key_points[:2]}")

        # 空頭發言
        print(f"\n🐻 空頭研究員發言（第 {round_num} 輪）...")
        print(f"   💡 空頭看到了多頭的觀點: {bull_argument.argument[:100]}...")

        bear_argument = bear_researcher.debate(
            analyst_reports=analyst_reports,
            opponent_argument=bull_argument,
            round_number=round_num
        )

        print(f"\n✅ 空頭論點:")
        print(f"   信心度: {bear_argument.confidence}%")
        print(f"   論點: {bear_argument.argument[:150]}...")
        print(f"   關鍵點: {bear_argument.key_points[:2]}")

    # 最終結果
    print("\n" + "=" * 80)
    print("辯論結果總結")
    print("=" * 80)
    print(f"\n🐂 多頭最終信心度: {bull_argument.confidence}%")
    print(f"🐻 空頭最終信心度: {bear_argument.confidence}%")

    if bull_argument.confidence > bear_argument.confidence:
        print(f"\n✅ 多頭觀點更有說服力（信心度差: {bull_argument.confidence - bear_argument.confidence:.1f}%）")
    else:
        print(f"\n✅ 空頭觀點更有說服力（信心度差: {bear_argument.confidence - bull_argument.confidence:.1f}%）")

    print("\n✅ 多輪辯論測試完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_multi_round_debate()
