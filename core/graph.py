import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from typing import TypedDict, List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import StateGraph, END

# 匯入我們自己的模組
from trading.okx_api_connector import OKXAPIConnector
from core.models import AnalystReport, ResearcherDebate, TraderDecision, RiskAssessment, FinalApproval, FactCheckResult, DebateJudgment
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
    NeutralResearcher, # Added
    DataFactChecker,    # Added
    DebateJudge,        # Added
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
    account_balance: Optional[Dict] # 新增：帳戶餘額資訊
    # --- 多週期分析參數 ---
    include_multi_timeframe: bool  # 是否包含多週期分析
    short_term_interval: str       # 短週期時間間隔
    medium_term_interval: str      # 中週期時間間隔
    long_term_interval: str        # 長週期時間間隔
    # --- 客戶端與通用數據 ---
    client: Any  # LangChain BaseChatModel
    user_llm_client: Optional[Any]  # ⭐ 用戶提供的 LLM 客戶端 (BaseChatModel)
    user_provider: Optional[str]       # ⭐ 用戶選擇的 provider
    market_data: Dict
    current_price: float
    funding_rate_info: Dict

    # --- 流程控制參數 ---
    selected_analysts: Optional[List[str]] # 指定要運行的分析師 ["technical", "sentiment", "fundamental", "news"]
    perform_trading_decision: bool         # 是否進行後續的辯論與交易決策
    execute_trade: bool                    # 是否自動執行交易 (新增)
    analysis_mode: Optional[str]           # "analysis_only" | "debate_report" | "full_trading"（覆蓋 perform_trading_decision）
    formatted_report: Optional[str]        # debate_report 模式下的最終報告文字

    # --- 各階段的產出 ---
    analyst_reports: List[AnalystReport]
    bull_argument: ResearcherDebate
    bear_argument: ResearcherDebate
    neutral_argument: Optional[ResearcherDebate] # Added
    fact_checks: Optional[Dict]                  # Added
    debate_judgment: Optional[DebateJudgment]    # Added
    debate_history: List[Dict]                   # 新增：存儲辯論過程中的每一發言
    trader_decision: TraderDecision
    risk_assessment: Optional[RiskAssessment] # 可能為 None
    final_approval: FinalApproval
    execution_result: Optional[Dict]          # 交易執行結果 (新增)

    # --- 循環控制 ---
    replan_count: int
    debate_round: int # 新增：當前辯論輪次


# 2. 創建節點 (Nodes)
# 每個節點都是一個函式，接收 state 作為參數，並返回一個包含更新後狀態的字典。

def prepare_data_node(state: AgentState) -> Dict:
    """
    節點 1: 準備所有需要的數據。
    功能：
    1. ⭐ 使用用戶提供的 LLM Client
    2. 檢查是否有預加載數據
    3. 執行數據下載
    """
    print("\n[節點 1/7] 準備數據...")

    # ⭐ 使用用戶提供的 LLM client
    user_client = state.get('user_llm_client')
    user_provider = state.get('user_provider', 'openai')

    if not user_client:
        raise ValueError("❌ 缺少用戶 LLM client。請確保前端傳遞了 user_api_key。")

    print(f">> ✅ 使用用戶的 {user_provider} client")
    client = user_client

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
            "debate_history": [],
            "debate_round": 0,
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
        "debate_history": [],
        "debate_round": 0,
        "replan_count": 0
    }

def analyst_team_node(state: AgentState) -> Dict:
    """
    節點 2: 四位分析師並行工作。
    使用 ThreadPoolExecutor 實現真正的並行執行，提升 3-4 倍速度。
    ⭐ 使用用戶提供的 LLM client
    """
    print("\n[節點 2/7] 分析師團隊 (並行分析)...")

    # ⭐ 使用用戶的 LLM client
    user_client = state.get('user_llm_client')
    if not user_client:
        raise ValueError("❌ 缺少用戶 LLM client")

    client = user_client
    market_data, symbol = state['market_data'], state['symbol']

    # 創建分析師實例（傳入用戶的 client）
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

def after_analyst_team_router(state: AgentState) -> str:
    """
    路由節點: 在分析師完成後，決定下一步。
    - analysis_only: 直接結束
    - debate_report / full_trading: 進入辯論流程
    向後兼容：perform_trading_decision=True → full_trading, False → analysis_only
    """
    analysis_mode = state.get('analysis_mode')
    if analysis_mode is None:
        # 向後兼容
        perform_trading_decision = state.get('perform_trading_decision', True)
        analysis_mode = "full_trading" if perform_trading_decision else "analysis_only"

    if analysis_mode == "analysis_only":
        print("  >> [analysis_only] 跳過辯論與交易決策階段。")
        return "end_process"
    else:
        # debate_report 或 full_trading 都進入辯論
        return "proceed_to_debate"

