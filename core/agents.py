import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import openai
from typing import Literal, List, Dict, Optional
from core.models import (
    AnalystReport, ResearcherDebate, TraderDecision, RiskAssessment, 
    FinalApproval, FactCheckResult, MultiTimeframeData
)
from core.config import FAST_THINKING_MODEL, DEEP_THINKING_MODEL, QUERY_PARSER_MODEL
from utils.llm_client import supports_json_mode, extract_json_from_response
from utils.retry_utils import retry_on_failure
from utils.utils import DataFrameEncoder
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from core.tools import get_crypto_tools

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

        # 檢查是否存在多週期數據
        multi_timeframe_data = market_data.get('multi_timeframe_data')
        multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis')

        multi_timeframe_context = ""
        if multi_timeframe_data:
            # 構建多週期分析上下文
            trend_info = multi_timeframe_analysis or {}
            short_term_data = multi_timeframe_data.get('short_term', {})
            medium_term_data = multi_timeframe_data.get('medium_term', {})
            long_term_data = multi_timeframe_data.get('long_term', {})

            multi_timeframe_context = f"""
多週期技術指標分析：
- 短週期趨勢 ({short_term_data.get('timeframe', '1h')}): {trend_info.get('short_term_trend', '不明')}
- 中週期趨勢 ({medium_term_data.get('timeframe', '4h')}): {trend_info.get('medium_term_trend', '不明')}
- 長週期趨勢 ({long_term_data.get('timeframe', '1d')}): {trend_info.get('long_term_trend', '不明')}
- 趨勢一致性: {trend_info.get('trend_consistency', '不明')}
- 整體偏向: {trend_info.get('overall_bias', '中性')}
- 多週期信心分數: {trend_info.get('confidence_score', 0):.1f}%

短週期({short_term_data.get('timeframe', '1h')})技術指標: {short_term_data.get('技術指標', {})}
中週期({medium_term_data.get('timeframe', '4h')})技術指標: {medium_term_data.get('技術指標', {})}
長週期({long_term_data.get('timeframe', '1d')})技術指標: {long_term_data.get('技術指標', {})}
"""
        else:
            multi_timeframe_context = "當前為單一週期分析模式，未啟用多週期技術指標對比。"

        prompt = f"""
你是一位專業的多週期技術分析師，專精於分析不同時間框架下的技術指標和市場結構。

你的任務：
1. 分析提供的單一週期及多週期技術指標數據
2. 識別各時間週期的關鍵技術信號（趨勢、動量、超買超賣）
3. 比較不同週期技術指標的一致性/分歧度
4. 提供看漲和看跌的多週期技術論點
5. 給出你的專業判斷

當前週期市場數據：
主要技術指標：
{json.dumps(market_data.get('技術指標', {}), indent=2, ensure_ascii=False)}
價格資訊：
{json.dumps(market_data.get('價格資訊', {}), indent=2, ensure_ascii=False)}

{multi_timeframe_context}

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

        result = AnalystReport.model_validate(json.loads(response.choices[0].message.content))

        # 如果存在多週期數據，創建多週期分析對象並附加到結果中
        if 'multi_timeframe_data' in market_data:
            from core.models import MultiTimeframeData
            multi_timeframe_data = market_data['multi_timeframe_data']
            multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis', {})

            multi_tf_analysis = MultiTimeframeData(
                short_term=multi_timeframe_data.get('short_term'),
                medium_term=multi_timeframe_data.get('medium_term'),
                long_term=multi_timeframe_data.get('long_term'),
                overall_trend=multi_timeframe_analysis
            )
            result.multi_timeframe_analysis = multi_tf_analysis

        return result


class SentimentAnalyst:
    """情緒分析師 Agent"""

    def __init__(self, client):
        self.client = client
        self.role = "情緒分析師"

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def analyze(self, market_data: Dict) -> AnalystReport:
        """分析市場情緒"""

        # 檢查是否存在多週期數據
        multi_timeframe_data = market_data.get('multi_timeframe_data')
        multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis')

        multi_timeframe_context = ""
        if multi_timeframe_data:
            # 構建多週期分析上下文
            trend_info = multi_timeframe_analysis or {}
            short_term_data = multi_timeframe_data.get('short_term', {})
            medium_term_data = multi_timeframe_data.get('medium_term', {})
            long_term_data = multi_timeframe_data.get('long_term', {})

            multi_timeframe_context = f"""
多週期市場情緒分析：
- 短週期({short_term_data.get('timeframe', '1h')})情緒狀態: {short_term_data.get('市場結構', {}).get('趨勢', '不明')}
- 中週期({medium_term_data.get('timeframe', '4h')})情緒狀態: {medium_term_data.get('市場結構', {}).get('趨勢', '不明')}
- 長週期({long_term_data.get('timeframe', '1d')})情緒狀態: {long_term_data.get('市場結構', {}).get('趨勢', '不明')}
- 情緒一致性: {trend_info.get('trend_consistency', '不明')}
- 整體情緒偏向: {trend_info.get('overall_bias', '中性')}
- 多週期情緒信心分數: {trend_info.get('confidence_score', 0):.1f}%

短週期({short_term_data.get('timeframe', '1h')})波動率: {short_term_data.get('市場結構', {}).get('波動率', '不明')}
中週期({medium_term_data.get('timeframe', '4h')})波動率: {medium_term_data.get('市場結構', {}).get('波動率', '不明')}
長週期({long_term_data.get('timeframe', '1d')})波動率: {long_term_data.get('市場結構', {}).get('波動率', '不明')}
"""
        else:
            multi_timeframe_context = "當前為單一週期分析模式，未啟用多週期情緒對比。"

        prompt = f"""
你是一位專業的多週期市場情緒分析專家，專精於解讀不同時間框架下的市場氛圍和投資者心理。

你的任務：
1. 基於價格走勢和成交量評估市場情緒
2. 分析不同時間週期的情緒差異
3. 識別恐慌或貪婪的跡象
4. 評估情緒在不同週期的一致性/分歧度
5. 判斷情緒對短期和長期價格的潛在影響

市場數據：
當前週期價格變化：{json.dumps(market_data.get('價格資訊', {}), indent=2, ensure_ascii=False)}
當前週期市場結構：{json.dumps(market_data.get('市場結構', {}), indent=2, ensure_ascii=False)}

