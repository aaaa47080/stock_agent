"""
一般對話 Agent

職責：處理問候、閒聊和一般問題
"""
from typing import Tuple, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from ..base import SubAgent
from ..models import Task, AgentResult


class ChatAgent(SubAgent):
    """
    一般對話 Agent

    職責：
    - 處理問候和打招呼
    - 進行自然對話
    - 回答關於系統功能的問題
    - 引導使用者到專業功能
    """

    SHOULD_PARTICIPATE_PROMPT = """判斷以下任務是否需要一般對話功能。

任務：{query}
類型：{task_type}

如果任務涉及以下內容，應該參與：
- 問候、打招呼
- 閒聊
- 詢問系統功能
- 無法歸類到其他專業的請求

只回答 YES 或 NO，然後簡短說明理由。"""

    CHAT_SYSTEM_PROMPT = """你是 Agent V3，一個友善的加密貨幣分析助手。

你的主要專長是加密貨幣分析，但你也可以進行自然對話。

特點：
- 語氣友善、專業
- 使用繁體中文
- 適時引導使用者到你的專業功能

你可以幫使用者：
- 分析加密貨幣（BTC, ETH, SOL, PI 等）
- 獲取最新新聞
- 進行技術分析
- 提供市場洞察

重要：你無法處理的事情：
- 天氣查詢
- 訂票訂房
- 網購或支付
- 其他與加密貨幣無關的功能

當使用者問超出你能力範圍的問題時：
1. 直接友善地說明你無法幫忙
2. 不要假裝可以處理
3. 不要一直問問題
4. 引導使用者到你能幫助的領域

範例回應：
- 天氣：「抱歉，我無法查詢天氣。但我可以幫你分析加密貨幣市場！想了解哪個幣種？」
- 訂票：「我沒有訂票功能，不過如果你想了解加密貨幣，隨時可以問我！」"""

    CONTEXT_PROMPT = """
對話歷史：
{history}

當前使用者輸入：{query}

請判斷：
1. 這個問題是否在我的能力範圍內？
2. 如果超出範圍，直接說明並引導
3. 如果在範圍內，友善回覆

請用繁體中文簡短回覆（2-3 句話）。
保持友善，但不要假裝能做到你做不到的事。"""

    @property
    def name(self) -> str:
        return "ChatAgent"

    @property
    def expertise(self) -> str:
        return "general"

    @property
    def description(self) -> str:
        return "一般對話 Agent，處理問候、閒聊和系統功能介紹"

    @property
    def responsibilities(self) -> str:
        return """
        1. 進行自然對話
        2. 回答關於系統功能的問題
        3. 引導使用者到專業功能
        4. 處理無法歸類的請求
        保持友善和專業。
        """

    def should_participate(self, task: Task) -> Tuple[bool, str]:
        """判斷是否參與此任務"""
        prompt = self.SHOULD_PARTICIPATE_PROMPT.format(
            query=task.query,
            task_type=task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type)
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.upper()
            should_join = "YES" in content
            reason = response.content.split("\n")[0] if "\n" in response.content else response.content
            return (should_join, reason)

        except Exception as e:
            # ChatAgent 是 fallback，預設參與
            return (True, f"預設參與（判斷錯誤：{e}）")

    def execute(self, task: Task) -> AgentResult:
        """
        執行對話任務

        流程：
        1. 構建上下文
        2. 調用 LLM 生成回覆
        """
        self._observations = []

        # 構建對話歷史
        history = self._build_history(task)

        # 生成回覆
        prompt = self.CONTEXT_PROMPT.format(
            history=history,
            query=task.query
        )

        try:
            messages = [
                SystemMessage(content=self.CHAT_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            reply = response.content

            self._add_observation(f"生成回覆成功")

            return AgentResult(
                success=True,
                message=reply,
                agent_name=self.name,
                observations=self._observations
            )

        except Exception as e:
            # Fallback 回覆
            self._add_observation(f"生成回覆失敗: {e}")

            return AgentResult(
                success=True,
                message=self._fallback_reply(task.query),
                agent_name=self.name,
                observations=self._observations
            )

    def _build_history(self, task: Task) -> str:
        """構建對話歷史"""
        if not hasattr(task, 'context') or not task.context:
            return "這是新對話的開始"

        history = task.context.get('history', [])
        if not history:
            return "這是新對話的開始"

        lines = []
        for msg in history[-6:]:  # 最近 3 輪對話
            role = "使用者" if msg.get('role') == 'user' else "助手"
            content = msg.get('content', '')[:100]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _fallback_reply(self, query: str) -> str:
        """Fallback 回覆"""
        # 簡單的規則匹配
        query_lower = query.lower()

        if any(word in query_lower for word in ['你好', '嗨', 'hi', 'hello', '哈囉']):
            return "你好！我是 Agent V3 加密貨幣分析助手。有什麼可以幫你的嗎？"

        if any(word in query_lower for word in ['功能', '能做', 'help', '幫助']):
            return """我可以幫你：
- 📰 查詢加密貨幣最新新聞
- 📊 進行技術分析
- 💡 提供市場洞察

試試問我「BTC 最新新聞」或「分析 ETH」！"""

        if any(word in query_lower for word in ['天氣', '天氣']):
            return "抱歉，我無法查詢天氣。但我可以幫你分析加密貨幣市場！試試問我「BTC 怎麼樣」？"

        # 預設回覆
        return "我是一個加密貨幣分析助手。雖然我不太確定你的問題，但如果你想了解加密貨幣，隨時可以問我！"