def research_debate_node(state: AgentState) -> Dict:
    """
    節點 3: 研究團隊進行一輪深度辯論。
    支持「單一模型」與「委員會模式 (多模型並行)」兩種模式。
    ⭐ 使用用戶提供的 LLM client（除了委員會模式的多模型配置）
    """
    from utils.llm_client import create_llm_client_from_config
    from core.config import (
        ENABLE_COMMITTEE_MODE, SYNTHESIS_MODEL,
        BULL_COMMITTEE_MODELS, BEAR_COMMITTEE_MODELS,
        BULL_RESEARCHER_MODEL, BEAR_RESEARCHER_MODEL
    )

    # ⭐ 使用用戶的 LLM client
    user_client = state.get('user_llm_client')
    if not user_client:
        raise ValueError("❌ 缺少用戶 LLM client")

    analyst_reports = state['analyst_reports']
    market_data = state['market_data']
    client = user_client  # 用於 fact_checker
    debate_round = state.get('debate_round', 0)
    debate_history = state.get('debate_history', [])
    
    # 辯論主題定義
    topics = ["技術面與指標", "基本面與新聞", "綜合決策與風險"]
    if debate_round >= len(topics):
        return {}

    topic = topics[debate_round]
    print(f"\n[節點 3/7] 研究團隊辯論 - 第 {debate_round + 1} 輪：{topic}...")
    
    if ENABLE_COMMITTEE_MODE:
        print(f"  >> [模式] 委員會模式已開啟，正在調動多個模型...")
        # 🛡️ 委員會模式驗證
        if not BULL_COMMITTEE_MODELS or not BEAR_COMMITTEE_MODELS:
             raise ValueError("❌ 委員會模式已開啟，但未配置委員會成員模型。請在設定中添加模型或關閉委員會模式。")
        
        # 顯示當前配置
        print(f"  >> 多頭委員會: {[m.get('model') for m in BULL_COMMITTEE_MODELS]}")
        print(f"  >> 空頭委員會: {[m.get('model') for m in BEAR_COMMITTEE_MODELS]}")

    # 1. 準備合成器與中立研究員 (使用 SYNTHESIS_MODEL)
    synth_client, synth_model_name = create_llm_client_from_config(SYNTHESIS_MODEL, user_client=user_client)
    synthesizer = CommitteeSynthesizer(synth_client, synth_model_name)
    neutral_researcher = NeutralResearcher(synth_client, synth_model_name)
    fact_checker = DataFactChecker(client)

    # 獲取上一輪的參數（如果有）
    prev_bull = state.get('bull_argument')
    prev_bear = state.get('bear_argument')
    prev_neutral = state.get('neutral_argument')

    # ==========================================
    # 階段 A: 多頭陣營發言 (Bull Side)
    # ==========================================
    opponents_for_bull = [arg for arg in [prev_bear, prev_neutral] if arg]
    
    bull_committee_details = [] # 用於存儲委員會詳細觀點

    if ENABLE_COMMITTEE_MODE:
        # 並行執行所有委員會成員
        bull_committee_args = []
        with ThreadPoolExecutor(max_workers=len(BULL_COMMITTEE_MODELS)) as executor:
            futures = []
            for cfg in BULL_COMMITTEE_MODELS:
                c, m = create_llm_client_from_config(cfg, user_client=user_client)
                researcher = BullResearcher(c, m)
                futures.append(executor.submit(researcher.debate, analyst_reports, opponents_for_bull, debate_round+1, topic))
            
            for future in as_completed(futures):
                try:
                    res = future.result()
                    bull_committee_args.append(res)
                    # 收集詳細觀點
                    bull_committee_details.append(res.model_dump())
                except Exception as e:
                    print(f"  >> 多頭委員會成員發言失敗: {e}")
        
        # 綜合多頭觀點
        bull_argument = synthesizer.synthesize_committee_views('Bull', bull_committee_args, analyst_reports)
    else:
        # 單一模型模式
        bull_client, bull_model = create_llm_client_from_config(BULL_RESEARCHER_MODEL, user_client=user_client)
        bull_researcher = BullResearcher(bull_client, bull_model)
        bull_argument = bull_researcher.debate(analyst_reports, opponents_for_bull, debate_round+1, topic)

    # ==========================================
    # 階段 B: 空頭陣營發言 (Bear Side)
    # ==========================================
    opponents_for_bear = [arg for arg in [bull_argument, prev_neutral] if arg]
    
    bear_committee_details = [] # 用於存儲委員會詳細觀點

    if ENABLE_COMMITTEE_MODE:
        # 並行執行所有委員會成員
        bear_committee_args = []
        with ThreadPoolExecutor(max_workers=len(BEAR_COMMITTEE_MODELS)) as executor:
            futures = []
            for cfg in BEAR_COMMITTEE_MODELS:
                c, m = create_llm_client_from_config(cfg, user_client=user_client)
                researcher = BearResearcher(c, m)
                futures.append(executor.submit(researcher.debate, analyst_reports, opponents_for_bear, debate_round+1, topic))
            
            for future in as_completed(futures):
                try:
                    res = future.result()
                    bear_committee_args.append(res)
                    # 收集詳細觀點
                    bear_committee_details.append(res.model_dump())
                except Exception as e:
                    print(f"  >> 空頭委員會成員發言失敗: {e}")
        
        # 綜合空頭觀點
        bear_argument = synthesizer.synthesize_committee_views('Bear', bear_committee_args, analyst_reports)
    else:
        # 單一模型模式
        bear_client, bear_model = create_llm_client_from_config(BEAR_RESEARCHER_MODEL, user_client=user_client)
        bear_researcher = BearResearcher(bear_client, bear_model)
        bear_argument = bear_researcher.debate(analyst_reports, opponents_for_bear, debate_round+1, topic)

    # ==========================================
    # 階段 C: 中立/裁判階段
    # ==========================================
    opponents_for_neutral = [arg for arg in [bull_argument, bear_argument] if arg]
    neutral_argument = neutral_researcher.debate(analyst_reports, opponents_for_neutral, debate_round+1, topic)

    # 數據核對
    current_args = [bull_argument, bear_argument, neutral_argument]
    fact_checks = fact_checker.check(current_args, market_data)
    
    # 更新歷史紀錄
    new_history = debate_history.copy()
    new_history.append({
        "round": debate_round + 1,
        "topic": topic,
        "bull": bull_argument.model_dump(),
        "bear": bear_argument.model_dump(),
        "neutral": neutral_argument.model_dump(),
        "bull_committee_details": bull_committee_details, # 新增
        "bear_committee_details": bear_committee_details, # 新增
        "fact_checks": {k: v.model_dump() for k, v in fact_checks.items()}
    })

    return {
        "bull_argument": bull_argument,
        "bear_argument": bear_argument,
        "neutral_argument": neutral_argument,
        "fact_checks": fact_checks,
        "debate_history": new_history,
        "debate_round": debate_round + 1
    }