{multi_timeframe_context}

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

        result = AnalystReport.model_validate(json.loads(response.choices[0].message.content))

        # 如果存在多週期數據，創建多週期分析對象並附加到結果中
        if 'multi_timeframe_data' in market_data:
            from core.models import MultiTimeframeData
            multi_timeframe_data = market_data['multi_timeframe_data']
            multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis', {})

            multi_tf_analysis = MultiTimeframeData(
                short_term=multi_timeframe_data.get('short_term'),
                medium_term=multi_timeframe_data.get('medium_term'),
                long_term=multi_timeframe_data.get('long_term'),
                overall_trend=multi_timeframe_analysis
            )
            result.multi_timeframe_analysis = multi_tf_analysis

        return result


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

        # 檢查是否存在多週期數據
        multi_timeframe_data = market_data.get('multi_timeframe_data')
        multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis')

        multi_timeframe_context = ""
        if multi_timeframe_data:
            # 構建多週期分析上下文
            trend_info = multi_timeframe_analysis or {}
            short_term_data = multi_timeframe_data.get('short_term', {})
            medium_term_data = multi_timeframe_data.get('medium_term', {})
            long_term_data = multi_timeframe_data.get('long_term', {})

            multi_timeframe_context = f"""
多週期基本面分析：
- 短週期({short_term_data.get('timeframe', '1h')})趨勢: {trend_info.get('short_term_trend', '不明')}
- 中週期({medium_term_data.get('timeframe', '4h')})趨勢: {trend_info.get('medium_term_trend', '不明')}
- 長週期({long_term_data.get('timeframe', '1d')})趨勢: {trend_info.get('long_term_trend', '不明')}
- 趨勢一致性: {trend_info.get('trend_consistency', '不明')}
- 整體結構強度: {trend_info.get('overall_bias', '中性')}
- 多週期結構信心分數: {trend_info.get('confidence_score', 0):.1f}%

短週期({short_term_data.get('timeframe', '1h')})市場結構: {short_term_data.get('市場結構', {})}
中週期({medium_term_data.get('timeframe', '4h')})市場結構: {medium_term_data.get('市場結構', {})}
長週期({long_term_data.get('timeframe', '1d')})市場結構: {long_term_data.get('市場結構', {})}
關鍵價位一致性評估:
{f"短週期支撐: {short_term_data.get('關鍵價位', {}).get('支撐位', '不明')}, 中週期支撐: {medium_term_data.get('關鍵價位', {}).get('支撐位', '不明')}, 長週期支撐: {long_term_data.get('關鍵價位', {}).get('支撐位', '不明')}"}
{f"短週期壓力: {short_term_data.get('關鍵價位', {}).get('壓力位', '不明')}, 中週期壓力: {medium_term_data.get('關鍵價位', {}).get('壓力位', '不明')}, 長週期壓力: {long_term_data.get('關鍵價位', {}).get('壓力位', '不明')}"}
"""
        else:
            multi_timeframe_context = "當前為單一週期分析模式，未啟用多週期基本面對比。"

        prompt = f"""
你是一位專業的多週期基本面分析專家，專精於評估不同時間框架下加密貨幣的價值和結構健康度。
當前市場類型是：{market_type}，槓桿倍數是：{leverage}x。
數據來源交易所：{exchange}。

對於 {symbol}，請分析：
1. 長期趨勢和價格定位
2. 市場結構在不同週期的健康度
3. 多週期關鍵支撐和壓力位的一致性/分歧度
4. 市場成熟度在不同時間框架下的表現
{f"5. 資金費率資訊：{json.dumps(funding_rate_info, indent=2, ensure_ascii=False)}" if market_type == 'futures' else ""}

當前週期市場數據：
{json.dumps(market_data, indent=2, ensure_ascii=False, cls=DataFrameEncoder)}

{multi_timeframe_context}

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

        result = AnalystReport.model_validate(json.loads(response.choices[0].message.content))

        # 如果存在多週期數據，創建多週期分析對象並附加到結果中
        if 'multi_timeframe_data' in market_data:
            from core.models import MultiTimeframeData
            multi_timeframe_data = market_data['multi_timeframe_data']
            multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis', {})

            multi_tf_analysis = MultiTimeframeData(
                short_term=multi_timeframe_data.get('short_term'),
                medium_term=multi_timeframe_data.get('medium_term'),
                long_term=multi_timeframe_data.get('long_term'),
                overall_trend=multi_timeframe_analysis
            )
            result.multi_timeframe_analysis = multi_tf_analysis

        return result

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
        result = AnalystReport.model_validate(json.loads(response.choices[0].message.content))

        # 如果存在多週期數據，創建多週期分析對象並附加到結果中
        if 'multi_timeframe_data' in market_data:
            from core.models import MultiTimeframeData
            multi_timeframe_data = market_data['multi_timeframe_data']
            multi_timeframe_analysis = market_data.get('multi_timeframe_trend_analysis', {})

            multi_tf_analysis = MultiTimeframeData(
                short_term=multi_timeframe_data.get('short_term'),
                medium_term=multi_timeframe_data.get('medium_term'),
                long_term=multi_timeframe_data.get('long_term'),
                overall_trend=multi_timeframe_analysis
            )
            result.multi_timeframe_analysis = multi_tf_analysis

        return result


# ============================================================================ 
# 第二層：研究團隊 (Research Team) - 進行辯論
# ============================================================================ 

class BullResearcher:
    """多頭研究員 Agent"""

    def __init__(self, client, model: str = None):
        self.client = client
        self.model = model or DEEP_THINKING_MODEL
        self.stance = "Bull"
        print(f"  >> 多頭研究員使用模型: {self.model}")

    def debate(self, analyst_reports: List[AnalystReport], opponent_arguments: List[ResearcherDebate] = [], round_number: int = 1, topic: str = "綜合") -> ResearcherDebate:
        """基於分析師報告提出看漲論點，並回應其他研究員觀點"""

        # 收集對手觀點
        opponents_section = ""
        if opponent_arguments:
            opponents_section = "=== 對手的論點 ===\n"
            for arg in opponent_arguments:
                opponents_section += f"[{arg.researcher_stance} 研究員]: {arg.argument}\n信心度: {arg.confidence}%\n---\n"

        prompt = f"""
