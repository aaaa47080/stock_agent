import pandas as pd
import numpy as np
from indicator_calculator import add_technical_indicators
from data_fetcher import get_historical_klines
import os
import json
import openai
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Optional
from datetime import datetime
from enum import Enum
import requests


# === AI 模型配置 ===
FAST_THINKING_MODEL = "gpt-4o"  # 用於數據收集和快速分析
DEEP_THINKING_MODEL = "o4-mini"  # 用於深度推理和決策



def get_crypto_news(symbol: str = "BTC", limit: int = 5):
    """
    從 CryptoPanic 獲取指定幣種的最新新聞
    需先申請 API Key: https://cryptopanic.com/developers/api/
    """
    # 請替換為你的 CryptoPanic API Token
    API_TOKEN = os.getenv("API_TOKEN", "")
    
    if API_TOKEN == "":
        print("⚠️ 警告：未設定 CryptoPanic API Token，無法獲取真實新聞")
        return []

    print(f"📰 正在從 CryptoPanic 撈取 {symbol} 的真實新聞...")
    
    # CryptoPanic API 請求
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        "auth_token": API_TOKEN,
        "currencies": symbol,
        "filter": "important",  # 只抓取重要新聞
        "kind": "news",         # 排除媒體影片，只抓新聞
        "public": "true"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        print("=====================================")
        print(response.content)
        print("=====================================")
        data = response.json()
        
        news_list = []
        if "results" in data:
            for item in data["results"][:limit]:
                # 格式化發布時間
                published_at = item["published_at"]
                title = item["title"]
                source = item["domain"]
                url = item["url"] # 新聞連結
                
                # 加入情緒標籤 (如果有)
                sentiment = "中性"
                if "votes" in item:
                    if item["votes"]["positive"] > item["votes"]["negative"]:
                        sentiment = "看漲"
                    elif item["votes"]["negative"] > item["votes"]["positive"]:
                        sentiment = "看跌"

                news_list.append(f"[{published_at}] 【{source}】{title} (社群情緒: {sentiment})")
        
        if not news_list:
            print("⚠️ 未找到相關新聞")
            
        return news_list

    except Exception as e:
        print(f"❌ 獲取新聞失敗: {str(e)}")
        return []

# ============================================================================
# Agent 角色定義
# ============================================================================

class AnalystReport(BaseModel):
    """分析師報告結構"""
    analyst_type: str
    summary: str = Field(..., min_length=50)
    key_findings: List[str]
    bullish_points: List[str] = []
    bearish_points: List[str] = []
    confidence: float = Field(..., ge=0, le=100)


class ResearcherDebate(BaseModel):
    """研究員辯論結構"""
    researcher_stance: Literal['Bull', 'Bear']
    argument: str = Field(..., min_length=100)
    key_points: List[str]
    counter_arguments: List[str] = []
    confidence: float = Field(..., ge=0, le=100)


class TraderDecision(BaseModel):
    """交易員決策結構"""
    decision: Literal['Buy', 'Sell', 'Hold']
    reasoning: str = Field(..., min_length=100)
    position_size: float = Field(..., ge=0, le=1)
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = Field(..., ge=0, le=100)
    synthesis: str = Field(..., min_length=50, description="如何綜合各方意見")


class RiskAssessment(BaseModel):
    """風險評估結構"""
    risk_level: Literal['低風險', '中低風險', '中風險', '中高風險', '高風險', '極高風險']
    assessment: str = Field(..., min_length=50)
    warnings: List[str]
    suggested_adjustments: str
    approve: bool
    adjusted_position_size: float = Field(..., ge=0, le=1)


class FinalApproval(BaseModel):
    """基金經理最終審批"""
    approved: bool
    final_decision: Literal['Execute Buy', 'Execute Sell', 'Hold', 'Reject']
    final_position_size: float = Field(..., ge=0, le=1)
    execution_notes: str
    rationale: str = Field(..., min_length=50)


# ============================================================================
# 第一層：分析師團隊 (Analysts Team)
# ============================================================================

