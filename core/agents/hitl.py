"""
Agent V4 — Human-In-The-Loop Manager

Provides ask(), ask_satisfaction(), reset(), get_history().
Copied V3 ask()/reset() logic verbatim, stripped LLM-based methods.
"""
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class QARecord:
    question: str
    response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class HITLManager:
    def __init__(self, max_questions_per_session: int = 10):
        self.max_questions = max_questions_per_session
        self._qa_history: List[QARecord] = []
        self._question_count: int = 0

    def ask(self, question: str, options: List[str] = None) -> str:
        """
        向使用者提問並等待回應 (copied from V3 EnhancedHITLManager.ask)

        在 CLI 環境中直接列印並等待輸入
        在非交互式環境中返回空字串
        """
        import sys
        if not sys.stdin.isatty():
            return ""

        # 顯示問題
        print(f"\n🤔 {question}")
        if options:
            for i, opt in enumerate(options, 1):
                print(f"   {i}. {opt}")
        print()

        try:
            response = input("你的回答 > ").strip()

            # 處理選項輸入
            if options and response.isdigit():
                idx = int(response) - 1
                if 0 <= idx < len(options):
                    response = options[idx]

            # 記錄回應
            self._record_response(question, response)
            return response

        except (EOFError, KeyboardInterrupt):
            return ""

    def ask_satisfaction(self, report: str) -> tuple:
        """Returns (satisfied: bool, feedback: str)"""
        print(f"\n{report}\n")
        answer = self.ask("這個結果符合您的需求嗎？", options=["滿意", "不滿意，需要補充"])
        if answer in ["滿意", "1"]:
            return (True, "")
        feedback = self.ask("請說明哪裡不夠好，或需要補充什麼：")
        return (False, feedback)

    def reset(self) -> None:
        """重置會話"""
        self._qa_history.clear()
        self._question_count = 0

    def get_history(self, limit: int = 20) -> List[dict]:
        """獲取問答歷史"""
        recent = self._qa_history[-limit:]
        return [
            {
                "question": r.question,
                "response": r.response,
                "time": r.timestamp,
            }
            for r in recent
        ]

    def _record_response(self, question: str, response: str) -> None:
        """記錄問答"""
        record = QARecord(question=question, response=response)
        self._qa_history.append(record)
        self._question_count += 1