你是一位專業的多週期多頭研究員。當前進行的是第 {round_number} 輪辯論，重點辯論主題為：【{topic}】。

分析師報告摘要：
{json.dumps([{"分析師": r.analyst_type, "摘要": r.summary} for r in analyst_reports], indent=2, ensure_ascii=False)}

{opponents_section}

你的任務：
1. 針對當前主題【{topic}】強化看漲論點。
2. **讓步機制**：在對手提出的觀點中，找出一個你認為最合理、最具威脅性的數據或邏輯，並公開承認它。
3. **針對性反駁**：具體指出空頭或中立派在【{topic}】方面的邏輯漏洞或數據誤讀。
4. 解釋為什麼儘管存在上述風險，看漲因素在【{topic}】維度上依然佔據主導地位。

請以 JSON 格式回覆：
- researcher_stance: "Bull"
- argument: 多頭論點 (繁體中文，至少100字，需包含讓步與反駁)
- key_points: 關鍵看漲點列表 (List[str])
- concession_point: 承認對手最有道理的觀點 (字串)
- counter_arguments: 對對手論點的反駁列表 (List[str])
- confidence: 信心度 (0-100)
- round_number: {round_number}
- opponent_view: "Addressing all current opponents"
"""
        try:
            if supports_json_mode(self.model):
                response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
                result_dict = json.loads(response.choices[0].message.content)
            else:
                response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}])
                result_dict = extract_json_from_response(response.choices[0].message.content)
            return ResearcherDebate.model_validate(result_dict)
        except Exception as e:
            return ResearcherDebate(researcher_stance="Bull", argument=f"分析出錯: {str(e)}", key_points=[], confidence=0, round_number=round_number)

class BearResearcher:
    """空頭研究員 Agent"""

    def __init__(self, client, model: str = None):
        self.client = client
        self.model = model or DEEP_THINKING_MODEL
        self.stance = "Bear"
        print(f"  >> 空頭研究員使用模型: {self.model}")

    def debate(self, analyst_reports: List[AnalystReport], opponent_arguments: List[ResearcherDebate] = [], round_number: int = 1, topic: str = "綜合") -> ResearcherDebate:
        """基於分析師報告提出看跌論點，並回應其他研究員觀點"""

        opponents_section = ""
        if opponent_arguments:
            opponents_section = "=== 對手的論點 ===\n"
            for arg in opponent_arguments:
                opponents_section += f"[{arg.researcher_stance} 研究員]: {arg.argument}\n信心度: {arg.confidence}%\n---\n"

        prompt = f"""
你是一位專業的多週期空頭研究員。當前進行的是第 {round_number} 輪辯論，重點辯論主題為：【{topic}】。

分析師報告摘要：
{json.dumps([{"分析師": r.analyst_type, "摘要": r.summary} for r in analyst_reports], indent=2, ensure_ascii=False)}

{opponents_section}

你的任務：
1. 針對當前主題【{topic}】強化看跌論點（識別風險）。
2. **讓步機制**：在多頭或中立派提出的觀點中，找出一個你認為最合理、最難反駁的利多因素，並公開承認它。
3. **針對性反駁**：具體指出多頭在【{topic}】維度上的過度樂觀或盲點。
4. 強調為什麼在【{topic}】維度下，潛在風險比收益更值得關注。

請以 JSON 格式回覆：
- researcher_stance: "Bear"
- argument: 空頭論點 (繁體中文，至少100字，需包含讓步與反駁)
- key_points: 關鍵看跌點列表 (List[str])
- concession_point: 承認對手最有道理的觀點 (字串)
- counter_arguments: 對對手論點的反駁列表 (List[str])
- confidence: 信心度 (0-100)
- round_number: {round_number}
- opponent_view: "Addressing all current opponents"
"""
        try:
            if supports_json_mode(self.model):
                response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
                result_dict = json.loads(response.choices[0].message.content)
            else:
                response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}])
                result_dict = extract_json_from_response(response.choices[0].message.content)
            return ResearcherDebate.model_validate(result_dict)
        except Exception as e:
            return ResearcherDebate(researcher_stance="Bear", argument=f"分析出錯: {str(e)}", key_points=[], confidence=0, round_number=round_number)

class NeutralResearcher:
    """中立/震盪派研究員 Agent (魔鬼代言人)"""

    def __init__(self, client, model: str = None):
        self.client = client
        self.model = model or DEEP_THINKING_MODEL
        self.stance = "Neutral"
        print(f"  >> 中立研究員使用模型: {self.model}")

    def debate(self, analyst_reports: List[AnalystReport], opponent_arguments: List[ResearcherDebate] = [], round_number: int = 1, topic: str = "綜合") -> ResearcherDebate:
        """提出中立/震盪觀點，質疑單邊趨勢"""

        opponents_section = ""
        if opponent_arguments:
            opponents_section = "=== 其他研究員的觀點 ===\n"
            for arg in opponent_arguments:
                opponents_section += f"[{arg.researcher_stance} 研究員]: {arg.argument}\n信心度: {arg.confidence}%\n---\n"

        prompt = f"""
你是一位專業的中立/震盪派研究員。當前進行的是第 {round_number} 輪辯論，重點主題為：【{topic}】。

你的任務：
1. 質疑多頭與空頭是否都對【{topic}】過度預測了方向。
2. 尋找市場在【{topic}】維度下可能陷入橫盤、震盪或波動率收斂的證據。
3. **讓步機制**：承認某一方在特定數據上的正確性，但指出這不代表單邊趨勢的確立。
4. 強調「觀望」或「區間操作」在當前【{topic}】背景下的合理性。

