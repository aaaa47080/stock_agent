"""
Agent V4 — Chat Agent

一般對話 Agent: 處理問候、閒聊、系統說明，是所有未知請求的 fallback。
也處理簡單的價格查詢（使用 get_crypto_price 工具）。
Supports multi-language responses.
"""
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)


class ChatAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "chat"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute chat/conversation task."""
        query = task.description
        language = (task.context or {}).get("language", "zh-TW")  # 獲取用戶語言偏好

        # Check if this is a price query (via tool_hint or keyword detection)
        if self._is_price_query(task, query):
            return self._handle_price_query(query, task, language)

        # Build system prompt from registry (use render so {current_time_tw} gets filled)
        system_prompt = PromptRegistry.render("chat_agent", "system", language)

        # Build response prompt
        history = "這是新對話的開始" if language == "zh-TW" else "This is the start of a new conversation"
        memory_facts = "無" if language == "zh-TW" else "None"
        agent_failures = ""
        if hasattr(task, "context") and task.context:
            history = task.context.get("history", history)
            memory_facts = task.context.get("memory_facts", memory_facts)
            agent_failures = task.context.get("agent_failures", "")

        response_prompt = PromptRegistry.render(
            "chat_agent", "response", language,
            query=query,
            history=history,
            memory_facts=memory_facts,
            agent_failures=agent_failures,
        )

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=response_prompt),
            ]
            response = self.llm.invoke(messages)
            reply = response.content
        except Exception as e:
            # 記錄詳細錯誤信息，包含異常類型和堆棧
            logger.error(
                f"[ChatAgent] LLM Invoke Failed\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Error Message: {e}\n"
                f"  Query: {query[:100]}...\n"
                f"  Language: {language}",
                exc_info=True  # 包含完整的堆棧追蹤
            )
            reply = "服務暫時無法使用，請稍後再試。" if language == "zh-TW" else "Service temporarily unavailable, please try again later."

        return AgentResult(
            success=True,
            message=reply,
            agent_name=self.name,
        )

    def _is_price_query(self, task: SubTask, query: str) -> bool:
        """Use LLM to detect if the task is a simple crypto price query."""
        if task.tool_hint == "get_crypto_price":
            return True
        try:
            prompt = (
                "判斷以下使用者訊息是否為「單純查詢加密貨幣即時價格」的請求。\n"
                "只回傳 true 或 false，不加任何說明。\n"
                "若訊息包含分析、技術指標、趨勢判斷等需求，回傳 false。\n\n"
                f"使用者訊息：{query}"
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip().lower().startswith("true")
        except Exception:
            return False

    def _handle_price_query(self, query: str, task: SubTask, language: str = "zh-TW") -> AgentResult:
        """Handle a simple price lookup query."""
        symbol = self._extract_symbol(query)

        # Use get_crypto_price tool directly
        result_data = None
        success = False
        tool = self.tool_registry.get("get_crypto_price", caller_agent=self.name)

        if tool:
            try:
                result_data = tool.handler.invoke({"symbol": symbol})
                success = True
            except Exception:
                pass

        if success and result_data:
            reply = self._format_price_data(symbol, result_data, language)
        else:
            # Fallback with multi-language
            if language == "zh-TW":
                reply = f"抱歉，暫時無法獲取 {symbol} 的即時價格。請稍後再試。"
            elif language == "zh-CN":
                reply = f"抱歉，暂时无法获取 {symbol} 的实时价格。请稍后再试。"
            else:
                reply = f"Sorry, unable to get real-time price for {symbol} at the moment. Please try again later."

        return AgentResult(
            success=True,
            message=reply,
            agent_name=self.name,
            data={"symbol": symbol, "price_data": result_data},
        )

    def _format_price_data(self, symbol: str, data: dict, language: str = "zh-TW") -> str:
        """Format price data with multi-language support."""
        if isinstance(data, dict):
            if "price_info" in data:
                return data["price_info"]
            else:
                price = data.get("price") or data.get("last") or data.get("current_price", "N/A")
                change = data.get("change_24h") or data.get("change") or data.get("percentage", "")

                trend_emoji = "📈" if str(change).startswith("+") or (isinstance(change, (int, float)) and change > 0) else "📉"

                if language == "zh-TW":
                    reply = f"### 💰 **{symbol} 即時價格資訊**\n\n"
                    reply += f"> **當前價格**: `${price}`\n"
                    if change:
                        reply += f"> **24h 變化**: {trend_emoji} `{change}%`\n"
                    high = data.get("high_24h")
                    low = data.get("low_24h")
                    vol = data.get("volume_24h")
                    if high and low:
                        reply += f"\n| 24h 最高 | 24h 最低 | 交易量 |\n| :---: | :---: | :---: |\n| {high} | {low} | {vol} |\n"
                elif language == "zh-CN":
                    reply = f"### 💰 **{symbol} 实时价格资讯**\n\n"
                    reply += f"> **当前价格**: `${price}`\n"
                    if change:
                        reply += f"> **24h 变化**: {trend_emoji} `{change}%`\n"
                    high = data.get("high_24h")
                    low = data.get("low_24h")
                    vol = data.get("volume_24h")
                    if high and low:
                        reply += f"\n| 24h 最高 | 24h 最低 | 交易量 |\n| :---: | :---: | :---: |\n| {high} | {low} | {vol} |\n"
                else:
                    reply = f"### 💰 **{symbol} Real-time Price**\n\n"
                    reply += f"> **Current Price**: `${price}`\n"
                    if change:
                        reply += f"> **24h Change**: {trend_emoji} `{change}%`\n"
                    high = data.get("high_24h")
                    low = data.get("low_24h")
                    vol = data.get("volume_24h")
                    if high and low:
                        reply += f"\n| 24h High | 24h Low | Volume |\n| :---: | :---: | :---: |\n| {high} | {low} | {vol} |\n"
                return reply
        elif isinstance(data, str):
            return f"### 💰 **{symbol}**\n\n{data}"
        else:
            return f"### 💰 **{symbol}**\n\n```json\n{str(data)}\n```"

    def _extract_symbol(self, description: str) -> str:
        """Use LLM to extract crypto symbol from description."""
        try:
            prompt = (
                "你是加密貨幣專家。從以下使用者訊息中萃取加密貨幣交易代號（ticker）。\n"
                "只回傳代號本身（如 BTC、ETH、SOL），不加任何說明。\n"
                "若無法辨識，回傳 BTC。\n\n"
                f"使用者訊息：{description}"
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = response.content.strip().upper().split()[0]
            import re
            if re.match(r'^[A-Z]{2,10}$', result):
                return result
        except Exception:
            pass
        return "BTC"