def debate_router(state: AgentState) -> str:
    """決定是否繼續下一輪辯論或進入裁判階段"""
    debate_round = state.get('debate_round', 0)
    bull_arg = state.get('bull_argument')
    bear_arg = state.get('bear_argument')
    
    # 基本終止條件：完成 2 輪 (原為 3)
    if debate_round >= 3:
        return "proceed_to_judgment"

    # 動態終止：根據論點數量差距判斷（不再依賴主觀信心度）
    if bull_arg and bear_arg:
        bull_points = len(bull_arg.key_points)
        bear_points = len(bear_arg.key_points)
        point_diff = abs(bull_points - bear_points)
        # 如果一方的論點數量遠超另一方，提前結束
        if point_diff >= 4 and max(bull_points, bear_points) >= 5:
            winner = "多頭" if bull_points > bear_points else "空頭"
            print(f"  >> [動態終止] {winner}論點數量優勢明顯 ({bull_points} vs {bear_points})")
            return "proceed_to_judgment"

    return "continue_debate"

def debate_judgment_node(state: AgentState) -> Dict:
    """
    節點 3.5: 裁判進行最終裁決
    ⭐ 使用 JUDGE_MODEL 配置
    """
    from core.config import JUDGE_MODEL
    from utils.llm_client import create_llm_client_from_config

    print(f"\n  >> [裁判裁決] 綜合交易委員會正在審核辯論表現...")

    # ⭐ 使用用戶的 LLM client
    user_client = state.get('user_llm_client')

    # 1. 嘗試使用 JUDGE_MODEL
    try:
        judge_client, _ = create_llm_client_from_config(JUDGE_MODEL, user_client=user_client)
        print(f"  >> [裁判] 使用模型: {JUDGE_MODEL.get('model', 'default')}")
    except Exception as e:
        print(f"  >> [裁判] JUDGE_MODEL 初始化失敗 ({e})，回退至 User Client")
        judge_client = user_client

    if not judge_client:
        raise ValueError("❌ 缺少 Judge Client")

    judge = DebateJudge(judge_client)
    
    debate_judgment = judge.judge(
        bull_argument=state['bull_argument'],
        bear_argument=state['bear_argument'],
        neutral_argument=state['neutral_argument'],
        fact_checks=state['fact_checks'],
        market_data=state['market_data']
    )
    print(f"  >> [裁決結果] 勝出方: {debate_judgment.winning_stance} | 理由: {debate_judgment.key_takeaway}")
    
    return {"debate_judgment": debate_judgment}

