import json
import openai
from typing import Literal, List, Dict, Optional
from models import AnalystReport, ResearcherDebate, TraderDecision, RiskAssessment, FinalApproval
from config import FAST_THINKING_MODEL, DEEP_THINKING_MODEL
from llm_client import supports_json_mode, extract_json_from_response
from retry_utils import retry_on_failure

# ============================================================================ 
# 第一層：分析師團隊 (Analysts Team)
# ============================================================================ 

class TechnicalAnalyst:
    """技術分析師 Agent"""

    def __init__(self, client):
        self.client = client
        self.role = "技術分析師"

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
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

        請以 JSON 格式回覆，嚴格遵守以下格式與要求：
        - analyst_type: "技術分析師"
        - summary: 技術分析摘要 (繁體中文，至少50字)。
        - key_findings: 關鍵發現列表 (**必須是字串的列表**，例如：`["RSI 指標顯示超買", "價格突破布林帶上軌"]`)。
        - bullish_points: 看漲技術信號列表 (List[str])。
        - bearish_points: 看跌技術信號列表 (List[str])。
        - confidence: 信心度 (0-100)。
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

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
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

請以 JSON 格式回覆，嚴格遵守以下格式與要求：
- analyst_type: "情緒分析師"
- summary: 情緒分析摘要 (繁體中文，**至少50字**)。
- key_findings: 關鍵發現列表 (**必須是字串的列表**，例如：`["市場情緒偏向貪婪", "成交量放大顯示參與度高"]`)。
- bullish_points: 正面情緒指標列表 (List[str])。
- bearish_points: 負面情緒指標列表 (List[str])。
- confidence: 信心度 (0 到 100 的數字)。
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

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def analyze(self, market_data: Dict, symbol: str) -> AnalystReport:
        """分析基本面"""

        market_type = market_data.get('market_type', 'spot')
        leverage = market_data.get('leverage', 1)
        exchange = market_data.get('exchange', 'binance')
        funding_rate_info = market_data.get('funding_rate_info', {})

        prompt = f"""
你是一位基本面分析專家，專精於評估加密貨幣的長期價值。
當前市場類型是：{market_type}，槓桿倍數是：{leverage}x。
數據來源交易所：{exchange}。

對於 {symbol}，請分析：
1. 長期趨勢和價格定位
2. 市場結構的健康度
3. 關鍵支撐和壓力位
4. 市場成熟度指標
{f"5. 資金費率資訊：{json.dumps(funding_rate_info, indent=2, ensure_ascii=False)}" if market_type == 'futures' else ""}

市場數據：
{json.dumps(market_data, indent=2, ensure_ascii=False)}

請以 JSON 格式回覆，嚴格遵守以下數據類型：
- analyst_type: "基本面分析師"
- summary: 基本面分析摘要 (繁體中文，**至少50字**)。
- key_findings: 關鍵發現列表 (必須是字串 List ["發現1", "發現2"]，不要使用 Key-Value 物件)。
- bullish_points: 看漲基本面因素列表 (List[str])。
- bearish_points: 看跌基本面因素列表 (List[str])。
- confidence: 信心度 (必須是 0 到 100 之間的數字，例如 75，不要寫文字)。
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

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def analyze(self, market_data: Dict) -> AnalystReport:
        """分析真實市場新聞和事件"""

        # 提取真實新聞數據
        real_news = market_data.get('新聞資訊', [])
        
        if not real_news:
            news_context = "目前沒有獲取到最新的真實新聞，請基於市場價格波動進行合理的推測分析。"
        else:
            news_str = "\n".join([f"- {n['title']}: {n.get('description', 'N/A')}" for n in real_news])
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
        print("============================================================")
        print("新聞分析師回覆內容：")  
        print(market_data)
        print("============================================================")
        return AnalystReport.model_validate(json.loads(response.choices[0].message.content))


# ============================================================================ 
# 第二層：研究團隊 (Research Team) - 進行辯論
# ============================================================================ 

class BullResearcher:
    """多頭研究員 Agent"""

    def __init__(self, client, model: str = None):
        self.client = client
        self.model = model or DEEP_THINKING_MODEL
        self.stance = "Bull"
        print(f"  🐂 多頭研究員使用模型: {self.model}")

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

        # 根據模型是否支持 JSON 模式來決定是否使用 response_format
        try:
            if supports_json_mode(self.model):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                # 支持 JSON 模式的模型，直接解析
                result_dict = json.loads(response.choices[0].message.content)
            else:
                # 對於不支持 JSON 模式的模型，仍然在 prompt 中要求 JSON，但不使用 response_format
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                # 使用提取函數從響應中提取 JSON
                result_dict = extract_json_from_response(response.choices[0].message.content)

            return ResearcherDebate.model_validate(result_dict)
        except Exception as e:
            print(f"       ❌ 失敗: {e}")
            # 返回一個默認的響應，避免整個流程中斷
            raise

class BearResearcher:
    """空頭研究員 Agent"""

    def __init__(self, client, model: str = None):
        self.client = client
        self.model = model or DEEP_THINKING_MODEL
        self.stance = "Bear"
        print(f"  🐻 空頭研究員使用模型: {self.model}")

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

        # 根據模型是否支持 JSON 模式來決定是否使用 response_format
        try:
            if supports_json_mode(self.model):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                # 支持 JSON 模式的模型，直接解析
                result_dict = json.loads(response.choices[0].message.content)
            else:
                # 對於不支持 JSON 模式的模型，仍然在 prompt 中要求 JSON，但不使用 response_format
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                # 使用提取函數從響應中提取 JSON
                result_dict = extract_json_from_response(response.choices[0].message.content)

            return ResearcherDebate.model_validate(result_dict)
        except Exception as e:
            print(f"       ❌ 失敗: {e}")
            # 返回一個默認的響應，避免整個流程中斷
            raise

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
        current_price: float,
        market_data: Dict,
        market_type: str,
        leverage: int,
        feedback: Optional[RiskAssessment] = None
    ) -> TraderDecision:
        """基於所有資訊做出交易決策"""

        feedback_prompt = ""
        if feedback:
            feedback_prompt = f"""