請以 JSON 格式回覆：
- researcher_stance: "Neutral"
- argument: 中立論點 (繁體中文，至少100字)
- key_points: 關鍵中立因素列表 (List[str])
- concession_point: 承認對手最有道理的觀點 (字串)
- counter_arguments: 對單邊趨勢觀點的反駁 (List[str])
- confidence: 信心度 (0-100)
- round_number: {round_number}
- opponent_view: "Questioning both sides"
"""
        try:
            if supports_json_mode(self.model):
                response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
                result_dict = json.loads(response.choices[0].message.content)
            else:
                response = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}])
                result_dict = extract_json_from_response(response.choices[0].message.content)
            return ResearcherDebate.model_validate(result_dict)
        except Exception as e:
            return ResearcherDebate(researcher_stance="Neutral", argument=f"分析出錯: {str(e)}", key_points=[], confidence=0, round_number=round_number)

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
        neutral_argument: Optional[ResearcherDebate],
        fact_checks: Optional[Dict],
        debate_judgment: Optional['DebateJudgment'], # Added
        current_price: float,
        market_data: Dict,
        market_type: str,
        leverage: int,
        feedback: Optional[RiskAssessment] = None,
        account_balance: Optional[Dict] = None
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
        
        account_balance_prompt = ""
        if account_balance:
            account_balance_prompt = f"""
=== 帳戶餘額資訊 ===
總餘額: {account_balance.get('total_balance', 'N/A')} {account_balance.get('currency', '')}
可用餘額: {account_balance.get('available_balance', 'N/A')} {account_balance.get('currency', '')}
**重要**: 你的決策和推理過程**必須**考慮到此帳戶餘額。如果可用餘額為0或很低，你的倉位建議應更加保守或為0。
"""

        fact_check_prompt = ""
        if fact_checks:
            fact_check_prompt = f"""
=== 數據檢察官驗證結果 ===
{json.dumps(fact_checks, indent=2, ensure_ascii=False, default=str)}
**注意**: 如果某方的數據準確性得分較低，請降低該觀點在決策中的權重。
"""

        judge_prompt = ""
        if debate_judgment:
            judge_prompt = f"""
=== 綜合交易委員會 (裁判) 裁決 ===
【裁判總結】: {debate_judgment.key_takeaway}
【裁決理由】: {debate_judgment.judge_rationale}
【公信力得分】: 多頭 {debate_judgment.bull_score} | 空頭 {debate_judgment.bear_score} | 中立 {debate_judgment.neutral_score}
【勝出方】: {debate_judgment.winning_stance}
**核心指導**: 你應該優先相信公信力得分較高的立場。如果裁判判定為 Tie，則表示市場處於高度分歧，應考慮觀望。
"""

        decision_options = ""
        if market_type == 'spot':
            decision_options = "Buy\" / \"Sell\" / \"Hold"
        else: # futures
            decision_options = "Long\" / \"Short\" / \"Hold"

        prompt = f"""
你是一位資深首席交易員。你需要綜合分析師報告、多空辯論、數據核對結果以及裁判的最終裁決來做出最終決策。

當前價格：${current_price:.2f}
市場類型：{market_type}

=== 研究員辯論內容 ===
【多頭】: {bull_argument.argument}
【空頭】: {bear_argument.argument}
【中立】: {neutral_argument.argument if neutral_argument else "無"}

{fact_check_prompt}
{judge_prompt}
{feedback_prompt}
{account_balance_prompt}

你的任務：
1. 權衡多、空、中三方觀點。**必須以裁判的公信力得分為主要參考依據**。
2. 參考數據檢察官的意見，排除掉那些基於錯誤數據的誇大言論。
3. 做出最終決策 ({decision_options}) 並設定具體的交易計劃。

請以 JSON 格式回覆：
- decision: "{decision_options}"
- reasoning: 決策推理 (繁體中文，需提及如何權衡三方觀點及裁判的裁決)
- position_size: 建議倉位 (0-1)
- leverage: 槓桿 (1-125)
- entry_price: 進場價 (float)
- stop_loss: 止損價 (float)
- take_profit: 止盈價 (float)
- confidence: 信心度 (0-100)
- synthesis: 綜合各方意見的總結
"""
        
        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = TraderDecision.model_validate(json.loads(response.choices[0].message.content))

        # 如果存在多週期數據，創建多週期分析對象並附加到結果中
        if 'multi_timeframe_data' in market_data and market_data.get('multi_timeframe_trend_analysis'):
            from core.models import MultiTimeframeData
            multi_timeframe_analysis = MultiTimeframeData(
                short_term=market_data['multi_timeframe_data'].get('short_term'),
                medium_term=market_data['multi_timeframe_data'].get('medium_term'),
                long_term=market_data['multi_timeframe_data'].get('long_term'),
                overall_trend=market_data['multi_timeframe_trend_analysis']
            )
            result.multi_timeframe_analysis = multi_timeframe_analysis

        return result


class DebateJudge:
    """綜合交易委員會裁判 Agent - 評估辯論各方表現"""
    
    def __init__(self, client):
        self.client = client
        
    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def judge(
        self,
        bull_argument: ResearcherDebate,
        bear_argument: ResearcherDebate,
        neutral_argument: ResearcherDebate,
        fact_checks: Dict,
        market_data: Dict
    ) -> 'DebateJudgment':
        """作為公正第三方評估辯論質量與公信力"""
        
        from core.models import DebateJudgment
        
        prompt = f"""
你是一位資深的「綜合交易委員會裁判」。你的任務是審查一場關於市場走勢的三方辯論，並給出公正的裁決分數。

辯論各方論點：
【多頭】: {bull_argument.argument}
【空頭】: {bear_argument.argument}
【中立】: {neutral_argument.argument}

數據檢察官驗證結果：
{json.dumps(fact_checks, indent=2, ensure_ascii=False, default=str)}

你的裁決標準：
1. 邏輯嚴密性：論點是否環環相扣，有無明顯漏洞。
2. 數據準確性：是否尊重事實，有無被檢察官糾正。
3. 讓步客觀性：是否誠實承認對手的合理點（讓步點是否深刻）。
4. 風險意識：是否考慮了潛在的黑天鵝事件或反向因素。