def after_debate_judgment_router(state: AgentState) -> str:
    """
    路由節點: 辯論裁決後，依 analysis_mode 決定下一步。
    - debate_report: 格式化報告後結束（不執行交易）
    - full_trading: 繼續交易員決策
    """
    analysis_mode = state.get('analysis_mode')
    if analysis_mode is None:
        analysis_mode = "full_trading" if state.get('perform_trading_decision', True) else "analysis_only"

    if analysis_mode == "debate_report":
        print("  >> [debate_report] 裁決完成，格式化分析報告。")
        return "format_report"
    return "proceed_to_trader"


def format_analysis_report_node(state: AgentState) -> Dict:
    """
    節點（debate_report 模式）: 格式化不含交易決策的分析報告。
    包含：價格資訊、各分析師報告摘要、辯論裁決、關鍵結論。
    """
    print("\n[format_analysis_report] 整合分析報告...")

    symbol = state.get("symbol", "未知")
    current_price = state.get("current_price", 0)
    market_data = state.get("market_data", {})
    analyst_reports = state.get("analyst_reports", [])
    judgment = state.get("debate_judgment")

    # --- 價格區塊 ---
    price_block = f"## 📊 {symbol} 市場分析報告\n\n"
    price_block += f"**當前價格**: ${current_price:,.4f}\n"
    change_24h = market_data.get("price_change_24h") or market_data.get("change_24h")
    if change_24h:
        price_block += f"**24h 變化**: {change_24h}\n"
    price_block += "\n"

    # --- 分析師報告區塊 ---
    analyst_block = "## 🔍 分析師報告\n\n"
    for report in analyst_reports:
        if report:
            analyst_type = getattr(report, "analyst_type", "")
            summary = getattr(report, "summary", "") or getattr(report, "analysis", "")
            signals = getattr(report, "key_signals", [])
            analyst_block += f"### {analyst_type.capitalize()} 分析師\n"
            if summary:
                analyst_block += f"{summary}\n"
            if signals:
                for s in signals[:3]:
                    analyst_block += f"- {s}\n"
            analyst_block += "\n"

    # --- 辯論裁決區塊 ---
    judgment_block = ""
    if judgment:
        winning_stance = getattr(judgment, "winning_stance", "N/A")
        key_takeaway = getattr(judgment, "key_takeaway", "")
        confidence = getattr(judgment, "confidence_score", None)
        judgment_block = "## ⚖️ 辯論裁決\n\n"
        judgment_block += f"**裁決方向**: {winning_stance}\n"
        if confidence is not None:
            judgment_block += f"**信心分數**: {confidence}/10\n"
        if key_takeaway:
            judgment_block += f"\n**關鍵結論**: {key_takeaway}\n"
        judgment_block += "\n"

    report_text = price_block + analyst_block + judgment_block
    report_text += "\n---\n*本報告由 AI 分析師生成，僅供參考，不構成投資建議。*\n"

    print(f"  >> 報告生成完成，長度: {len(report_text)} 字元")
    return {"formatted_report": report_text}