=== 風險管理員回饋 ===
你的上一個計畫已被拒絕，原因如下。請根據這些回饋，提出一個經過修正的、全新的交易計畫。
風險評估: {feedback.assessment}
建議調整: {feedback.suggested_adjustments}
警告: {", ".join(feedback.warnings)}
請務必根據以上建議，調整你的倉位、止損或止盈，或改變決策。
"""
        decision_options = ""
        if market_type == 'spot':
            decision_options = "Buy\" / \"Sell\" / \"Hold"
        else: # futures
            decision_options = "Long\" / \"Short\" / \"Hold"

        funding_rate_context = ""
        if market_type == 'futures' and market_data.get('funding_rate_info'):
            funding_rate_context = f"""
=== 資金費率資訊 ===
{json.dumps(market_data['funding_rate_info'], indent=2, ensure_ascii=False)}
"""
        exchange = market_data.get('exchange', 'binance') # Extract exchange from market_data

        # 提取關鍵價位信息
        key_levels = market_data.get('關鍵價位', {})
        support = key_levels.get('支撐位', current_price * 0.95)
        resistance = key_levels.get('壓力位', current_price * 1.05)

        prompt = f"""
你是一位經驗豐富的專業交易員，負責做出最終的交易決策。
當前市場類型是：{market_type}。
數據來源交易所：{exchange}。
{f"請根據市場風險、波動率和你的交易策略，自行決定合適的槓桿倍數 (1-125x)。考慮因素：波動率越高應使用越低槓桿，趨勢越明確可適當提高槓桿。" if market_type == 'futures' else ""}
{feedback_prompt}

你已經收到：
1. 四位分析師的詳細報告
2. 多頭研究員的看漲論點
3. 空頭研究員的看跌論點

=== 市場價格資訊 ===
當前價格：${current_price:.2f}
支撐位：${support:.2f}
壓力位：${resistance:.2f}
{funding_rate_context}

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
1. 綜合評估所有資訊，做出理性的交易決策 ({decision_options})。
2. **如果決定交易（非 Hold），你必須給出具體的進場價、止損價、止盈價（浮點數）**。
3. 確定合理的倉位大小（佔總資金的百分比）。
4. 基於技術分析設定止損止盈：
   - 止損：可參考支撐位/壓力位，或使用 ATR、固定百分比（2-5%）
   - 止盈：可參考壓力位/支撐位，或使用風險回報比（1:2 或 1:3）

**重要**：所有價格必須是具體數字（浮點數），不能是 null（除非 decision 為 "Hold"）。

