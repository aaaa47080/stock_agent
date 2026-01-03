import os
import sys
import json
import time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agents import BullResearcher, BearResearcher, CommitteeSynthesizer
from core.models import AnalystReport, ResearcherDebate
from utils.llm_client import create_llm_client_from_config
from core.config import BULL_COMMITTEE_MODELS, BEAR_COMMITTEE_MODELS, SYNTHESIS_MODEL

# Load env
load_dotenv()

def run_debug_committee():
    print("🚀 開始測試委員會模式 (Committee Mode)...")
    print("--------------------------------------------------")
    
    # 1. 檢查配置
    print(f"📋 讀取多頭委員會配置: 共 {len(BULL_COMMITTEE_MODELS)} 位成員")
    for i, model_cfg in enumerate(BULL_COMMITTEE_MODELS):
        print(f"   [多頭成員 {i+1}] Provider: {model_cfg.get('provider')}, Model: {model_cfg.get('model')}")
        
    print(f"\n📋 讀取空頭委員會配置: 共 {len(BEAR_COMMITTEE_MODELS)} 位成員")
    for i, model_cfg in enumerate(BEAR_COMMITTEE_MODELS):
        print(f"   [空頭成員 {i+1}] Provider: {model_cfg.get('provider')}, Model: {model_cfg.get('model')}")
    
    print(f"\n🤖 讀取綜合模型配置: {SYNTHESIS_MODEL.get('model')} ({SYNTHESIS_MODEL.get('provider')})")
    print("--------------------------------------------------")

    # 2. 準備假數據 (Mock Data)
    print("📦 準備假分析師報告...")
    mock_reports = [
        AnalystReport(
            analyst_type="技術分析師",
            summary="根據目前的技術指標分析，RSI 已經顯示出嚴重的超賣信號（數值約為 25），同時 MACD 剛剛完成低位黃金交叉，這是一個非常強烈的短期底部反彈信號，預計價格在未來幾個交易日內會有明顯的回升空間。",
            key_findings=["RSI 超賣", "MACD 金叉"],
            bullish_points=["技術指標觸底反彈"],
            bearish_points=[],
            confidence=85
        ),
        AnalystReport(
            analyst_type="新聞分析師",
            summary="根據最新的市場消息，SEC 剛剛正式批准了多個現貨 ETF 的申請，這標誌著機構資金將開始大規模進場。市場情緒目前處於極度樂觀的狀態，多個社群媒體的討論量創下歷史新高，利多消息正在持續發酵中。",
            key_findings=["ETF 批准", "機構進場"],
            bullish_points=["重大利好落地"],
            bearish_points=[],
            confidence=95
        )
    ]

    # ==========================================
    # 3. 多頭委員會 (Bull Committee)
    # ==========================================
    print("\n⚡ 3. 啟動多頭委員會並行思考...")
    start_time = time.time()
    
    bull_committee_args = []
    
    with ThreadPoolExecutor(max_workers=len(BULL_COMMITTEE_MODELS)) as executor:
        futures = []
        for i, cfg in enumerate(BULL_COMMITTEE_MODELS):
            print(f"   -> 啟動多頭成員 {i+1} ({cfg.get('model')})...")
            try:
                client, model_name = create_llm_client_from_config(cfg)
                researcher = BullResearcher(client, model=model_name)
                futures.append(executor.submit(
                    researcher.debate, 
                    mock_reports, 
                    [], 
                    1, 
                    "技術與新聞"
                ))
            except Exception as e:
                print(f"   ❌ 多頭成員 {i+1} 初始化失敗: {e}")

        for i, future in enumerate(as_completed(futures)):
            try:
                res = future.result()
                bull_committee_args.append(res)
                print(f"   ✅ 收到多頭成員 {len(bull_committee_args)} 的觀點 (信心度: {res.confidence}%)")
                print(f"      [論點摘要]: {res.argument[:150]}...")
                print(f"      [關鍵點]: {', '.join(res.key_points)}")
                print("-" * 30)
            except Exception as e:
                print(f"   ❌ 某多頭成員執行失敗: {e}")

    # ==========================================
    # 4. 空頭委員會 (Bear Committee)
    # ==========================================
    print("\n⚡ 4. 啟動空頭委員會並行思考...")
    
    bear_committee_args = []
    
    with ThreadPoolExecutor(max_workers=len(BEAR_COMMITTEE_MODELS)) as executor:
        futures = []
        for i, cfg in enumerate(BEAR_COMMITTEE_MODELS):
            print(f"   -> 啟動空頭成員 {i+1} ({cfg.get('model')})...")
            try:
                client, model_name = create_llm_client_from_config(cfg)
                researcher = BearResearcher(client, model=model_name)
                # 空頭需要看多頭的觀點嗎？在第一輪通常不需要，或是給一些預設的
                futures.append(executor.submit(
                    researcher.debate, 
                    mock_reports, 
                    bull_committee_args, # 空頭可以看到多頭的觀點進行反駁
                    1, 
                    "技術與新聞"
                ))
            except Exception as e:
                print(f"   ❌ 空頭成員 {i+1} 初始化失敗: {e}")

        for i, future in enumerate(as_completed(futures)):
            try:
                res = future.result()
                bear_committee_args.append(res)
                print(f"   ✅ 收到空頭成員 {len(bear_committee_args)} 的觀點 (信心度: {res.confidence}%)")
                print(f"      [論點摘要]: {res.argument[:150]}...")
                print(f"      [關鍵點]: {', '.join(res.key_points)}")
                print("-" * 30)
            except Exception as e:
                print(f"   ❌ 某空頭成員執行失敗: {e}")

    duration = time.time() - start_time
    print(f"⏱️  委員會發言結束，耗時 {duration:.2f} 秒")
    print(f"   共收集到 {len(bull_committee_args)} 份多頭觀點, {len(bear_committee_args)} 份空頭觀點")


    # ==========================================
    # 5. 測試觀點合成 (Synthesizer)
    # ==========================================
    print("\n⚗️  5. 測試觀點合成 (Synthesizer)...")
    try:
        test_synthesis_config = {
            "provider": "google_gemini",
            "model": "gemini-3-flash-preview"
        }
        print(f"   >> (Debug) 切換合成模型為: {test_synthesis_config['model']}")
        
        synth_client, synth_model_name = create_llm_client_from_config(test_synthesis_config)
        synthesizer = CommitteeSynthesizer(synth_client, model=synth_model_name)
        
        # 合成多頭
        final_bull_arg = synthesizer.synthesize_committee_views(
            'Bull', 
            bull_committee_args, 
            mock_reports
        )
        
        # 合成空頭
        final_bear_arg = synthesizer.synthesize_committee_views(
            'Bear', 
            bear_committee_args, 
            mock_reports
        )
        
        print("\n==================================================")
        print("🏆 最終合成觀點 (Bull Consensus):")
        print("==================================================")
        print(final_bull_arg.argument)
        print("--------------------------------------------------")
        print(f"信心度: {final_bull_arg.confidence}%")
        print("==================================================")
        
        print("\n==================================================")
        print("🐻 最終合成觀點 (Bear Consensus):")
        print("==================================================")
        print(final_bear_arg.argument)
        print("--------------------------------------------------")
        print(f"信心度: {final_bear_arg.confidence}%")
        print("==================================================")

        print("✅ 委員會模式測試成功！")
        
    except Exception as e:
        print(f"❌ 合成失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_debug_committee()