class TechnicalAnalyst:
    """技術分析師 Agent"""
    
    def __init__(self, client):
        self.client = client
        self.role = "技術分析師"
    
    def analyze(self, market_data: Dict) -> AnalystReport:
        """分析技術指標"""
        
        prompt = f"""
你是一位專業的技術分析師，專精於加密貨幣市場的技術指標分析。

你的任務：
1. 分析提供的技術指標數據
2. 識別關鍵的技術信號（趨勢、動量、超買超賣）
3. 提供看漲和看跌的技術論點
4. 給出你的專業判斷

市場數據：
{json.dumps(market_data.get('技術指標', {}), indent=2, ensure_ascii=False)}
價格資訊：
{json.dumps(market_data.get('價格資訊', {}), indent=2, ensure_ascii=False)}

請以 JSON 格式回覆，包含：
- analyst_type: "技術分析師"
- summary: 技術分析摘要 (繁體中文，至少50字)
- key_findings: 關鍵發現列表
- bullish_points: 看漲技術信號列表
- bearish_points: 看跌技術信號列表
- confidence: 信心度 (0-100)
"""
        
        response = self.client.chat.completions.create(
            model=FAST_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        
        return AnalystReport.model_validate(json.loads(response.choices[0].message.content))


class SentimentAnalyst:
    """情緒分析師 Agent"""
    
    def __init__(self, client):
        self.client = client
        self.role = "情緒分析師"
    
    def analyze(self, market_data: Dict) -> AnalystReport:
        """分析市場情緒"""
        
        prompt = f"""
你是一位市場情緒分析專家，專精於解讀市場氛圍和投資者心理。

你的任務：
1. 基於價格走勢和成交量評估市場情緒
2. 識別恐慌或貪婪的跡象
3. 評估市場參與度
4. 判斷情緒對價格的潛在影響

市場數據：
價格變化：{json.dumps(market_data.get('價格資訊', {}), indent=2, ensure_ascii=False)}
市場結構：{json.dumps(market_data.get('市場結構', {}), indent=2, ensure_ascii=False)}

請以 JSON 格式回覆，包含：
- analyst_type: "情緒分析師"
- summary: 情緒分析摘要 (繁體中文)
- key_findings: 關鍵發現
- bullish_points: 正面情緒指標
- bearish_points: 負面情緒指標
- confidence: 信心度 (請填寫 0 到 100 的數字，不要填寫文字)
"""
        
        response = self.client.chat.completions.create(
            model=FAST_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        
        return AnalystReport.model_validate(json.loads(response.choices[0].message.content))


class FundamentalAnalyst:
    """基本面分析師 Agent"""
    
    def __init__(self, client):
        self.client = client
        self.role = "基本面分析師"
    
    def analyze(self, market_data: Dict, symbol: str) -> AnalystReport:
        """分析基本面"""
        
        prompt = f"""
你是一位基本面分析專家，專精於評估加密貨幣的長期價值。

對於 {symbol}，請分析：
1. 長期趨勢和價格定位
2. 市場結構的健康度
3. 關鍵支撐和壓力位
4. 市場成熟度指標

市場數據：
{json.dumps(market_data, indent=2, ensure_ascii=False)}

請以 JSON 格式回覆，嚴格遵守以下數據類型：
- analyst_type: "基本面分析師"
- summary: 基本面分析摘要 (繁體中文)
- key_findings: 關鍵發現列表 (必須是字串 List ["發現1", "發現2"]，不要使用 Key-Value 物件)
- bullish_points: 看漲基本面因素列表 (List[str])
- bearish_points: 看跌基本面因素列表 (List[str])
- confidence: 信心度 (必須是 0 到 100 之間的數字，例如 75，不要寫文字)
"""
        
        response = self.client.chat.completions.create(
            model=FAST_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        
        return AnalystReport.model_validate(json.loads(response.choices[0].message.content))

class NewsAnalyst:
    """新聞分析師 Agent (已升級真實新聞功能)"""
    
    def __init__(self, client):
        self.client = client
        self.role = "新聞分析師"
    
    def analyze(self, market_data: Dict) -> AnalystReport:
        """分析真實市場新聞和事件"""
        
        # 提取真實新聞數據
        real_news = market_data.get('新聞資訊', [])
        
        if not real_news:
            news_context = "目前沒有獲取到最新的真實新聞，請基於市場價格波動進行合理的推測分析。"
        else:
            news_str = "\n".join(real_news)
            news_context = f"以下是從 CryptoPanic 獲取的最新真實市場新聞：\n{news_str}"

        prompt = f"""
你是一位加密貨幣市場新聞分析師。請基於提供的**真實新聞**與**近期價格表現**進行分析。

市場數據：
1. 近期價格表現：
{json.dumps(market_data.get('最近5天歷史', []), indent=2, ensure_ascii=False)}

2. 真實市場新聞快訊：
{news_context}

你的任務：
1. 分析新聞對市場情緒的具體影響 (利多/利空/中性)
2. 判斷市場是否已經反映了這些新聞 (Price-in)
3. 結合價格走勢，預測未來可能的催化劑

請以 JSON 格式回覆，**嚴格遵守以下數據類型** (避免程式報錯)：
- analyst_type: "新聞分析師"
- summary: 新聞影響分析 (繁體中文，至少50字)
- key_findings: 關鍵發現列表 (必須是字串 List ["發現1", "發現2"]，**絕對不要**使用 Key-Value 物件)
- bullish_points: 正面催化劑列表 (List[str])
- bearish_points: 負面風險事件列表 (List[str])
- confidence: 信心度 (必須是 0 到 100 之間的**數字**，例如 65，不要寫文字)
"""
        
        response = self.client.chat.completions.create(
            model=FAST_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        
        return AnalystReport.model_validate(json.loads(response.choices[0].message.content))


# ============================================================================
# 第二層：研究團隊 (Research Team) - 進行辯論
# ============================================================================

class BullResearcher:
    """多頭研究員 Agent"""
    
    def __init__(self, client):
        self.client = client
        self.stance = "Bull"
    
    def debate(self, analyst_reports: List[AnalystReport]) -> ResearcherDebate:
        """基於分析師報告提出看漲論點"""
        
        all_bullish = []
        all_bearish = []
        for report in analyst_reports:
            all_bullish.extend(report.bullish_points)
            all_bearish.extend(report.bearish_points)
        
        prompt = f"""
你是一位多頭研究員，你的任務是尋找和強化看漲論點。

分析師報告摘要：
{json.dumps([{"分析師": r.analyst_type, "摘要": r.summary} for r in analyst_reports], indent=2, ensure_ascii=False)}

所有看漲因素：
{json.dumps(all_bullish, indent=2, ensure_ascii=False)}

所有看跌因素：
{json.dumps(all_bearish, indent=2, ensure_ascii=False)}

你的任務：
1. 綜合看漲論點並強化
2. 解釋為什麼看漲因素更重要
3. 反駁看跌論點
4. 提供具體的買入理由

請以 JSON 格式回覆，嚴格遵守數據類型：
- researcher_stance: "Bull"
- argument: 多頭論點 (繁體中文，至少100字)
- key_points: 關鍵看漲點列表 (必須是字串 List ["點1", "點2"])
- counter_arguments: 對空頭論點的反駁列表 (必須是字串 List ["反駁1", "反駁2"]，絕對不要使用 Key-Value 物件或字典)
- confidence: 信心度 (0-100 的數字)
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return ResearcherDebate.model_validate(json.loads(response.choices[0].message.content))

class BearResearcher:
    """空頭研究員 Agent"""
    
    def __init__(self, client):
        self.client = client
        self.stance = "Bear"
    
    def debate(self, analyst_reports: List[AnalystReport]) -> ResearcherDebate:
        """基於分析師報告提出看跌論點"""
        
        all_bullish = []
        all_bearish = []
        for report in analyst_reports:
            all_bullish.extend(report.bullish_points)
            all_bearish.extend(report.bearish_points)
        
        prompt = f"""
你是一位空頭研究員，你的任務是識別風險和強化看跌論點。

分析師報告摘要：
{json.dumps([{"分析師": r.analyst_type, "摘要": r.summary} for r in analyst_reports], indent=2, ensure_ascii=False)}

所有看漲因素：
{json.dumps(all_bullish, indent=2, ensure_ascii=False)}

所有看跌因素：
{json.dumps(all_bearish, indent=2, ensure_ascii=False)}

你的任務：
1. 綜合看跌論點並強化
2. 指出潛在風險和陷阱
3. 反駁看漲論點
4. 提供具體的風險警告

請以 JSON 格式回覆，嚴格遵守數據類型：
- researcher_stance: "Bear"
- argument: 空頭論點 (繁體中文，至少100字)
- key_points: 關鍵看跌點列表 (必須是字串 List ["點1", "點2"])
- counter_arguments: 對多頭論點的反駁列表 (必須是字串 List ["反駁1", "反駁2"]，絕對不要使用 Key-Value 物件或字典)
- confidence: 信心度 (0-100 的數字)
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return ResearcherDebate.model_validate(json.loads(response.choices[0].message.content))

# ============================================================================
# 第三層：交易員 (Trader)
# ============================================================================

class Trader:
    """交易員 Agent - 綜合所有資訊做出最終決策"""
    
    def __init__(self, client):
        self.client = client
    
    def make_decision(
        self,
        analyst_reports: List[AnalystReport],
        bull_argument: ResearcherDebate,
        bear_argument: ResearcherDebate,
        current_price: float
    ) -> TraderDecision:
        """基於所有資訊做出交易決策"""
        
        prompt = f"""
你是一位經驗豐富的專業交易員，負責做出最終的交易決策。

你已經收到：
1. 四位分析師的詳細報告
2. 多頭研究員的看漲論點
3. 空頭研究員的看跌論點

當前價格：${current_price:.2f}

=== 分析師報告 ===
{json.dumps([{
    "分析師": r.analyst_type,
    "摘要": r.summary,
    "信心度": r.confidence
} for r in analyst_reports], indent=2, ensure_ascii=False)}

=== 多頭論點 ===
論點：{bull_argument.argument}
關鍵點：{json.dumps(bull_argument.key_points, ensure_ascii=False)}
信心度：{bull_argument.confidence}%

=== 空頭論點 ===
論點：{bear_argument.argument}
關鍵點：{json.dumps(bear_argument.key_points, ensure_ascii=False)}
信心度：{bear_argument.confidence}%

你的任務：
1. 綜合評估所有資訊
2. 權衡多空雙方論點
3. 做出理性的交易決策 (Buy/Sell/Hold)
4. 確定合理的倉位大小
5. 設定止損和止盈位置

請以 JSON 格式回覆：
- decision: "Buy" / "Sell" / "Hold"
- reasoning: 決策推理 (繁體中文，至少100字)
- position_size: 建議倉位 (0-1)
- entry_price: 進場價位
- stop_loss: 止損價位
- take_profit: 止盈價位
- confidence: 決策信心度
- synthesis: 如何綜合各方意見 (繁體中文)
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return TraderDecision.model_validate(json.loads(response.choices[0].message.content))


# ============================================================================
# 第四層：風險管理團隊 (Risk Management Team)
# ============================================================================

class RiskManager:
    """風險管理員 Agent"""
    
    def __init__(self, client):
        self.client = client
    
    def assess(
        self,
        trader_decision: TraderDecision,
        market_data: Dict
    ) -> RiskAssessment:
        """評估交易決策的風險"""
        
        prompt = f"""
你是一位風險管理專家，負責評估並控制交易風險。

交易員決策：
- 決策：{trader_decision.decision}
- 倉位：{trader_decision.position_size * 100}%
- 進場價：${trader_decision.entry_price:.2f}
- 止損：${trader_decision.stop_loss:.2f}
- 止盈：${trader_decision.take_profit:.2f}
- 信心度：{trader_decision.confidence}%
- 理由：{trader_decision.reasoning}

市場狀況：
波動率：{market_data.get('市場結構', {}).get('20天波動率_年化', 'N/A')}
成交量比例：{market_data.get('市場結構', {}).get('當前成交量vs平均_比例', 'N/A')}

你的任務：
1. 評估這筆交易的風險等級
2. 檢查倉位是否合理
3. 確認止損止盈設置
4. 提供風險警告
5. 建議調整 (如果需要)
6. 決定是否批准

請以 JSON 格式回覆：
- risk_level: "低風險"/"中低風險"/"中風險"/"中高風險"/"高風險"/"極高風險"
- assessment: 風險評估 (繁體中文，至少50字)
- warnings: 風險警告列表
- suggested_adjustments: 建議調整 (繁體中文)
- approve: true/false (是否批准)
- adjusted_position_size: 調整後的倉位 (0-1)
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return RiskAssessment.model_validate(json.loads(response.choices[0].message.content))


# ============================================================================
# 第五層：基金經理 (Fund Manager)
# ============================================================================

class FundManager:
    """基金經理 Agent - 最終審批者"""
    
    def __init__(self, client):
        self.client = client
    
    def approve(
        self,
        trader_decision: TraderDecision,
        risk_assessment: RiskAssessment
    ) -> FinalApproval:
        """最終審批交易"""
        
        prompt = f"""
你是基金經理，負責最終審批所有交易決策。

交易員決策：
- 決策：{trader_decision.decision}
- 倉位：{trader_decision.position_size * 100}%
- 信心度：{trader_decision.confidence}%

風險評估：
- 風險等級：{risk_assessment.risk_level}
- 風險經理批准：{"是" if risk_assessment.approve else "否"}
- 調整後倉位：{risk_assessment.adjusted_position_size * 100}%
- 風險警告：{json.dumps(risk_assessment.warnings, ensure_ascii=False)}

你的任務：
1. 綜合考慮交易決策和風險評估
2. 做出最終批准或拒絕決定
3. 確定最終執行的倉位大小
4. 提供執行指示

請以 JSON 格式回覆：
- approved: true/false
- final_decision: "Execute Buy"/"Execute Sell"/"Hold"/"Reject"
- final_position_size: 最終倉位 (0-1)
- execution_notes: 執行注意事項 (繁體中文)
- rationale: 批准/拒絕的理由 (繁體中文，至少50字)
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return FinalApproval.model_validate(json.loads(response.choices[0].message.content))


# ============================================================================
# TradingAgents 主系統
# ============================================================================

def prepare_market_data(df: pd.DataFrame) -> Dict:
    """準備市場數據"""
    if df is None or df.empty:
        return {}
    
    latest = df.iloc[-1]
    
    price_data = {
        "當前價格": float(latest['Close']),
        "開盤價": float(latest['Open']),
        "最高價": float(latest['High']),
        "最低價": float(latest['Low']),
        "成交量": float(latest['Volume']),
        "時間戳": str(latest['Close_time'])
    }
    
    if len(df) >= 7:
        price_data["7天價格變化百分比"] = float(((latest['Close'] / df.iloc[-7]['Close']) - 1) * 100)
    
    if len(df) >= 30:
        price_data["30天價格變化百分比"] = float(((latest['Close'] / df.iloc[-30]['Close']) - 1) * 100)
    
    technical_indicators = {
        "趨勢指標": {
            "EMA_12": float(latest.get('EMA_12', 0)),
            "EMA_26": float(latest.get('EMA_26', 0)),
            "ADX_14": float(latest.get('ADX_14', 0)) if 'ADX_14' in latest else None
        },
        "動量指標": {
            "RSI_14": float(latest.get('RSI_14', 0)),
            "MACD_線": float(latest.get('MACD_12_26_9', 0)),
            "MACD_信號線": float(latest.get('MACDs_12_26_9', 0)),
            "MACD_柱狀圖": float(latest.get('MACDh_12_26_9', 0))
        },
        "隨機指標": {
            "Stochastic_K": float(latest.get('STOCHk_14_3_3', 0)) if 'STOCHk_14_3_3' in latest else None,
            "Stochastic_D": float(latest.get('STOCHd_14_3_3', 0)) if 'STOCHd_14_3_3' in latest else None
        },
        "波動率指標": {
            "ATR_14": float(latest.get('ATR_14', 0)) if 'ATR_14' in latest else None,
            "布林帶_上軌": float(latest.get('BBU_20_2.0', 0)) if 'BBU_20_2.0' in latest else None,
            "布林帶_下軌": float(latest.get('BBL_20_2.0', 0)) if 'BBL_20_2.0' in latest else None
        },
        "成交量指標": {
            "OBV": float(latest.get('OBV', 0)) if 'OBV' in latest else None
        }
    }
    
    recent_history = []
    for i in range(min(5, len(df))):
        idx = -(i + 1)
        row = df.iloc[idx]
        recent_history.append({
            "時間": str(row['Close_time']),
            "價格": float(row['Close']),
            "RSI": float(row.get('RSI_14', 0)),
            "成交量": float(row['Volume'])
        })
    
    market_structure = {}
    if len(df) >= 20:
        returns = df['Close'].pct_change().tail(20)
        market_structure["20天波動率_年化"] = float(returns.std() * np.sqrt(252) * 100)
        vol_ma = df['Volume'].rolling(20).mean()
        market_structure["當前成交量vs平均_比例"] = float(latest['Volume'] / vol_ma.iloc[-1]) if vol_ma.iloc[-1] > 0 else 1.0
    
    key_levels = {}
    if len(df) >= 30:
        key_levels["30天最高"] = float(df['High'].tail(30).max())
        key_levels["30天最低"] = float(df['Low'].tail(30).min())
    
    return {
        "價格資訊": price_data,
        "技術指標": technical_indicators,
        "最近5天歷史": recent_history,
        "市場結構": market_structure,
        "關鍵價位": key_levels
    }


def run_trading_agents(symbol: str = 'BTCUSDT', interval: str = '1d', limit: int = 100):
    """執行完整的 TradingAgents 流程"""
    
    print("=" * 100)
    print("TradingAgents：多智能體 LLM 交易框架")
    print("模擬專業交易公司的協作決策流程")
    print("=" * 100)
    
    # 初始化 OpenAI 客戶端
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 錯誤：找不到 OPENAI_API_KEY")
        return
    
    client = openai.OpenAI(api_key=api_key)
    
    # 獲取市場數據
    print("\n[準備階段] 正在獲取市場數據...")
    klines_df = get_historical_klines(symbol, interval, limit)
    if klines_df is None or klines_df.empty:
        print("❌ 數據獲取失敗")
        return
    
    df_with_indicators = add_technical_indicators(klines_df)
    market_data = prepare_market_data(df_with_indicators)
    current_price = market_data['價格資訊']['當前價格']
    
    print(f"✅ 數據準備完成 | 當前價格: ${current_price:.2f}")
    
    # 第一層：分析師團隊並行工作
    print("\n" + "=" * 100)
    print("第一層：分析師團隊 (並行分析)")
    print("=" * 100)
    
    technical_analyst = TechnicalAnalyst(client)
    sentiment_analyst = SentimentAnalyst(client)
    fundamental_analyst = FundamentalAnalyst(client)
    news_analyst = NewsAnalyst(client)
    
    print("📊 技術分析師正在分析...")
    tech_report = technical_analyst.analyze(market_data)
    print(f"✅ 技術分析完成 | 信心度: {tech_report.confidence}%")
    
    print("💭 情緒分析師正在分析...")
    sentiment_report = sentiment_analyst.analyze(market_data)
    print(f"✅ 情緒分析完成 | 信心度: {sentiment_report.confidence}%")
    
    print("📈 基本面分析師正在分析...")
    fundamental_report = fundamental_analyst.analyze(market_data, symbol)
    print(f"✅ 基本面分析完成 | 信心度: {fundamental_report.confidence}%")
    
    print("📰 新聞分析師正在分析...")
    news_report = news_analyst.analyze(market_data)
    print(f"✅ 新聞分析完成 | 信心度: {news_report.confidence}%")
    
    analyst_reports = [tech_report, sentiment_report, fundamental_report, news_report]
    
    # 第二層：研究團隊辯論
    print("\n" + "=" * 100)
    print("第二層：研究團隊 (多空辯論)")
    print("=" * 100)
    
    bull_researcher = BullResearcher(client)
    bear_researcher = BearResearcher(client)
    
    print("🐂 多頭研究員正在構建看漲論點...")
    bull_argument = bull_researcher.debate(analyst_reports)
    print(f"✅ 多頭論點完成 | 信心度: {bull_argument.confidence}%")
    
    print("🐻 空頭研究員正在構建看跌論點...")
    bear_argument = bear_researcher.debate(analyst_reports)
    print(f"✅ 空頭論點完成 | 信心度: {bear_argument.confidence}%")
    
    # 第三層：交易員決策
    print("\n" + "=" * 100)
    print("第三層：交易員 (綜合決策)")
    print("=" * 100)
    
    trader = Trader(client)
    print("💼 交易員正在綜合所有資訊並做出決策...")
    trader_decision = trader.make_decision(analyst_reports, bull_argument, bear_argument, current_price)
    print(f"✅ 交易決策完成 | 決策: {trader_decision.decision} | 信心度: {trader_decision.confidence}%")
    
    # 第四層：風險管理
    print("\n" + "=" * 100)
    print("第四層：風險管理 (風險評估)")
    print("=" * 100)
    
    risk_manager = RiskManager(client)
    print("🛡️ 風險經理正在評估交易風險...")
    risk_assessment = risk_manager.assess(trader_decision, market_data)
    print(f"✅ 風險評估完成 | 風險等級: {risk_assessment.risk_level} | 批准: {'是' if risk_assessment.approve else '否'}")
    
    # 第五層：基金經理批准
    print("\n" + "=" * 100)
    print("第五層：基金經理 (最終審批)")
    print("=" * 100)
    
    fund_manager = FundManager(client)
    print("👔 基金經理正在做最終審批...")
    final_approval = fund_manager.approve(trader_decision, risk_assessment)
    print(f"✅ 最終審批完成 | 決定: {final_approval.final_decision}")
    
    # 顯示完整決策流程
    display_full_report(
        analyst_reports,
        bull_argument,
        bear_argument,
        trader_decision,
        risk_assessment,
        final_approval,
        current_price
    )


def display_full_report(
    analyst_reports,
    bull_argument,
    bear_argument,
    trader_decision,
    risk_assessment,
    final_approval,
    current_price
):
    """顯示完整的決策報告"""
    
    print("\n\n" + "=" * 100)
    print("📋 TradingAgents 完整決策報告")
    print("=" * 100)
    
    # 分析師報告
    print("\n【第一層：分析師團隊報告】")
    print("-" * 100)
    for report in analyst_reports:
        print(f"\n{report.analyst_type} (信心度: {report.confidence}%)")
        print(f"摘要：{report.summary}")
        if report.bullish_points:
            print(f"看漲點：{', '.join(report.bullish_points[:3])}")
        if report.bearish_points:
            print(f"看跌點：{', '.join(report.bearish_points[:3])}")
    
    # 研究員辯論
    print("\n【第二層：研究團隊辯論】")
    print("-" * 100)
    print(f"\n🐂 多頭研究員 (信心度: {bull_argument.confidence}%)")
    print(f"論點：{bull_argument.argument}")
    print(f"關鍵點：")
    for point in bull_argument.key_points:
        print(f"  • {point}")
    
    print(f"\n🐻 空頭研究員 (信心度: {bear_argument.confidence}%)")
    print(f"論點：{bear_argument.argument}")
    print(f"關鍵點：")
    for point in bear_argument.key_points:
        print(f"  • {point}")
    
    # 交易員決策
    print("\n【第三層：交易員決策】")
    print("-" * 100)
    print(f"決策：{trader_decision.decision}")
    print(f"信心度：{trader_decision.confidence}%")
    print(f"建議倉位：{trader_decision.position_size * 100:.0f}%")
    print(f"進場價：${trader_decision.entry_price:.2f}")
    print(f"止損價：${trader_decision.stop_loss:.2f} ({((trader_decision.stop_loss/current_price - 1) * 100):.2f}%)")
    print(f"止盈價：${trader_decision.take_profit:.2f} ({((trader_decision.take_profit/current_price - 1) * 100):.2f}%)")
    print(f"\n推理過程：{trader_decision.reasoning}")
    print(f"\n綜合評估：{trader_decision.synthesis}")
    
    # 風險評估
    print("\n【第四層：風險管理評估】")
    print("-" * 100)
    print(f"風險等級：{risk_assessment.risk_level}")
    print(f"風險經理批准：{'✅ 是' if risk_assessment.approve else '❌ 否'}")
    print(f"調整後倉位：{risk_assessment.adjusted_position_size * 100:.0f}%")
    print(f"評估：{risk_assessment.assessment}")
    if risk_assessment.warnings:
        print(f"\n⚠️ 風險警告：")
        for warning in risk_assessment.warnings:
            print(f"  • {warning}")
    print(f"\n建議調整：{risk_assessment.suggested_adjustments}")
    
    # 最終審批
    print("\n【第五層：基金經理最終審批】")
    print("-" * 100)
    print(f"最終決定：{final_approval.final_decision}")
    print(f"是否批准：{'✅ 批准' if final_approval.approved else '❌ 拒絕'}")
    print(f"最終倉位：{final_approval.final_position_size * 100:.0f}%")
    print(f"執行指示：{final_approval.execution_notes}")
    print(f"批准理由：{final_approval.rationale}")
    
    # 最終建議
    print("\n" + "=" * 100)
    print("🎯 最終執行建議")
    print("=" * 100)
    
    if final_approval.approved:
        action_emoji = "🟢" if "Buy" in final_approval.final_decision else "🔴"
        print(f"{action_emoji} 建議執行：{final_approval.final_decision}")
        print(f"執行倉位：{final_approval.final_position_size * 100:.0f}%")
        print(f"當前價格：${current_price:.2f}")
        if final_approval.final_position_size > 0:
            print(f"止損價位：${trader_decision.stop_loss:.2f}")
            print(f"止盈價位：${trader_decision.take_profit:.2f}")
    else:
        print("⏸️ 建議觀望，等待更好的機會")
    
    print("\n" + "=" * 100)
    print("報告結束")
    print("=" * 100)


if __name__ == '__main__':
    run_trading_agents(symbol='BTCUSDT', interval='1d', limit=100)