請以 JSON 格式回覆：
- decision: "{decision_options}"
- reasoning: 決策推理 (繁體中文，至少100字)。
- position_size: 建議倉位 (0-1)。如果 decision 為 "Hold"，此項應為 0。
{f"- leverage: 使用的槓桿倍數 (整數，1-125)。僅當 decision 為 \"Long\" 或 \"Short\" 時需要提供，否則為 null。" if market_type == 'futures' else ""}
- entry_price: **進場價位（浮點數）**。通常是當前價格或稍微優化的價格。Hold 時為 null。
- stop_loss: **止損價位（浮點數）**。必須基於技術分析或固定百分比。Hold 時為 null。
- take_profit: **止盈價位（浮點數）**。建議使用 1:2 或 1:3 風險回報比。Hold 時為 null。
- confidence: 決策信心度 (0-100)
- synthesis: 如何綜合各方意見 (繁體中文)

**範例（做多）**：
- entry_price: {current_price:.2f}
- stop_loss: {current_price * 0.97:.2f}  (約 -3% 止損)
- take_profit: {current_price * 1.06:.2f}  (約 +6% 止盈，1:2 風險回報比)

**範例（做空）**：
- entry_price: {current_price:.2f}
- stop_loss: {current_price * 1.03:.2f}  (約 +3% 止損)
- take_profit: {current_price * 0.94:.2f}  (約 -6% 止盈)
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

# 在 agents.py 的 RiskManager 類中需要修改

class RiskManager:
    """風險管理員 Agent"""
    
    def __init__(self, client):
        self.client = client
    
    def assess(
        self,
        trader_decision: TraderDecision,
        market_data: Dict,
        market_type: str,
        leverage: int
    ) -> RiskAssessment:
        """評估交易決策的風險"""
        
        # 🔧 特殊處理 Hold 決策
        if trader_decision.decision == "Hold":
            return RiskAssessment(
                risk_level="低風險",
                assessment="交易員建議保持觀望，不進行任何交易操作。當前市場狀況不明朗或缺乏明確的交易機會，因此選擇不承擔任何新的市場風險。這是一個謹慎且合理的決策。",
                warnings=["建議持續關注市場動態", "如市場出現明確信號可重新評估"],
                suggested_adjustments="無需調整，維持觀望狀態即可。",
                approve=True,
                adjusted_position_size=0.0
            )
        
        prompt = f"""
你是一位風險管理專家，負責評估並控制交易風險。
當前市場類型是：{market_type}。

交易員決策：
- 決策：{trader_decision.decision}
- 倉位：{trader_decision.position_size * 100}%
{f"- 使用槓桿：{trader_decision.leverage}x" if trader_decision.leverage else ""}
- 進場價：${f'{trader_decision.entry_price:.2f}' if trader_decision.entry_price is not None else 'N/A'}
- 止損：${f'{trader_decision.stop_loss:.2f}' if trader_decision.stop_loss is not None else 'N/A'}
- 止盈：${f'{trader_decision.take_profit:.2f}' if trader_decision.take_profit is not None else 'N/A'}
- 信心度：{trader_decision.confidence}%
- 理由：{trader_decision.reasoning}

市場狀況：
波動率：{market_data.get('市場結構', {}).get('波動率', 'N/A')}%
成交量：{market_data.get('市場結構', {}).get('平均交易量', 'N/A')}
{f"資金費率：{market_data['funding_rate_info'].get('last_funding_rate', 'N/A')}" if market_type == 'futures' and market_data.get('funding_rate_info') else ""}

你的任務：
1. 評估這筆交易的風險等級
2. 檢查倉位、止損、止盈是否合理
3. 決定是否批准或需要調整
{f"4. 對於合約交易，特別評估槓桿帶來的清算風險和資金費率的影響。" if market_type == 'futures' else ""}

**重要決策邏輯**：
- 如果交易計劃合理且風險可控 → approve: true, adjusted_position_size 等於原始倉位
- 如果有明顯風險但可調整 → approve: true, adjusted_position_size 為調整後的倉位
- 如果風險過高無法接受 → approve: false

**adjusted_position_size 設定規則**：
✅ 如果**完全同意**交易員的建議 → adjusted_position_size = {trader_decision.position_size}（與原始倉位相同）
⚠️  如果需要**小幅調整** → adjusted_position_size 調整為合理值（例如降低 10-30%）
❌ 如果**不批准** → approve: false, adjusted_position_size = 0

請以 JSON 格式回覆：
- risk_level: "低風險"/"中低風險"/"中風險"/"中高風險"/"高風險"/"極高風險"
- assessment: 風險評估（繁體中文，至少50個字符）
- warnings: 風險警告列表（如果沒有風險警告，可以是空列表 []）
- suggested_adjustments: 建議調整（繁體中文）。如果完全同意，寫"建議按照交易員計劃執行"。
- approve: true/false（是否批准）
- adjusted_position_size: 調整後的倉位（0-1）。**如果完全同意，必須等於 {trader_decision.position_size}**
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
        risk_assessment: RiskAssessment,
        market_type: str,
        leverage: int
    ) -> FinalApproval:
        """最終審批交易"""
        
        # 計算調整幅度
        position_change_pct = abs(risk_assessment.adjusted_position_size - trader_decision.position_size) / trader_decision.position_size * 100 if trader_decision.position_size > 0 else 0

        prompt = f"""
