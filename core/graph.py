import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openai
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from typing import TypedDict, List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import StateGraph, END

# 匯入我們自己的模組
from core.models import AnalystReport, ResearcherDebate, TraderDecision, RiskAssessment, FinalApproval
from data.data_processor import (
    fetch_and_process_klines,
    build_market_data_package
)
from core.agents import (
    TechnicalAnalyst,
    SentimentAnalyst,
    FundamentalAnalyst,
    NewsAnalyst,
    BullResearcher,
    BearResearcher,
    Trader,
    RiskManager,
    FundManager,
    CommitteeSynthesizer
)
from utils.settings import Settings

# 重新規劃次數上限（從配置讀取）
MAX_REPLANS = Settings.MAX_REPLANS

# 1. 定義狀態 (State)
class AgentState(TypedDict):
    """
    AgentState 就好比一個在所有節點間傳遞的公事包。
    每個節點都可以讀取其中的內容，並將自己的工作成果放進去，傳給下一個節點。
    """
    # --- 輸入參數 ---
    symbol: str
    interval: str
    limit: int
    market_type: str
    leverage: int
    exchange: str # Added
    preloaded_data: Optional[Dict]  # 用來接收預先抓好的資料
    # --- 多週期分析參數 ---
    include_multi_timeframe: bool  # 是否包含多週期分析
    short_term_interval: str       # 短週期時間間隔
    medium_term_interval: str      # 中週期時間間隔
    long_term_interval: str        # 長週期時間間隔
    # --- 客戶端與通用數據 ---
    client: openai.OpenAI
    market_data: Dict
    current_price: float
    funding_rate_info: Dict

    # --- 各階段的產出 ---
    analyst_reports: List[AnalystReport]
    bull_argument: ResearcherDebate
    bear_argument: ResearcherDebate
    trader_decision: TraderDecision
    risk_assessment: Optional[RiskAssessment] # 可能為 None
    final_approval: FinalApproval

    # --- 循環控制 ---
    replan_count: int


# 2. 創建節點 (Nodes)
# 每個節點都是一個函式，接收 state 作為參數，並返回一個包含更新後狀態的字典。

def prepare_data_node(state: AgentState) -> Dict:
    """
    節點 1: 準備所有需要的數據。
    功能：
    1. 初始化 OpenAI Client
    2. 檢查是否有預加載數據（緩存），如果有則直接使用
    3. 如果沒有緩存，則從交易所和新聞源撈取數據
    4. 可選：獲取多週期數據以進行更全面的分析

    已重構：將數據處理邏輯抽取到 data_processor.py，提高可維護性
    """
    print("\n[節點 1/7] 準備數據...")

    # 1. 初始化 OpenAI Client
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(">> 錯誤：找不到 OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)

    # 2. 檢查是否有預加載的數據（緩存機制）
    if state.get("preloaded_data"):
        print(">> [緩存命中] 檢測到預加載數據，跳過重複下載...")

        # 複製數據，避免修改原始緩存
        market_data = state["preloaded_data"].copy()

        # 更新市場類型和槓桿（這些參數可能不同）
        market_data["market_type"] = state["market_type"]
        market_data["leverage"] = state.get("leverage", 1)

        # 如果狀態中包含多週期參數，且預加載數據中沒有多週期信息，則添加多週期數據
        include_multi_timeframe = state.get("include_multi_timeframe", False)
        if include_multi_timeframe and "multi_timeframe_data" not in market_data:
            print(f">> [多週期模式] 預加載數據中添加多週期分析...")
            symbol = state['symbol']
            exchange = state['exchange']
            market_type = state['market_type']

            # 構建完整的市場數據包（使用重構後的函數，包含多週期分析）
            from data.data_processor import build_market_data_package
            df_with_indicators, funding_rate_info = fetch_and_process_klines(
                symbol=symbol,
                interval=state['interval'],  # 使用主週期
                limit=state['limit'],
                market_type=market_type,
                exchange=exchange
            )

            market_data = build_market_data_package(
                df=df_with_indicators,
                symbol=symbol,
                market_type=market_type,
                exchange=exchange,
                leverage=state.get("leverage", 1),
                funding_rate_info=funding_rate_info,
                include_multi_timeframe=True,
                short_term_interval=state.get("short_term_interval", "1h"),
                medium_term_interval=state.get("medium_term_interval", "4h"),
                long_term_interval=state.get("long_term_interval", "1d")
            )

        return {
            "client": client,
            "market_data": market_data,
            "current_price": market_data["價格資訊"]["當前價格"],
            "funding_rate_info": market_data.get("funding_rate_info", {}),
            "replan_count": 0
        }

    # 3. 沒有緩存，執行數據下載和處理
    symbol = state['symbol']
    interval = state['interval']
    limit = state['limit']
    market_type = state['market_type']
    exchange = state['exchange']
    leverage = state.get('leverage', 1)

    # 判斷是否需要多週期分析
    include_multi_timeframe = state.get("include_multi_timeframe", False)
    print(f">> [多週期模式] 包含多週期分析: {include_multi_timeframe}")

    if include_multi_timeframe:
        # 使用多週期數據構建函數
        from data.data_processor import build_market_data_package
        df_with_indicators, funding_rate_info = fetch_and_process_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
            market_type=market_type,
            exchange=exchange
        )

        market_data = build_market_data_package(
            df=df_with_indicators,
            symbol=symbol,
            market_type=market_type,
            exchange=exchange,
            leverage=leverage,
            funding_rate_info=funding_rate_info,
            include_multi_timeframe=True,
            short_term_interval=state.get("short_term_interval", "1h"),
            medium_term_interval=state.get("medium_term_interval", "4h"),
            long_term_interval=state.get("long_term_interval", "1d")
        )
    else:
        # 獲取並處理 K線數據（使用重構後的函數）
        df_with_indicators, funding_rate_info = fetch_and_process_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
            market_type=market_type,
            exchange=exchange
        )

        # 構建完整的市場數據包（使用重構後的函數）
        market_data = build_market_data_package(
            df=df_with_indicators,
            symbol=symbol,
            market_type=market_type,
            exchange=exchange,
            leverage=leverage,
            funding_rate_info=funding_rate_info,
            include_multi_timeframe=False  # 單週期模式
        )

    current_price = market_data["價格資訊"]["當前價格"]
    print(f">> 數據準備完成 | 當前價格: ${current_price:.2f}")

    return {
        "client": client,
        "market_data": market_data,
        "current_price": current_price,
        "funding_rate_info": funding_rate_info,
        "replan_count": 0
    }