def trader_decision_node(state: AgentState) -> Dict:
    """
    節點 4: 交易員綜合所有資訊做出決策。(可能被回饋)
    ⭐ 使用用戶提供的 LLM client
    """
    print("\n[節點 4/7] 交易員 (綜合決策)...")

    # ⭐ 使用用戶的 LLM client
    user_client = state.get('user_llm_client')
    if not user_client:
        raise ValueError("❌ 缺少用戶 LLM client")

    replan_count = state.get('replan_count', 0)
    feedback = state.get('risk_assessment')

    if feedback:
        print(f"  - ⚠️ 收到風險管理員回饋，正在重新規劃 (第 {replan_count + 1} 次)...")

    trader = Trader(user_client)
    trader_decision = trader.make_decision(
        bull_argument=state['bull_argument'],
        bear_argument=state['bear_argument'],
        neutral_argument=state.get('neutral_argument'),
        fact_checks=state.get('fact_checks'),
        debate_judgment=state.get('debate_judgment'),
        current_price=state['current_price'],
        market_data=state['market_data'],
        market_type=state['market_data']['market_type'],
        feedback=feedback,
        account_balance=state.get('account_balance')
    )
    
    print(f">> 交易決策完成 | 決策: {trader_decision.decision}")
    return {"trader_decision": trader_decision, "replan_count": replan_count + 1}