你是一位基金經理，擁有最終的資金調度權。
當前市場類型是：{market_type}。

交易員建議：
- 決策：{trader_decision.decision}
- 建議倉位：{trader_decision.position_size * 100}%
{f"- 建議槓桿：{trader_decision.leverage}x" if trader_decision.leverage else ""}
- 理由：{trader_decision.reasoning}

風險管理員評估：
- 風險等級：{risk_assessment.risk_level}
- 評估意見：{risk_assessment.assessment}
- 是否批准：{risk_assessment.approve}
- 調整後倉位：{risk_assessment.adjusted_position_size * 100}%
- 調整幅度：{position_change_pct:.1f}%
{f"- 建議調整：{risk_assessment.suggested_adjustments}" if market_type == 'futures' else ""}

**最終決策邏輯**：
1. 如果風險管理**批准** + 倉位調整幅度 < 5% → final_decision: "Approve"（完全批准）
2. 如果風險管理**批准** + 倉位調整幅度 5-30% → final_decision: "Amended"（修正後批准）
3. 如果風險管理**批准** + 倉位調整幅度 > 30% → 根據風險評估決定 Amended 或 Reject
4. 如果風險管理**不批准** → final_decision: "Reject"（拒絕交易）

你的任務：
1. 審核交易員的決策與風險管理員的評估
2. 根據上述邏輯做出最終決定
3. 確定最終執行的倉位大小與槓桿倍數

請以 JSON 格式回覆：
- approved: true 或 false（是否批准交易）
- final_decision: "Approve" / "Reject" / "Amended" / "Hold"
- final_position_size: 最終批准的倉位（0-1）。通常採用風險管理員建議的 adjusted_position_size。
- approved_leverage: 最終批准的槓桿倍數（整數）。現貨或不交易時為 null。
- execution_notes: 具體的執行注意事項（例如："分批進場"、"嚴格執行止損"）
- rationale: 最終決策的詳細理由（繁體中文，至少 50 字）

**範例**：
- 如果倉位調整 < 5%：final_decision = "Approve"，rationale = "風險管理評估通過，交易計劃合理，批准按原計劃執行。"
- 如果倉位調整 10%：final_decision = "Amended"，rationale = "基於風險控制，將倉位從 30% 調整至 20%，降低市場曝險。"
- 如果風險過高：final_decision = "Reject"，rationale = "當前市場風險過高，不適合開倉，建議觀望。"
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        # 解析 JSON
        result = json.loads(response.choices[0].message.content)
        
        # ==========================================
        # 🛡️ 數據清洗與容錯處理 (防止 AI 偶發性漏欄位)
        # ==========================================
        
        # 1. 確保 approved 欄位存在
        if 'approved' not in result:
            # 如果 AI 沒給 approved，根據 final_decision 推斷
            result['approved'] = result.get('final_decision') in ['Approve', 'Amended']

        # 2. 處理槓桿
        if 'approved_leverage' not in result:
            result['approved_leverage'] = None
        if market_type == 'spot': # 現貨強制為 None
            result['approved_leverage'] = None
            
        # 3. 處理拒絕或觀望的情況
        if result.get('final_decision') in ['Hold', 'Reject']:
            result['approved_leverage'] = None
            result['final_position_size'] = 0.0
            result['approved'] = False # 確保邏輯一致

        # 4. 確保 execution_notes 存在
        if 'execution_notes' not in result:
            result['execution_notes'] = "依照標準程序執行，注意滑點控制。"

        # 5. 確保 rationale 存在 (防止 AI 寫成 reasoning)
        if 'rationale' not in result:
            # 如果 AI 寫錯成 reasoning，就複製過來
            result['rationale'] = result.get('reasoning', '基於風險與收益比的綜合考量做出此決策。')

        return FinalApproval.model_validate(result)