def analyst_team_node(state: AgentState) -> Dict:
    """
    節點 2: 四位分析師並行工作。
    使用 ThreadPoolExecutor 實現真正的並行執行，提升 3-4 倍速度。
    """
    print("\n[節點 2/7] 分析師團隊 (並行分析)...")
    client, market_data, symbol = state['client'], state['market_data'], state['symbol']

    # 創建分析師實例
    analysts = {
        'technical': TechnicalAnalyst(client),
        'sentiment': SentimentAnalyst(client),
        'fundamental': FundamentalAnalyst(client),
        'news': NewsAnalyst(client)
    }

    # 定義分析任務
    def run_technical():
        print("  >> 技術分析師開始分析...")
        result = analysts['technical'].analyze(market_data)
        print("  >> 技術分析完成")
        return result

    def run_sentiment():
        print("  >> 情緒分析師開始分析...")
        result = analysts['sentiment'].analyze(market_data)
        print("  >> 情緒分析完成")
        return result

    def run_fundamental():
        print("  >> 基本面分析師開始分析...")
        result = analysts['fundamental'].analyze(market_data, symbol)
        print("  >> 基本面分析完成")
        return result

    def run_news():
        print("  >> 新聞分析師開始分析...")
        result = analysts['news'].analyze(market_data)
        print("  >> 新聞分析完成")
        return result

    # 並行執行所有分析師
    analyst_reports = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        # 提交所有任務
        futures = {
            executor.submit(run_technical): 'technical',
            executor.submit(run_sentiment): 'sentiment',
            executor.submit(run_fundamental): 'fundamental',
            executor.submit(run_news): 'news'
        }

        # 收集結果（保持順序）
        results = {}
        for future in as_completed(futures):
            analyst_type = futures[future]
            try:
                results[analyst_type] = future.result()
            except Exception as e:
                print(f"  >> {analyst_type} 分析失敗: {e}")
                # 使用降級策略：創建一個默認報告
                from models import AnalystReport
                # Ensure the summary has at least 50 characters to meet validation requirements
                default_summary = f"{analyst_type}分析暫時無法完成，使用默認評估。由於技術問題，本次分析採用保守策略。這是一個預設的安全評估，建議結合其他分析師的意見進行綜合判斷。"
                results[analyst_type] = AnalystReport(
                    analyst_type=f"{analyst_type}分析師",
                    summary=default_summary,
                    key_findings=[f"{analyst_type}分析遇到技術問題"],
                    bullish_points=["數據暫時無法獲取"],
                    bearish_points=["建議謹慎操作"],
                    confidence=50.0
                )

        # 按原始順序組裝報告
        analyst_reports = [
            results.get('technical'),
            results.get('sentiment'),
            results.get('fundamental'),
            results.get('news')
        ]

    print(">> 所有分析師報告完成")
    return {"analyst_reports": analyst_reports}