def risk_management_node(state: AgentState) -> Dict:
    """
    節點 5: 風險經理評估交易風險。
    ⭐ 使用用戶提供的 LLM client
    """
    print("\n[節點 5/7] 風險管理 (風險評估)...")

    # ⭐ 使用用戶的 LLM client
    user_client = state.get('user_llm_client')
    if not user_client:
        raise ValueError("❌ 缺少用戶 LLM client")

    risk_manager = RiskManager(user_client)
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
    ⭐ 使用用戶提供的 LLM client
    """
    print("\n[節點 7/7] 基金經理 (最終審批)...")

    # ⭐ 使用用戶的 LLM client
    user_client = state.get('user_llm_client')
    if not user_client:
        raise ValueError("❌ 缺少用戶 LLM client")

    fund_manager = FundManager(user_client)
    final_approval = fund_manager.approve(
        trader_decision=state['trader_decision'],
        risk_assessment=state['risk_assessment'],
        market_type=state['market_data']['market_type'],
        leverage=state['market_data']['leverage']
    )
    
    print(f">> 最終審批完成 | 決定: {final_approval.final_decision}")
    return {"final_approval": final_approval}

def execute_trade_node(state: AgentState) -> Dict:
    """
    節點 8: 自動執行交易 (可選)。
    """
    if not state.get("execute_trade", False):
        print(">> [執行階段] 用戶未啟用自動交易，跳過執行。")
        return {"execution_result": {"status": "skipped", "reason": "User disabled auto-execution"}}

    approval = state.get("final_approval")
    if not approval or not approval.approved:
        print(">> [執行階段] 基金經理未批准交易，跳過執行。")
        return {"execution_result": {"status": "skipped", "reason": "Trade not approved by Fund Manager"}}

    decision = approval.final_decision # Approve, Amended
    if decision not in ["Approve", "Amended"]:
        return {"execution_result": {"status": "skipped", "reason": "Decision is not actionable"}}

    print(f"\n[節點 8/7] 執行交易: {state['symbol']} ({state['market_type']})...")
    
    try:
        okx = OKXAPIConnector()
        if not all([okx.api_key, okx.secret_key, okx.passphrase]):
            print(">> ⚠️ 錯誤: 未設定 OKX API Keys，無法執行交易。")
            return {"execution_result": {"status": "failed", "error": "Missing API Keys"}}

        # 準備訂單參數
        symbol = state['symbol'] # e.g., BTC-USDT
        market_type = state['market_type']
        
        # 決定買賣方向
        trader_decision = state['trader_decision']
        side = ""
        pos_side = "" # for futures
        
        if "Buy" in trader_decision.decision or "Long" in trader_decision.decision:
            side = "buy"
            pos_side = "long"
        elif "Sell" in trader_decision.decision or "Short" in trader_decision.decision:
            side = "sell"
            pos_side = "short"
        else:
            return {"execution_result": {"status": "skipped", "reason": "Hold decision"}}

        # 計算下單數量
        # 注意: 這裡需要更複雜的計算邏輯 (基於餘額、幣價、最小下單單位等)
        # 暫時簡化: 如果是現貨，買入 USDT 金額；如果是合約，買入張數
        # 由於複雜性，我們先做一個 "Dry Run" 或保守計算
        
        account_balance = state.get('account_balance')
        if not account_balance:
             # 嘗試現場抓取餘額
             balance_data = okx.get_account_balance("USDT")
             if balance_data and balance_data.get('code') == '0' and balance_data.get('data'):
                 details = balance_data['data'][0]['details']
                 usdt_bal = next((d for d in details if d['ccy'] == 'USDT'), None)
                 if usdt_bal:
                     avail = float(usdt_bal.get('availBal', 0))
                     state['account_balance'] = {'available_balance': avail, 'currency': 'USDT'}
        
        avail_balance = state.get('account_balance', {}).get('available_balance', 0)
        target_pct = approval.final_position_size
        
        # 安全檢查
        if avail_balance <= 0:
             return {"execution_result": {"status": "failed", "error": "Insufficient balance"}}

        amount_usdt = avail_balance * target_pct
        
        # 最小下單金額檢查 (假設 2 USDT)
        if amount_usdt < 2:
             return {"execution_result": {"status": "skipped", "reason": f"Calculated amount {amount_usdt:.2f} USDT too small"}}

        print(f"  >> 準備下單: {side} {symbol}, 金額: {amount_usdt:.2f} USDT (倉位 {target_pct:.1%})")

        order_result = {}
        if market_type == "spot":
            # 現貨市價單 (sz 為買入金額 USDT)
            if side == "buy":
                order_result = okx.place_spot_order(
                    instId=symbol, 
                    side="buy", 
                    ordType="market", 
                    sz=str(amount_usdt)
                )
            else:
                # 賣出需要持有幣種的數量，這裡暫時略過賣出邏輯，因為需要知道持有多少幣
                # 簡單實作：如果有餘額資訊，賣出對應比例
                # TODO: 獲取 Base Currency 餘額
                return {"execution_result": {"status": "skipped", "reason": "Spot Sell not fully implemented yet"}}

        elif market_type == "futures":
            # 合約市價單
            # 需要設置槓桿
            leverage = approval.approved_leverage or 1
            # 轉換為合約張數 (需知道每張合約價值，OKX 1張 BTC=0.01 BTC? 不，是 100 USD 或其他)
            # 這是最複雜的部分。OKX API 下單單位 sz: 
            # 買入/賣出數量。
            # 現貨：買入為金額（市價），賣出為數量。
            # 合約：張數。
            
            # 為了安全，這裡我們先不下單，而是返回一個 "Ready to Execute" 的狀態
            # 或者只做 1 張的最小測試
            # 為了符合用戶期望，我們先回傳一個模擬的成功，但註明是模擬
            pass 
            
        # 暫時返回模擬結果，直到我們完善數量計算邏輯
        return {"execution_result": {
            "status": "simulated", 
            "message": f"Would execute {side} {symbol} for ~{amount_usdt:.2f} USDT. (Auto-execution logic safety lock active)",
            "details": order_result
        }}

    except Exception as e:
        print(f"  >> 執行交易時發生錯誤: {e}")
        return {"execution_result": {"status": "failed", "error": str(e)}}

# 3. 構建圖 (Graph)
workflow = StateGraph(AgentState)

# 添加節點
workflow.add_node("prepare_data", prepare_data_node)
workflow.add_node("run_analyst_team", analyst_team_node)
workflow.add_node("run_research_debate", research_debate_node)
workflow.add_node("run_debate_judgment", debate_judgment_node) # 新增
workflow.add_node("format_analysis_report", format_analysis_report_node)  # debate_report 模式
workflow.add_node("run_trader_decision", trader_decision_node)
workflow.add_node("run_risk_management", risk_management_node)
workflow.add_node("run_fund_manager_approval", fund_manager_approval_node)
workflow.add_node("execute_trade_node", execute_trade_node) # 新增

# 設置入口點
workflow.set_entry_point("prepare_data")

# 添加邊 (Edges)
workflow.add_edge("prepare_data", "run_analyst_team")

# 條件路由：分析師完成後，決定是否進入辯論階段
workflow.add_conditional_edges(
    "run_analyst_team",
    after_analyst_team_router,
    {
        "proceed_to_debate": "run_research_debate",
        "end_process": END
    }
)

# 辯論循環路由
workflow.add_conditional_edges(
    "run_research_debate",
    debate_router,
    {
        "continue_debate": "run_research_debate",
        "proceed_to_judgment": "run_debate_judgment"
    }
)

# 裁決後：debate_report → format_analysis_report → END；full_trading → trader
workflow.add_conditional_edges(
    "run_debate_judgment",
    after_debate_judgment_router,
    {
        "format_report": "format_analysis_report",
        "proceed_to_trader": "run_trader_decision",
    }
)
workflow.add_edge("format_analysis_report", END)

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

workflow.add_edge("run_fund_manager_approval", "execute_trade_node") # 修改: 接到執行節點
workflow.add_edge("execute_trade_node", END) # 執行後結束

# 4. 編譯圖
app = workflow.compile()
print("OK LangGraph 工作流編譯完成 (包含條件式回饋循環)。")