請以 JSON 格式回覆，給出 0-100 的公信力評分：
- bull_score: 多頭公信力評分
- bear_score: 空頭公信力評分
- neutral_score: 中立派公信力評分
- judge_rationale: 裁決理由 (繁體中文，至少100字，需點評各方表現)
- key_takeaway: 你從這場辯論中總結出的最核心事實
- winning_stance: "Bull", "Bear", "Neutral", 或 "Tie"
"""

        response = self.client.chat.completions.create(
            model=DEEP_THINKING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        return DebateJudgment.model_validate(json.loads(response.choices[0].message.content))


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
        
        # 檢查多週期分析數據
        multi_timeframe_context = ""
        if 'multi_timeframe_data' in market_data and market_data.get('multi_timeframe_trend_analysis'):
            trend_analysis = market_data['multi_timeframe_trend_analysis']
            short_term_data = market_data['multi_timeframe_data'].get('short_term', {})
            medium_term_data = market_data['multi_timeframe_data'].get('medium_term', {})
            long_term_data = market_data['multi_timeframe_data'].get('long_term', {})

            multi_timeframe_context = f"""
=== 多週期風險分析 ===
- 短週期趨勢 ({short_term_data.get('timeframe', '1h')}): {trend_analysis.get('short_term_trend', '不明')}
- 中週期趨勢 ({medium_term_data.get('timeframe', '4h')}): {trend_analysis.get('medium_term_trend', '不明')}
- 長週期趨勢 ({long_term_data.get('timeframe', '1d')}): {trend_analysis.get('long_term_trend', '不明')}
- 趨勢一致性: {trend_analysis.get('trend_consistency', '不明')}
- 整體偏向: {trend_analysis.get('overall_bias', '中性')}
- 多週期信心分數: {trend_analysis.get('confidence_score', 0):.1f}%

風險評估考量：
- 當趨勢一致性高時，信號更可靠，風險相對較低
- 當趨勢不一致時，市場方向不明，風險較高
- 多週期分析一致性影響倉位調整決策
"""
        else:
            multi_timeframe_context = "當前為單一週期分析，無多週期趨勢數據。"

        prompt = f"""
你是一位專業的多週期風險管理專家，負責結合不同時間框架的資訊評估並控制交易風險。
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
- 多週期一致性：{'是' if trader_decision.multi_timeframe_analysis else '否'}

{multi_timeframe_context}

市場狀況：
波動率：{market_data.get('市場結構', {}).get('波動率', 'N/A')}%
成交量：{market_data.get('市場結構', {}).get('平均交易量', 'N/A')}
{f"資金費率：{market_data['funding_rate_info'].get('last_funding_rate', 'N/A')}" if market_type == 'futures' and market_data.get('funding_rate_info') else ""}

你的任務：
1. 評估這筆交易的風險等級，特別考慮多週期一致性
2. 檢查倉位、止損、止盈是否合理
3. 決定是否批准或需要調整
{f"4. 對於合約交易，特別評估槓桿帶來的清算風險和資金費率的影響。" if market_type == 'futures' else ""}
5. 根據多週期一致性調整風險評估和倉位建議

**重要決策邏輯**：
- 如果交易計劃合理且風險可控 → approve: true, adjusted_position_size 等於原始倉位
- 如果多週期一致性高，風險較低，可適度提高倉位
- 如果多週期一致性低，市場風險較高，應降低倉位或拒絕
- 如果有明顯風險但可調整 → approve: true, adjusted_position_size 為調整後的倉位
- 如果風險過高無法接受 → approve: false

**adjusted_position_size 設定規則**：
✅ 如果**完全同意**交易員的建議 → adjusted_position_size = {trader_decision.position_size}（與原始倉位相同）
📈 如果多週期**一致性高**，可適當增加倉位 → adjusted_position_size = {min(1.0, trader_decision.position_size * 1.2)}
📉 如果多週期**一致性低**，應降低倉位 → adjusted_position_size = {max(0.01, trader_decision.position_size * 0.7)}
⚠️  如果需要**小幅調整** → adjusted_position_size 調整為合理值（例如降低 10-30%）
❌ 如果**不批准** → approve: false, adjusted_position_size = 0