def research_debate_node(state: AgentState) -> Dict:
    """
    節點 3: 研究團隊進行多空辯論。
    實現多輪互動辯論機制，讓多空雙方真正互相討論。
    支持委員會模式：多個模型組成委員會，先內部討論再辯論。
    """
    from utils.settings import Settings
    from core.config import (
        ENABLE_COMMITTEE_MODE,
        BULL_COMMITTEE_MODELS,
        BEAR_COMMITTEE_MODELS,
        SYNTHESIS_MODEL,
        BULL_RESEARCHER_MODEL,
        BEAR_RESEARCHER_MODEL
    )
    from utils.llm_client import create_llm_client_from_config

    debate_rounds = Settings.DEBATE_ROUNDS
    analyst_reports = state['analyst_reports']
    client = state['client']

    # 檢查是否啟用委員會模式
    if ENABLE_COMMITTEE_MODE:
        print(f"\n[節點 3/7] 研究團隊 (委員會模式 + {debate_rounds}輪辯論)...")
        print(f"  >> 多頭委員會: {len(BULL_COMMITTEE_MODELS)} 個模型")
        print(f"  >> 空頭委員會: {len(BEAR_COMMITTEE_MODELS)} 個模型")

        # === 多頭委員會討論 ===
        print(f"\n  >> 多頭委員會內部討論...")
        bull_committee_args = []
        for i, model_config in enumerate(BULL_COMMITTEE_MODELS, 1):
            print(f"     成員 {i}: {model_config['provider']}:{model_config['model']}")
            member_client, member_model = create_llm_client_from_config(model_config)
            researcher = BullResearcher(member_client, member_model)
            arg = researcher.debate(analyst_reports)
            bull_committee_args.append(arg)
            print(f"        >> 信心度: {arg.confidence}%")

        # 綜合多頭委員會觀點
        print(f"\n  >> 綜合多頭委員會觀點...")
        synthesis_client, synthesis_model = create_llm_client_from_config(SYNTHESIS_MODEL)
        synthesizer = CommitteeSynthesizer(synthesis_client, synthesis_model)
        bull_argument = synthesizer.synthesize_committee_views('Bull', bull_committee_args, analyst_reports)
        print(f"     >> 多頭委員會綜合觀點 (信心度: {bull_argument.confidence}%)")

        # === 空頭委員會討論 ===
        print(f"\n  >> 空頭委員會內部討論...")
        bear_committee_args = []
        for i, model_config in enumerate(BEAR_COMMITTEE_MODELS, 1):
            print(f"     成員 {i}: {model_config['provider']}:{model_config['model']}")
            member_client, member_model = create_llm_client_from_config(model_config)
            researcher = BearResearcher(member_client, member_model)
            arg = researcher.debate(analyst_reports)
            bear_committee_args.append(arg)
            print(f"        >> 信心度: {arg.confidence}%")

        # 綜合空頭委員會觀點
        print(f"\n  >> 綜合空頭委員會觀點...")
        bear_argument = synthesizer.synthesize_committee_views('Bear', bear_committee_args, analyst_reports)
        print(f"     >> 空頭委員會綜合觀點 (信心度: {bear_argument.confidence}%)")

        # 如果啟用多輪辯論，使用綜合觀點進行辯論
        if debate_rounds > 1:
            print(f"\n  >> 委員會綜合觀點進行 {debate_rounds-1} 輪辯論...")
            # 創建研究員進行後續辯論
            bull_client, bull_model = create_llm_client_from_config(SYNTHESIS_MODEL)
            bear_client, bear_model = create_llm_client_from_config(SYNTHESIS_MODEL)
            bull_researcher = BullResearcher(bull_client, bull_model)
            bear_researcher = BearResearcher(bear_client, bear_model)

            # 從第2輪開始辯論（第1輪已經是委員會綜合）
            for round_num in range(2, debate_rounds + 1):
                print(f"\n  >> 第 {round_num}/{debate_rounds} 輪辯論...")

                bull_argument = bull_researcher.debate(
                    analyst_reports=analyst_reports,
                    opponent_argument=bear_argument,
                    round_number=round_num
                )
                print(f"     >> 多頭信心度: {bull_argument.confidence}%")

                bear_argument = bear_researcher.debate(
                    analyst_reports=analyst_reports,
                    opponent_argument=bull_argument,
                    round_number=round_num
                )
                print(f"     >> 空頭信心度: {bear_argument.confidence}%")

    else:
        # === 單一模型辯論模式 ===
        print(f"\n[節點 3/7] 研究團隊 (多空辯論 - {debate_rounds}輪互動)...")

        # 創建多空研究員
        bull_client, bull_model = create_llm_client_from_config(BULL_RESEARCHER_MODEL)
        bear_client, bear_model = create_llm_client_from_config(BEAR_RESEARCHER_MODEL)
        bull_researcher = BullResearcher(bull_client, bull_model)
        bear_researcher = BearResearcher(bear_client, bear_model)

        # 進行多輪辯論
        bull_argument = None
        bear_argument = None

        for round_num in range(1, debate_rounds + 1):
            print(f"\n{'=' * 80}")
            print(f"  >> 第 {round_num}/{debate_rounds} 輪辯論")
            print(f"{'=' * 80}")

            # 多頭發言（如果不是第一輪，會看到空頭上一輪的觀點）
            print(f"\n  >> 多頭研究員發言...")
            if bear_argument:
                print(f"     >> 多頭看到了空頭上一輪的觀點：")
                print(f"        空頭論點摘要: {bear_argument.argument[:150]}...")
                print(f"        空頭信心度: {bear_argument.confidence}%")

            bull_argument = bull_researcher.debate(
                analyst_reports=analyst_reports,
                opponent_argument=bear_argument,  # 傳入空頭的上一輪觀點
                round_number=round_num
            )

            print(f"\n  >> 多頭研究員觀點 (第 {round_num} 輪)：")
            print(f"     信心度: {bull_argument.confidence}%")
            print(f"     完整論點: {bull_argument.argument}")
            print(f"     關鍵看漲點:")
            for i, point in enumerate(bull_argument.key_points, 1):
                print(f"       {i}. {point}")
            if bull_argument.counter_arguments:
                print(f"     對空頭的反駁:")
                for i, counter in enumerate(bull_argument.counter_arguments, 1):
                    print(f"       {i}. {counter}")
            print()

            # 空頭發言（看到多頭本輪的觀點）
            print(f"  >> 空頭研究員發言...")
            print(f"     >> 空頭看到了多頭本輪的觀點：")
            print(f"        多頭論點摘要: {bull_argument.argument[:150]}...")
            print(f"        多頭信心度: {bull_argument.confidence}%")

            bear_argument = bear_researcher.debate(
                analyst_reports=analyst_reports,
                opponent_argument=bull_argument,  # 傳入多頭的本輪觀點
                round_number=round_num
            )

            print(f"\n  >> 空頭研究員觀點 (第 {round_num} 輪)：")
            print(f"     信心度: {bear_argument.confidence}%")
            print(f"     完整論點: {bear_argument.argument}")
            print(f"     關鍵看跌點:")
            for i, point in enumerate(bear_argument.key_points, 1):
                print(f"       {i}. {point}")
            if bear_argument.counter_arguments:
                print(f"     對多頭的反駁:")
                for i, counter in enumerate(bear_argument.counter_arguments, 1):
                    print(f"       {i}. {counter}")
            print()

    # 辯論總結
    print(f"\n{'=' * 80}")
    print(f"  >> 辯論總結")
    print(f"{'=' * 80}")
    print(f"\n  >> 多頭最終觀點:")
    print(f"     信心度: {bull_argument.confidence}%")
    print(f"     核心論點: {bull_argument.argument[:200]}...")
    print(f"\n  >> 空頭最終觀點:")
    print(f"     信心度: {bear_argument.confidence}%")
    print(f"     核心論點: {bear_argument.argument[:200]}...")

    confidence_diff = abs(bull_argument.confidence - bear_argument.confidence)
    if bull_argument.confidence > bear_argument.confidence:
        print(f"\n  >> 辯論結果: 多頭觀點較強 (信心度差距: {confidence_diff:.1f}%)")
    elif bear_argument.confidence > bull_argument.confidence:
        print(f"\n  >> 辯論結果: 空頭觀點較強 (信心度差距: {confidence_diff:.1f}%)")
    else:
        print(f"\n  >> 辯論結果: 雙方勢均力敵")

    print(f"\n>> {debate_rounds}輪辯論完成")
    print(f"{'=' * 80}\n")

    return {"bull_argument": bull_argument, "bear_argument": bear_argument}

