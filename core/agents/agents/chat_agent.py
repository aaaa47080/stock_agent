"""
Agent V4 — Chat Agent

一般對話 Agent: 處理問候、閒聊、系統說明，是所有未知請求的 fallback。
也處理簡單的價格查詢（使用 get_crypto_price 工具）。
"""
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

# from ..base import SubAgent
from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


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

        # Check if this is a price query (via tool_hint or keyword detection)
        # Note: task might not have tool_hint if it came from simple classification?
        # Manually check tool_registry for price tool if needed? 
        # But here we just use what we have.
        
        if self._is_price_query(task, query):
            return self._handle_price_query(query, task)

        # Build system prompt from registry
        system_prompt = PromptRegistry.get("chat_agent", "system")

        # Build response prompt
        history = "這是新對話的開始"
        memory_facts = "無"
        agent_failures = ""
        if hasattr(task, "context") and task.context:
            history = task.context.get("history", history)
            memory_facts = task.context.get("memory_facts", "無")
            agent_failures = task.context.get("agent_failures", "")

        response_prompt = PromptRegistry.render(
            "chat_agent", "response",
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
            print(f"[ChatAgent] LLM Invoke Failed: {e}")
            reply = "服務暫時無法使用，請稍後再試。"

        return AgentResult(
            success=True,
            message=reply,
            agent_name=self.name,
        )

    def _is_price_query(self, task: SubTask, query: str) -> bool:
        """Detect if the task is a simple price query."""
        if task.tool_hint == "get_crypto_price":
            return True
        query_lower = query.lower()
        price_keywords = ['價格', '多少錢', '多少', '現價', '現在價格', 'price', '報價']
        has_price_keyword = any(kw in query_lower for kw in price_keywords)
        # Only treat as price query if it doesn't also ask for analysis
        analysis_keywords = ['分析', '技術', 'rsi', 'macd', '走勢分析', '指標']
        has_analysis_keyword = any(kw in query_lower for kw in analysis_keywords)
        return has_price_keyword and not has_analysis_keyword

    def _handle_price_query(self, query: str, task: SubTask) -> AgentResult:
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
            # Format price data
            data = result_data
            if isinstance(data, dict):
                # V3 tool returns {"price_info": "## PI 即時價格\n| ..."}
                if "price_info" in data:
                    reply = data["price_info"]
                else:
                    price = data.get("price") or data.get("last") or data.get("current_price", "N/A")
                    change = data.get("change_24h") or data.get("change") or data.get("percentage", "")
                    
                    # 判斷漲跌符號與顏色指示 (Markdown 無法直接上色，但可用 emoji)
                    trend_emoji = "📈" if str(change).startswith("+") or (isinstance(change, (int, float)) and change > 0) else "📉"
                    
                    reply = f"### 💰 **{symbol} 即時價格資訊**\n\n"
                    reply += f"> **當前價格**: `${price}`\n"
                    if change:
                        reply += f"> **24h 變化**: {trend_emoji} `{change}%`\n"
                    
                    # 添加更多資訊（若有）
                    high = data.get("high_24h")
                    low = data.get("low_24h")
                    vol = data.get("volume_24h")
                    if high and low:
                         reply += f"\n| 24h 最高 | 24h 最低 | 交易量 |\n| :---: | :---: | :---: |\n| {high} | {low} | {vol} |\n"

            elif isinstance(data, str):
                reply = f"### 💰 **{symbol} 即時價格**\n\n{data}"
            else:
                reply = f"### 💰 **{symbol} 即時價格**\n\n```json\n{str(data)}\n```"
        else:
            # Fallback
            reply = f"抱歉，暫時無法獲取 {symbol} 的即時價格。請稍後再試。"

        return AgentResult(
            success=True,
            message=reply,
            agent_name=self.name,
            data={"symbol": symbol, "price_data": result_data},
        )

    def _extract_symbol(self, description: str) -> str:
        """Extract crypto symbol from description."""
        crypto_map = {
            'BTC': ['btc', 'bitcoin', '比特幣'],
            'ETH': ['eth', 'ethereum', '以太坊'],
            'SOL': ['sol', 'solana'],
            'PI': ['pi', 'pi network', 'pi幣'],
            'DOGE': ['doge', 'dogecoin'],
            'XRP': ['xrp', 'ripple'],
            'BNB': ['bnb', 'binance'],
        }
        desc_lower = description.lower()
        for symbol, keywords in crypto_map.items():
            if any(kw in desc_lower for kw in keywords):
                return symbol
        return "BTC"
