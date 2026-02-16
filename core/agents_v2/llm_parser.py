"""
LLM Task Parser - 使用 LLM 进行语义解析，替代硬编码规则

这个模块用 LLM 来理解用户意图，而不是用 if "关键词" in query 的规则匹配。
"""
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from .task import Task, TaskType, ParsedIntent
from utils.llm_client import extract_json_from_response


class LLMTaskParser:
    """
    使用 LLM 进行语义解析

    替代所有硬编码的规则匹配：
    - 任务类型判断
    - 符号提取（不依赖硬编码列表）
    - 分析深度判断
    - 回测需求判断
    """

    PARSE_PROMPT = """你是一個意圖解析器。分析用戶的查詢，提取以下信息。

用戶查詢：{query}

請以 JSON 格式回覆：
{{
    "symbols": ["提取的交易符號（大寫，如 BTC, ETH）"],
    "task_type": "simple_price 或 analysis 或 deep_analysis",
    "depth": "quick 或 normal 或 deep",
    "needs_backtest": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "簡短說明你的判斷理由"
}}

判斷標準：
- task_type:
  - simple_price: 只是問價格（如「BTC多少」「現價」）
  - analysis: 一般分析請求
  - deep_analysis: 需要深度分析、多空辯論、完整報告

- depth:
  - quick: 快速、簡單、概略
  - normal: 標準分析
  - deep: 深度、詳細、完整

- needs_backtest: 是否提到歷史、回測、過去表現

- symbols: 提取所有提到的加密貨幣或股票符號，轉成大寫

如果沒有明確提到符號，symbols 可以為空陣列。
只回覆 JSON，不要其他內容。"""

    def __init__(self, llm_client: BaseChatModel):
        """
        初始化 Parser

        Args:
            llm_client: LangChain BaseChatModel 實例
        """
        self.client = llm_client

    def parse(self, query: str) -> ParsedIntent:
        """
        使用 LLM 解析用戶查詢

        Args:
            query: 用戶輸入

        Returns:
            ParsedIntent: 解析結果
        """
        prompt = self.PARSE_PROMPT.format(query=query)

        try:
            response = self.client.invoke([HumanMessage(content=prompt)])
            json_data = extract_json_from_response(response.content)

            parsed = ParsedIntent.model_validate(json_data)

            # 標準化 task_type
            parsed.task_type = self._normalize_task_type(parsed.task_type)

            # 標準化 depth
            parsed.depth = self._normalize_depth(parsed.depth)

            # 標準化 symbols（確保大寫）
            parsed.symbols = [s.upper() for s in parsed.symbols if s]

            return parsed

        except Exception as e:
            # Fallback: 返回默認值
            return ParsedIntent(
                symbols=[],
                task_type="analysis",
                depth="normal",
                needs_backtest=False,
                confidence=0.0,
                reasoning=f"LLM 解析失敗: {str(e)}"
            )

    def _normalize_task_type(self, task_type: str) -> str:
        """標準化任務類型"""
        task_type = task_type.lower().strip()

        if "simple" in task_type or "price" in task_type:
            return "simple_price"
        elif "deep" in task_type:
            return "deep_analysis"
        else:
            return "analysis"

    def _normalize_depth(self, depth: str) -> str:
        """標準化分析深度"""
        depth = depth.lower().strip()

        if "quick" in depth or "fast" in depth or "簡單" in depth:
            return "quick"
        elif "deep" in depth or "detail" in depth or "詳細" in depth or "完整" in depth:
            return "deep"
        else:
            return "normal"

    def extract_symbols(self, query: str) -> list[str]:
        """
        提取交易符號

        Args:
            query: 用戶輸入

        Returns:
            符號列表（大寫）
        """
        parsed = self.parse(query)
        return parsed.symbols

    def determine_task_type(self, query: str) -> TaskType:
        """
        判斷任務類型

        Args:
            query: 用戶輸入

        Returns:
            TaskType 枚舉
        """
        parsed = self.parse(query)

        type_map = {
            "simple_price": TaskType.SIMPLE_PRICE,
            "analysis": TaskType.ANALYSIS,
            "deep_analysis": TaskType.DEEP_ANALYSIS,
        }

        return type_map.get(parsed.task_type, TaskType.ANALYSIS)

    def to_task(self, query: str) -> Task:
        """
        直接將查詢轉換為 Task 對象

        Args:
            query: 用戶輸入

        Returns:
            Task 對象
        """
        parsed = self.parse(query)

        task_type_map = {
            "simple_price": TaskType.SIMPLE_PRICE,
            "analysis": TaskType.ANALYSIS,
            "deep_analysis": TaskType.DEEP_ANALYSIS,
        }

        return Task(
            query=query,
            type=task_type_map.get(parsed.task_type, TaskType.ANALYSIS),
            symbols=parsed.symbols if parsed.symbols else ["BTC"],  # 默認 BTC
            analysis_depth=parsed.depth,
            needs_backtest=parsed.needs_backtest,
            context={
                "confidence": parsed.confidence,
                "reasoning": parsed.reasoning,
            }
        )