def trader_decision_node(state: AgentState) -> Dict:
    """
    節點 4: 交易員綜合所有資訊做出決策。(可能被回饋)
    """
    print("\n[節點 4/7] 交易員 (綜合決策)...")
    
    replan_count = state.get('replan_count', 0)
    feedback = state.get('risk_assessment')

    if feedback:
        print(f"  - ⚠️ 收到風險管理員回饋，正在重新規劃 (第 {replan_count + 1} 次)...")
    
    trader = Trader(state['client'])
    trader_decision = trader.make_decision(
        analyst_reports=state['analyst_reports'],
        bull_argument=state['bull_argument'],
        bear_argument=state['bear_argument'],
        current_price=state['current_price'],
        market_data=state['market_data'],
        market_type=state['market_data']['market_type'],
        leverage=state['market_data']['leverage'],
        feedback=feedback # 將回饋傳遞給 Trader
    )
    
    print(f">> 交易決策完成 | 決策: {trader_decision.decision}")
    return {"trader_decision": trader_decision, "replan_count": replan_count + 1}

def risk_management_node(state: AgentState) -> Dict:
    """
    節點 5: 風險經理評估交易風險。
    """
    print("\n[節點 5/7] 風險管理 (風險評估)...")
    
    risk_manager = RiskManager(state['client'])
    risk_assessment = risk_manager.assess(
        trader_decision=state['trader_decision'],
        market_data=state['market_data'],
        market_type=state['market_data']['market_type'],
        leverage=state['market_data']['leverage']
    )
    
    print(f">> 風險評估完成 | 風險等級: {risk_assessment.risk_level} | 批准: {'是' if risk_assessment.approve else '否'}")
    return {"risk_assessment": risk_assessment}

