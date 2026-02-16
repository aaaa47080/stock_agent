"""
Agent V3 增強版 Human-in-the-Loop (HITL) Manager

由 LLM 決定何時需要詢問使用者，而非固定時機
"""
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage

from .models import HITLTriggerType, ConversationContext


@dataclass
class HITLQuestion:
    """HITL 問題定義"""
    question: str
    question_type: HITLTriggerType
    context: Dict[str, Any] = field(default_factory=dict)
    options: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class HITLResponse:
    """HITL 回應記錄"""
    question: HITLQuestion
    user_response: str
    responded_at: datetime = field(default_factory=datetime.now)


class EnhancedHITLManager:
    """
    增強版 Human-in-the-Loop Manager

    與原版不同：
    1. 由 LLM 決定是否需要詢問使用者
    2. 支援多種詢問類型
    3. 記錄使用者回饋用於學習
    4. 可配置詢問策略
    """

    SHOULD_ASK_PROMPT = """你是一個智慧助手，負責判斷是否需要向使用者詢問更多資訊。

重要：這是一個加密貨幣分析系統，只能處理：
- 加密貨幣相關問題（價格、新聞、技術分析）
- 一般對話和問候

系統無法處理：
- 天氣查詢
- 訂票訂房
- 網購或支付
- 其他與加密貨幣無關的功能

當前對話上下文：
{context}

當前狀態：{state}

請判斷：
1. 使用者的請求是否在系統能力範圍內？
2. 如果超出能力範圍，should_ask 必須為 false
3. 如果在能力範圍內但資訊不足，是否需要詢問？

問題類型說明：
- info_needed: 需要更多資訊（如缺少幣種名稱）
- preference: 詢問使用者偏好（如分析深度）
- confirmation: 確認重要決策
- satisfaction: 詢問滿意度
- clarification: 澄清模糊的問題

請以 JSON 格式回覆：
{{
    "should_ask": true/false,
    "question": "問題內容（如果 should_ask 為 true）",
    "type": "問題類型",
    "reason": "為什麼需要（或不需要）詢問",
    "out_of_scope": true/false
}}
"""

    ASK_QUESTION_PROMPT = """根據上下文，生成一個友善的問題來詢問使用者。

上下文：{context}
問題類型：{question_type}
目的：{purpose}

請生成一個：
1. 簡潔明瞭的問題
2. 語氣友善
3. 使用繁體中文

只回覆問題本身，不要其他內容。"""

    def __init__(
        self,
        llm_client,
        auto_ask_threshold: float = 0.7,
        max_questions_per_session: int = 5
    ):
        """
        初始化 HITL Manager

        Args:
            llm_client: LangChain LLM 客戶端
            auto_ask_threshold: 自動詢問的信心度閾值
            max_questions_per_session: 每個會話最多詢問次數
        """
        self.llm = llm_client
        self.auto_ask_threshold = auto_ask_threshold
        self.max_questions = max_questions_per_session

        # 當前待處理的問題
        self._pending_question: Optional[HITLQuestion] = None
        # 問答歷史
        self._qa_history: List[HITLResponse] = []
        # 會話統計
        self._session_stats = {
            "total_questions": 0,
            "total_responses": 0,
            "by_type": {}
        }

    def should_ask_user(
        self,
        context: ConversationContext,
        current_state: str = "processing"
    ) -> Tuple[bool, str, HITLTriggerType]:
        """
        使用 LLM 判斷是否需要詢問使用者

        Args:
            context: 對話上下文
            current_state: 當前處理狀態

        Returns:
            (should_ask: bool, question: str, question_type: HITLTriggerType)
        """
        # 檢查是否超過最大詢問次數
        if self._session_stats["total_questions"] >= self.max_questions:
            return (False, "", HITLTriggerType.INFO_NEEDED)

        prompt = self.SHOULD_ASK_PROMPT.format(
            context=context.to_prompt_string(),
            state=current_state
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = self._parse_response(response.content)

            should_ask = result.get("should_ask", False)
            question = result.get("question", "")
            q_type = self._parse_question_type(result.get("type", "info_needed"))

            return (should_ask, question, q_type)

        except Exception as e:
            print(f"[HITL] 判斷錯誤: {e}")
            return (False, "", HITLTriggerType.INFO_NEEDED)

    def ask(
        self,
        question: str,
        question_type: HITLTriggerType = HITLTriggerType.INFO_NEEDED,
        options: List[str] = None
    ) -> str:
        """
        向使用者提問並等待回應

        在 CLI 環境中直接列印並等待輸入
        在非交互式環境中返回空字串

        Args:
            question: 問題內容
            question_type: 問題類型
            options: 選項列表（可選）

        Returns:
            使用者的回應（非交互式環境返回空字串）
        """
        # 檢查是否在交互式環境中
        import sys
        if not sys.stdin.isatty():
            # 非交互式環境，跳過詢問
            return ""

        # 創建問題記錄
        q = HITLQuestion(
            question=question,
            question_type=question_type,
            options=options or []
        )
        self._pending_question = q

        # 顯示問題
        print(f"\n🤔 {question}")
        if options:
            for i, opt in enumerate(options, 1):
                print(f"   {i}. {opt}")
        print()

        try:
            # 等待使用者輸入（設置超時）
            response = input("你的回答 > ").strip()

            # 處理選項輸入
            if options and response.isdigit():
                idx = int(response) - 1
                if 0 <= idx < len(options):
                    response = options[idx]

            # 記錄回應
            self._record_response(q, response)

            return response

        except (EOFError, KeyboardInterrupt):
            # 無法讀取輸入，返回空字串
            return ""

    def ask_if_needed(
        self,
        context: ConversationContext,
        current_state: str = "processing"
    ) -> Tuple[bool, str]:
        """
        如果需要則詢問使用者

        結合 should_ask_user 和 ask 的便捷方法

        Args:
            context: 對話上下文
            current_state: 當前狀態

        Returns:
            (asked: bool, response: str)
        """
        should_ask, question, q_type = self.should_ask_user(context, current_state)

        if should_ask and question:
            response = self.ask(question, q_type)
            return (True, response)

        return (False, "")

    def generate_question(
        self,
        purpose: str,
        question_type: HITLTriggerType,
        context: str = ""
    ) -> str:
        """
        讓 LLM 生成問題

        Args:
            purpose: 問題目的
            question_type: 問題類型
            context: 上下文資訊

        Returns:
            生成的問題
        """
        prompt = self.ASK_QUESTION_PROMPT.format(
            context=context,
            question_type=question_type.value,
            purpose=purpose
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            print(f"[HITL] 生成問題錯誤: {e}")
            return f"請提供更多關於「{purpose}」的資訊"

    def get_pending_question(self) -> Optional[HITLQuestion]:
        """獲取當前待處理的問題"""
        return self._pending_question

    def has_pending_question(self) -> bool:
        """是否有待處理的問題"""
        return self._pending_question is not None

    def clear_pending(self) -> None:
        """清除待處理問題"""
        self._pending_question = None

    def get_history(self, limit: int = 20) -> List[dict]:
        """
        獲取問答歷史

        Args:
            limit: 返回記錄數量限制

        Returns:
            問答記錄列表
        """
        recent = self._qa_history[-limit:]
        return [
            {
                "question": r.question.question,
                "type": r.question.question_type.value,
                "response": r.user_response,
                "time": r.responded_at.isoformat()
            }
            for r in recent
        ]

    def get_stats(self) -> dict:
        """獲取統計資訊"""
        return self._session_stats.copy()

    def reset(self) -> None:
        """重置會話"""
        self._pending_question = None
        self._qa_history.clear()
        self._session_stats = {
            "total_questions": 0,
            "total_responses": 0,
            "by_type": {}
        }

    def _record_response(self, question: HITLQuestion, response: str) -> None:
        """記錄問答"""
        record = HITLResponse(question=question, user_response=response)
        self._qa_history.append(record)

        # 更新統計
        self._session_stats["total_questions"] += 1
        self._session_stats["total_responses"] += 1

        type_key = question.question_type.value
        self._session_stats["by_type"][type_key] = \
            self._session_stats["by_type"].get(type_key, 0) + 1

        self._pending_question = None

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 回應為 JSON"""
        import json
        import re

        # 嘗試提取 JSON
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        # 解析失敗，返回默認值
        return {
            "should_ask": False,
            "question": "",
            "type": "info_needed",
            "reason": "無法解析 LLM 回應"
        }

    def _parse_question_type(self, type_str: str) -> HITLTriggerType:
        """解析問題類型"""
        type_map = {
            "info_needed": HITLTriggerType.INFO_NEEDED,
            "preference": HITLTriggerType.PREFERENCE,
            "confirmation": HITLTriggerType.CONFIRMATION,
            "satisfaction": HITLTriggerType.SATISFACTION,
            "clarification": HITLTriggerType.CLARIFICATION,
        }

        type_lower = type_str.lower().strip()
        return type_map.get(type_lower, HITLTriggerType.INFO_NEEDED)