請以 JSON 格式回覆：
- risk_level: "低風險"/"中低風險"/"中風險"/"中高風險"/"高風險"/"極高風險"
- assessment: 風險評估（繁體中文，至少50個字符，需包含多週期分析考量）
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

        result = RiskAssessment.model_validate(json.loads(response.choices[0].message.content))

        # 如果存在多週期數據，創建多週期分析對象並附加到結果中
        if 'multi_timeframe_data' in market_data and market_data.get('multi_timeframe_trend_analysis'):
            from core.models import MultiTimeframeData
            multi_timeframe_analysis = MultiTimeframeData(
                short_term=market_data['multi_timeframe_data'].get('short_term'),
                medium_term=market_data['multi_timeframe_data'].get('medium_term'),
                long_term=market_data['multi_timeframe_data'].get('long_term'),
                overall_trend=market_data['multi_timeframe_trend_analysis']
            )
            result.multi_timeframe_analysis = multi_timeframe_analysis

        return result

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

        # 檢查多週期分析數據
        multi_timeframe_context = ""
        if trader_decision.multi_timeframe_analysis:
            trend_analysis = trader_decision.multi_timeframe_analysis.overall_trend or {}
            multi_timeframe_context = f"""
=== 多週期分析一致性 ===
- 多週期趨勢一致性: {trend_analysis.get('trend_consistency', '不明')}
- 整體偏向: {trend_analysis.get('overall_bias', '中性')}
- 多週期信心分數: {trend_analysis.get('confidence_score', 0):.1f}%

決策考量：
- 當趨勢一致性高時，信號更可靠，可適當增加信任度
- 當趨勢不一致時，需更加謹慎
- 基於多週期一致性調整最終決策
"""
        else:
            multi_timeframe_context = "當前為單一週期分析，無多週期趨勢數據。"

        prompt = f"""
你是一位專業的多週期基金經理，擁有最終的資金調度權，需結合不同時間框架的資訊做出決策。
當前市場類型是：{market_type}。

交易員建議：
- 決策：{trader_decision.decision}
- 建議倉位：{trader_decision.position_size * 100}%
{f"- 建議槓桿：{trader_decision.leverage}x" if trader_decision.leverage else ""}
- 理由：{trader_decision.reasoning}
- 多週期一致性：{'是' if trader_decision.multi_timeframe_analysis else '否'}

風險管理員評估：
- 風險等級：{risk_assessment.risk_level}
- 評估意見：{risk_assessment.assessment}
- 是否批准：{risk_assessment.approve}
- 調整後倉位：{risk_assessment.adjusted_position_size * 100}%
- 調整幅度：{position_change_pct:.1f}%
- 多週期一致性：{'是' if risk_assessment.multi_timeframe_analysis else '否'}
{f"- 建議調整：{risk_assessment.suggested_adjustments}" if market_type == 'futures' else ""}

{multi_timeframe_context}

決策權重考量：
- **多週期一致性高**：信號更可靠，適當增加決策信心
- **多週期一致性低**：市場方向不明，更加謹慎
- 平衡風險管理員建議與多週期分析一致性

**最終決策邏輯**：
1. 如果風險管理**批准** + 倉位調整幅度 < 5% + 多週期一致性高 → final_decision: "Approve"（完全批准）
2. 如果風險管理**批准** + 倉位調整幅度 5-30% → final_decision: "Amended"（修正後批准）
3. 如果風險管理**批准**但多週期一致性低 → 根據綜合評估決定 Amended 或 Reject
4. 如果風險管理**不批准** → final_decision: "Reject"（拒絕交易）

你的任務：
1. 審核交易員的決策、風險管理員的評估和多週期一致性
2. 根據上述邏輯做出最終決定
3. 確定最終執行的倉位大小與槓桿倍數
4. 考慮多週期分析對決策的影響

請以 JSON 格式回覆：
- approved: true 或 false（是否批准交易）
- final_decision: "Approve" / "Reject" / "Amended" / "Hold"
- final_position_size: 最終批准的倉位（0-1）。通常採用風險管理員建議的 adjusted_position_size。
- approved_leverage: 最終批准的槓桿倍數（整數）。現貨或不交易時為 null。
- execution_notes: 具體的執行注意事項（例如："分批進場"、"嚴格執行止損"）
- rationale: 最終決策的詳細理由（繁體中文，至少 50 字，需包含多週期分析考量）

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

        # 創建最終決策對象
        final_approval = FinalApproval.model_validate(result)

        # 如果交易員或風險管理員有包含多週期分析，也附加到最終決策中
        if trader_decision.multi_timeframe_analysis:
            final_approval.multi_timeframe_analysis = trader_decision.multi_timeframe_analysis

        return final_approval

# ============================================================================
# 委員會模式支援
# ============================================================================

class CommitteeSynthesizer:
    """委員會觀點綜合器 - 將多個模型的觀點整合成一個綜合觀點"""

    def __init__(self, client, model: str = None):
        self.client = client
        self.model = model or DEEP_THINKING_MODEL
        print(f"  >> 綜合模型: {self.model}")

    def synthesize_committee_views(
        self,
        stance: Literal['Bull', 'Bear'],
        committee_arguments: List[ResearcherDebate],
        analyst_reports: List[AnalystReport]
    ) -> ResearcherDebate:
        """綜合委員會成員的觀點"""

        # 收集所有委員會成員的觀點
        all_arguments = []
        all_key_points = []
        all_counter_arguments = []
        avg_confidence = 0.0

        for i, arg in enumerate(committee_arguments, 1):
            all_arguments.append(f"成員 {i}: {arg.argument}")
            all_key_points.extend(arg.key_points)
            all_counter_arguments.extend(arg.counter_arguments)
            avg_confidence += arg.confidence

        avg_confidence = avg_confidence / len(committee_arguments) if committee_arguments else 50.0

        stance_zh = "多頭" if stance == "Bull" else "空頭"

        prompt = f"""
你是一位資深的市場分析綜合專家，負責整合{stance_zh}委員會所有成員的觀點。

委員會共有 {len(committee_arguments)} 位成員，他們的觀點如下：

{chr(10).join(all_arguments)}

所有關鍵點：
{json.dumps(all_key_points, ensure_ascii=False, indent=2)}

所有反駁論點：
{json.dumps(all_counter_arguments, ensure_ascii=False, indent=2)}

平均信心度：{avg_confidence:.1f}%

你的任務：
1. 綜合所有成員的觀點，提煉出核心共識
2. 識別最強有力的論點
3. 去除重複和次要論點
4. 形成一個統一、連貫的{stance_zh}觀點
5. **識別讓步點**：從分析師報告中，找出對我方觀點最不利、最難反駁的證據或數據，予以承認。

請以 JSON 格式回覆：
- researcher_stance: "{stance}"
- argument: 綜合後的{stance_zh}論點 (繁體中文，至少150字)
- key_points: 核心關鍵點列表 (去重後的 3-5 個最重要的點)
- concession_point: 承認最不利的證據或觀點 (字串)
- counter_arguments: 統一的反駁論點列表 (去重後的 3-5 個)
- confidence: 綜合信心度 (基於所有成員的平均信心度調整，0-100)
- round_number: 1
- opponent_view: null
"""

        try:
            if supports_json_mode(self.model):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                result_dict = json.loads(response.choices[0].message.content)
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                result_dict = extract_json_from_response(response.choices[0].message.content)

            return ResearcherDebate.model_validate(result_dict)
        except Exception as e:
            print(f"       >> 綜合失敗: {e}")
            raise

class DataFactChecker:
    """數據檢察官 Agent - 確保論點基於真實數據"""

    def __init__(self, client):
        self.client = client

    def check(self, arguments: List[ResearcherDebate], market_data: Dict) -> Dict[str, FactCheckResult]:
        """核對數據準確性"""
        market_summary = {
            "價格": market_data.get("價格資訊", {}).get("當前價格"),
            "技術指標": market_data.get("技術指標", {}),
            "市場結構": market_data.get("市場結構", {})
        }
        
        args_text = ""
        for a in arguments:
            if a:
                args_text += f"[{a.researcher_stance}]: {a.argument}\n"
        
        prompt = f"""
你是一位嚴格的數據檢察官。你的任務是核對研究員在辯論中引用的數據是否與真實市場數據相符。

真實市場數據：
{json.dumps(market_summary, indent=2, ensure_ascii=False)}

研究員論點：
{args_text}

你的任務：
1. 檢查研究員是否引用了錯誤的數值。
2. 檢查研究員是否對數據進行了嚴重扭曲的解讀。
3. 如果發現錯誤，請具體指出並更正。

