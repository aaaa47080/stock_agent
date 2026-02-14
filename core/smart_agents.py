import json
from typing import Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

from core.models import AnalystReport
from core.agents import TechnicalAnalyst
from core.tools.crypto_tools import technical_analysis_tool
from utils.llm_client import extract_json_from_response


class SmartTechnicalAnalyst(TechnicalAnalyst):
    """
    智能技術分析師 Agent (具備工具使用能力)
    繼承自 TechnicalAnalyst，但重寫了 analyze 方法以使用工具。
    """

    def __init__(self, client):
        super().__init__(client)
        self.role = "智能技術分析師"

        # 初始化工具
        self.tools = [technical_analysis_tool]

        # 獲取 ReAct Prompt (或自定義)
        # 這裡我們使用一個簡單的 System Prompt 配合工具
        # 注意: LangChain 的 create_react_agent 需要特定的 prompt 格式
        # 我們可以使用 hwchase17/react-json 或類似的，或者自定義
        self.prompt = hub.pull("hwchase17/react")

        # 創建 Agent
        self.agent = create_react_agent(self.client, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(
            agent=self.agent, tools=self.tools, verbose=True, handle_parsing_errors=True
        )

    def analyze(self, market_data: Dict) -> AnalystReport:
        """
        使用工具進行分析。
        與原始方法不同，這裡我們不依賴 market_data 中的預加載指標，
        而是讓 Agent 自行決定是否調用工具獲取最新數據。
        """
        symbol = market_data.get(
            "symbol"
        )  # 假設 market_data 包含 symbol，如果沒有則需從 context 獲取
        interval = market_data.get("interval", "1d")

        # 如果 market_data 沒有 symbol (因為它是 klines 數據包)，我們需要從外部傳入或推斷
        # 這裡為了演示，我們假設調用者會傳入包含元數據的 market_data

        if not symbol:
            # Fallback to original logic if no symbol provided (or error)
            print("⚠️ SmartTechnicalAnalyst: 缺少 symbol，回退到原始分析邏輯")
            return super().analyze(market_data)

        print(f"🤖 SmartTechnicalAnalyst正在分析 {symbol} ({interval})...")

        # 構建 Prompt
        query = f"""
        你是一位專業的智能技術分析師。
        請對 {symbol} 進行 {interval} 級別的技術分析。
        
        你擁有 `technical_analysis_tool` 工具，請務必使用它來獲取最新的技術指標數據 (RSI, MACD, 均線等)。
        不要憑空猜測數據。
        
        獲取數據後，請根據數據生成一份詳細的分析報告。
        
        最後的回答必須是符合以下 JSON 格式的字串 (不要用 Markdown code block 包裹，直接返回 JSON):
        {{
            "analyst_type": "技術分析師",
            "summary": "分析摘要 (繁體中文，至少50字)",
            "key_findings": ["關鍵發現1", "關鍵發現2"],
            "bullish_points": ["看漲點1", "看漲點2"],
            "bearish_points": ["看跌點1", "看跌點2"],
            "confidence": 信心度數值 (0-100)
        }}
        """

        try:
            # 執行 Agent
            result = self.agent_executor.invoke({"input": query})
            output = result.get("output", "")

            # 嘗試解析 JSON
            parsed_result = extract_json_from_response(output)
            return AnalystReport.model_validate(parsed_result)

        except Exception as e:
            print(f"❌ SmartTechnicalAnalyst 分析失敗: {e}")
            # Fallback
            return super().analyze(market_data)