def after_risk_management_router(state: AgentState) -> str:
    """
    路由節點: 在風險評估後，決定下一步。
    """
    print("\n[節點 6/7] 進行路由決策...")
    
    if state['risk_assessment'].approve:
        print("  - >> 風險評估已批准。流程繼續至基金經理。")
        return "proceed_to_fund_manager"
    else:
        if state['replan_count'] >= MAX_REPLANS:
            print("  - >> 已達重新規劃次數上限。即使被拒絕，也將流程交給基金經理做最終決定。")
            return "proceed_to_fund_manager"
        else:
            print("  - >> 風險評估未批准。流程返回交易員節點進行重新規劃。")
            return "replan_with_trader"

def fund_manager_approval_node(state: AgentState) -> Dict:
    """
    節點 7: 基金經理最終審批。
    """
    print("\n[節點 7/7] 基金經理 (最終審批)...")
    
    fund_manager = FundManager(state['client'])
    final_approval = fund_manager.approve(
        trader_decision=state['trader_decision'],
        risk_assessment=state['risk_assessment'],
        market_type=state['market_data']['market_type'],
        leverage=state['market_data']['leverage']
    )
    
    print(f">> 最終審批完成 | 決定: {final_approval.final_decision}")
    return {"final_approval": final_approval}

# 3. 構建圖 (Graph)
workflow = StateGraph(AgentState)

# 添加節點
workflow.add_node("prepare_data", prepare_data_node)
workflow.add_node("run_analyst_team", analyst_team_node)
workflow.add_node("run_research_debate", research_debate_node)
workflow.add_node("run_trader_decision", trader_decision_node)
workflow.add_node("run_risk_management", risk_management_node)
workflow.add_node("run_fund_manager_approval", fund_manager_approval_node)

# 設置入口點
workflow.set_entry_point("prepare_data")

# 添加邊 (Edges)
workflow.add_edge("prepare_data", "run_analyst_team")
workflow.add_edge("run_analyst_team", "run_research_debate")
workflow.add_edge("run_research_debate", "run_trader_decision")
# 交易員決策後，進入風險管理
workflow.add_edge("run_trader_decision", "run_risk_management")

# 關鍵：添加條件邊
workflow.add_conditional_edges(
    "run_risk_management",
    after_risk_management_router,
    {
        "proceed_to_fund_manager": "run_fund_manager_approval",
        "replan_with_trader": "run_trader_decision", # 返回交易員節點
    }
)

workflow.add_edge("run_fund_manager_approval", END)

# 4. 編譯圖
app = workflow.compile()
print("OK LangGraph 工作流編譯完成 (包含條件式回饋循環)。")