請以 JSON 格式回覆，Key 為研究員立場 (Bull/Bear/Neutral)，Value 為 FactCheckResult 結構：
- is_accurate: bool
- corrections: List[str]
- confidence_score: 0-100 (準確度評分)
- comment: 簡短評論
"""
        try:
            response = self.client.chat.completions.create(
                model=FAST_THINKING_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result_dict = json.loads(response.choices[0].message.content)
            validated = {}
            for stance, data in result_dict.items():
                if stance in ['Bull', 'Bear', 'Neutral']:
                    validated[stance] = FactCheckResult.model_validate(data)
            return validated
        except Exception as e:
            print(f"       >> 數據核對出錯: {e}")
            return {}


# ============================================================================

# Merged from core/agent.py (CryptoAgent)

# ============================================================================

CRYPTO_ASSISTANT_PROMPT = """你是一位專業的加密貨幣投資分析助手，同時也是一位友善的 AI 助理。你的名字是 Pi Crypto Insight。

## 你的能力

1. **一般對話**: 你可以回答各種問題，不限於加密貨幣話題。你可以聊天、回答知識問題、提供建議等。

2. **加密貨幣分析**: 你有專業的工具可以分析加密貨幣市場，包括：
   - 即時價格查詢
   - 技術指標分析
   - 新聞面分析
   - 完整投資分析

## 可用工具說明

你有以下工具可以使用：

| 工具名稱 | 功能 | 速度 | 適用情境 |
|---------|------|------|---------|
| `get_crypto_price_tool` | 即時價格查詢 | 最快 (1-2秒) | 「現在多少錢？」「價格是多少？」 |
| `technical_analysis_tool` | 純技術分析 | 快 (3-5秒) | 「RSI 是多少？」「MACD 如何？」「趨勢如何？」 |
| `news_analysis_tool` | 新聞面分析 | 快 (3-5秒) | 「最新新聞是什麼？」「有什麼消息？」 |
| `full_investment_analysis_tool` | 完整投資分析 | 慢 (30秒-2分鐘) | 「可以投資嗎？」「應該買嗎？」「給我完整分析」 |

## 工具選擇策略

請根據用戶問題選擇最合適的工具：

### 1. 價格相關問題 → `get_crypto_price_tool`
- 「BTC 現在多少錢？」
- 「ETH 的價格是多少？」
- 「PI 幣價格？」

### 2. 技術指標問題 → `technical_analysis_tool`
- 「BTC 的 RSI 是多少？」
- 「ETH 超買了嗎？」
- 「SOL 的趨勢如何？」
- 「支撐位在哪裡？」

### 3. 新聞/消息問題 → `news_analysis_tool`
- 「BTC 最近有什麼新聞？」
- 「ETH 有什麼消息？」
- 「市場情緒如何？」

### 4. 投資決策問題 → `full_investment_analysis_tool`
- 「BTC 可以投資嗎？」
- 「應該買入 ETH 嗎？」
- 「SOL 值得做多嗎？」
- 「給我完整的分析報告」
- 「幫我分析一下 PI」（如果用戶沒指定類型，且看起來想要投資建議）

### 5. 一般問題 → 不需要工具，直接回答
- 「什麼是 RSI？」
- 「如何看 MACD？」
- 「你好」
- 「謝謝」
- 任何非即時數據相關的問題

## 重要原則

1. **選擇最輕量的工具**: 如果只是問價格，不要用完整分析工具。用戶問 RSI，不需要跑完整投資分析。

2. **確認幣種**:
   - 如果用戶提到「它」、「這個幣」、「剛才那個」，請根據對話上下文推斷是指哪個幣種。
   - 如果無法確定，請禮貌地詢問：「請問您是指哪個加密貨幣呢？」

3. **說明等待時間**: 在調用 `full_investment_analysis_tool` 前，先告知用戶：「正在為您進行完整分析，這可能需要 30 秒到 2 分鐘，請稍候...」

4. **錯誤處理**: 如果工具返回錯誤，友善地告知用戶並提供替代建議。

5. **語言**: 請使用繁體中文回應，除非用戶使用其他語言。

6. **風險提示**: 在給出投資建議時，適當加上風險提示。

7. **引用來源**: 當工具返回包含網址 (URL) 的新聞或數據來源時，**必須**在回應的最後方保留這些連結，作為「參考資料」。不要移除或摘要這些連結。

## 對話風格

- 專業但友善
- 簡潔明瞭
- 必要時提供補充說明
- 使用表格和 Markdown 格式使回答更易讀
- **最後必須附上參考資料連結** (如果有)

## 範例對話

**用戶**: BTC 現在多少錢？
**助手**: [使用 get_crypto_price_tool] 返回價格資訊

**用戶**: RSI 是多少？
**助手**: [根據上下文知道是 BTC，使用 technical_analysis_tool] 返回技術分析

**用戶**: 可以買嗎？
**助手**: 「正在為您進行完整分析，請稍候...」[使用 full_investment_analysis_tool] 返回完整分析

**用戶**: 什麼是布林帶？
**助手**: [不需要工具，直接解釋布林帶的概念]

