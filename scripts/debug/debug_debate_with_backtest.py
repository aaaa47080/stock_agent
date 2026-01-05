import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
import json
import openai
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.data_processor import fetch_and_process_klines, build_market_data_package
from core.agents import TechnicalAnalyst, BullResearcher, BearResearcher, NeutralResearcher
from core.models import AnalystReport
from utils.llm_client import create_llm_client_from_config
from core.config import BULL_RESEARCHER_MODEL, BEAR_RESEARCHER_MODEL

# Load env
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def run_debug_debate():
    symbol = "BTC-USDT"
    print(f"🔍 1. 正在獲取 {symbol} 數據 (包含歷史回測)...")
    
    # 1. 獲取數據 (增加到 300 條以確保有足夠數據產生回測信號)
    df, funding_info = fetch_and_process_klines(symbol, "1d", 300, "spot", "okx")
    market_data = build_market_data_package(
        df=df,
        symbol=symbol,
        market_type="spot",
        exchange="okx",
        leverage=1,
        funding_rate_info=funding_info
    )
    
    # 檢查回測數據是否存在
    backtest_data = market_data.get('歷史回測', [])
    print(f"   >> 獲取到 {len(backtest_data)} 筆回測策略結果")
    if backtest_data:
        print(f"   >> 最佳策略摘要: {backtest_data[0].get('summary')}")

    # 2. 運行技術分析師 (產生包含回測的報告)
    print("\n🤖 2. 正在運行 TechnicalAnalyst (讓它解讀回測數據)...")
    tech_analyst = TechnicalAnalyst(client)
    tech_report = tech_analyst.analyze(market_data)
    
    print("\n   [技術分析師報告摘要]:")
    print(f"   {tech_report.summary}")
    print(f"   關鍵發現: {tech_report.key_findings}")

    # 模擬其他分析師的簡單報告 (為了省 Token，這裡手動創建簡單的 Dummy Reports)
    sentiment_report = AnalystReport(
        analyst_type="情緒分析師",
        summary="市場情緒目前呈現極度貪婪的狀態，恐慌與貪婪指數已經達到 75 的高位。社交媒體上的討論熱度持續升溫，散戶投資者的參與度顯著增加，這通常是市場可能出現短期回調的警訊，建議投資人保持謹慎，不要盲目追高。",
        key_findings=["社交情緒高漲", "資金費率正值"],
        bullish_points=["散戶湧入"],
        bearish_points=["可能過熱"],
        confidence=80
    )
    
    analyst_reports = [tech_report, sentiment_report]

    # 3. 觸發辯論 (第一輪)
    print("\n⚔️ 3. 開始辯論 (Round 1)...")
    
    # 初始化正確的模型客戶端
    bull_client, bull_model_name = create_llm_client_from_config(BULL_RESEARCHER_MODEL)
    bear_client, bear_model_name = create_llm_client_from_config(BEAR_RESEARCHER_MODEL)

    # 多頭發言
    print("\n--- [多頭研究員 Bull] ---")
    bull_researcher = BullResearcher(bull_client, model=bull_model_name)
    bull_arg = bull_researcher.debate(analyst_reports, [], round_number=1, topic="技術與回測數據")
    print(f"論點:\n{bull_arg.argument}")
    print(f"引用關鍵點: {bull_arg.key_points}")

    # 空頭發言
    print("\n--- [空頭研究員 Bear] ---")
    bear_researcher = BearResearcher(bear_client, model=bear_model_name)
    bear_arg = bear_researcher.debate(analyst_reports, [bull_arg], round_number=1, topic="技術與回測數據")
    print(f"論點:\n{bear_arg.argument}")
    print(f"針對反駁: {bear_arg.counter_arguments}")

    # 4. 驗證是否提到回測
    print("\n==========================================")
    print("🔍 驗證結果:")
    
    combined_text = (tech_report.summary + str(tech_report.key_findings) + 
                    bull_arg.argument + bear_arg.argument)
    
    keywords = ["回測", "勝率", "歷史", "策略", "RSI", "MA", "回報"]
    found_keywords = [kw for kw in keywords if kw in combined_text]
    
    if found_keywords:
        print(f"✅ 成功! 在辯論中檢測到以下回測相關關鍵詞: {found_keywords}")
    else:
        print("❌ 警告: 辯論中似乎未明確提及回測數據，可能需要調整 Prompt 權重。\n")

if __name__ == "__main__":
    run_debug_debate()