現在，請根據用戶的問題，決定是否需要使用工具，並給出專業且友善的回應。
"""


# ============================================================================
# Agent 建立函式
# ============================================================================

def create_crypto_agent(
    model_name: str = None,
    temperature: float = 0.3,
    verbose: bool = False
):
    """
    創建加密貨幣分析 Agent

    Args:
        model_name: 使用的模型名稱，預設使用 QUERY_PARSER_MODEL
        temperature: 溫度參數
        verbose: 是否顯示詳細日誌

    Returns:
        LangGraph Agent 實例
    """

    # 初始化 LLM
    llm = ChatOpenAI(
        model=model_name or QUERY_PARSER_MODEL,
        temperature=temperature,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # 獲取工具
    tools = get_crypto_tools()

    # 使用 langgraph 創建 ReAct Agent
    # create_react_agent 會自動處理工具調用和對話流程
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=CRYPTO_ASSISTANT_PROMPT  # 系統提示詞
    )

    return agent


# ============================================================================
# CryptoAgent 封裝類
# ============================================================================

class CryptoAgent:
    """加密貨幣分析 Agent 封裝類"""

    def __init__(
        self,
        model_name: str = None,
        temperature: float = 0.3,
        verbose: bool = False
    ):
        """
        初始化 CryptoAgent

        Args:
            model_name: 使用的模型名稱
            temperature: 溫度參數
            verbose: 是否顯示詳細日誌
        """
        self.agent = create_crypto_agent(model_name, temperature, verbose)
        self.chat_history: List = []
        self.last_symbol: Optional[str] = None  # 追蹤最後提到的幣種
        self.verbose = verbose

    def chat(self, user_input: str) -> str:
        """
        與 Agent 對話

        Args:
            user_input: 用戶輸入

        Returns:
            Agent 回應
        """
        try:
            # 構建消息列表
            messages = self.chat_history + [HumanMessage(content=user_input)]

            # 執行 Agent (langgraph 使用 invoke 方法)
            result = self.agent.invoke({"messages": messages})

            # 從結果中提取最後的 AI 消息
            response = ""
            tool_outputs = []
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content and not response:
                        response = msg.content
                    # 收集工具的原始輸出
                    if hasattr(msg, 'tool_name') or (hasattr(msg, 'type') and msg.type == 'tool'):
                        tool_outputs.append(msg.content)

            # --- [新增] 自動提取網址並附加參考資料區 ---
            references = self._extract_references_from_tools(tool_outputs)
            if references:
                response += "\n\n---\n### 📚 相關連接\n"
                for i, url in enumerate(references, 1):
                    response += f"{i}.{url}\n\n"

            # 更新對話歷史
            self.chat_history.append(HumanMessage(content=user_input))
            self.chat_history.append(AIMessage(content=response))

            # 限制歷史長度（避免 context 過長）
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]

            # 嘗試從對話中提取幣種（用於上下文追蹤）
            self._extract_symbol(user_input)

            return response

        except Exception as e:
            error_msg = f"處理請求時發生錯誤: {str(e)}"
            print(f"[CryptoAgent Error] {error_msg}")
            import traceback
            if self.verbose:
                traceback.print_exc()
            return f"抱歉，處理您的請求時發生了一些問題。請稍後再試，或換一種方式提問。\n\n錯誤詳情: {str(e)}"

    def chat_stream(self, user_input: str):
        """
        與 Agent 對話（串流模式）

        Args:
            user_input: 用戶輸入

        Yields:
            逐步生成的回應文字
        """
        try:
            # 構建消息列表
            messages = self.chat_history + [HumanMessage(content=user_input)]

            # 執行 Agent
            result = self.agent.invoke({"messages": messages})

            # 從結果中提取最後的 AI 消息
            response = ""
            tool_outputs = []
            if "messages" in result:
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content and not response:
                        response = msg.content
                    if hasattr(msg, 'tool_name') or (hasattr(msg, 'type') and msg.type == 'tool'):
                        tool_outputs.append(msg.content)

            if not response:
                response = "抱歉，我無法處理這個請求。"

            # --- [新增] 自動提取網址並附加參考資料區 ---
            references = self._extract_references_from_tools(tool_outputs)
            if references:
                response += "\n\n---\n### 📚 相關連接\n"
                for i, url in enumerate(references, 1):
                    response += f"{i}.{url}\n\n"

            # 更新對話歷史
            self.chat_history.append(HumanMessage(content=user_input))
            self.chat_history.append(AIMessage(content=response))

            # 限制歷史長度
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]

            # 嘗試從對話中提取幣種
            self._extract_symbol(user_input)

            yield response

        except Exception as e:
            import traceback
            if self.verbose:
                traceback.print_exc()
            yield f"抱歉，處理您的請求時發生了一些問題: {str(e)}"

    def _extract_references_from_tools(self, tool_outputs: List[str]) -> List[str]:
        """從工具輸出中提取唯一網址"""
        import re
        seen_urls = set()
        urls = []
        
        for output in tool_outputs:
            if not isinstance(output, str): continue
            
            # 匹配所有 http/https 網址
            found_urls = re.findall(r'(https?://[^\s\)\"\'>\]]+)', output)
            for url in found_urls:
                # 移除網址末尾可能存在的標點符號 (例如 Markdown 的括號)
                clean_url = url.split(')')[0].split(']')[0].rstrip(',. ')
                if clean_url not in seen_urls and len(clean_url) > 10:
                    urls.append(clean_url)
                    seen_urls.add(clean_url)
        
        return urls

    def _extract_symbol(self, text: str) -> Optional[str]:
        """從文字中提取幣種符號"""
        import re
        # 常見的加密貨幣符號
        crypto_pattern = r'\b(BTC|ETH|SOL|XRP|ADA|DOGE|DOT|MATIC|LINK|AVAX|ATOM|UNI|LTC|BCH|SHIB|PI|PIUSDT|BTCUSDT|ETHUSDT)\b'
        matches = re.findall(crypto_pattern, text.upper())
        if matches:
            # 清理符號
            symbol = matches[0].replace("USDT", "")
            self.last_symbol = symbol
            return symbol
        return None

    def clear_history(self):
        """清除對話歷史"""
        self.chat_history = []
        self.last_symbol = None

    def get_last_symbol(self) -> Optional[str]:
        """獲取最後提到的幣種"""
        return self.last_symbol


# ============================================================================
# 便捷函式
# ============================================================================

def quick_chat(message: str, verbose: bool = False) -> str:
    """
    快速對話（無狀態，每次創建新 Agent）

    Args:
        message: 用戶消息
        verbose: 是否顯示詳細日誌

    Returns:
        Agent 回應
    """
    agent = CryptoAgent(verbose=verbose)
    return agent.chat(message)


# ============================================================================
# 測試代碼
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Pi Crypto Insight - Agent 測試模式")
    print("=" * 60)

    # 創建 Agent
    agent = CryptoAgent(verbose=True)

    # 測試對話
    test_queries = [
        "你好！",
        "BTC 現在多少錢？",
        "它的 RSI 是多少？",
        "什麼是 MACD？",
        "PI 幣最近有什麼新聞？",
    ]

    for query in test_queries:
        print(f"\n{'=' * 40}")
        print(f"用戶: {query}")
        print("-" * 40)
        response = agent.chat(query)
        print(f"助手: {response}")
        print("=" * 40)