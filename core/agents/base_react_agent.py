"""
BaseReActAgent - 統一的 LangGraph Agent 基類

所有 sub-agent 繼承此類，使用 LangGraph create_react_agent 實現 ReAct 循環。
LLM 自動決定：是否調用工具、調用哪個工具、傳入什麼參數。
"""
import logging
import json
from abc import abstractmethod
from typing import List, Optional, Any

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

from .models import SubTask, AgentResult
from .prompt_registry import PromptRegistry
from .tool_registry import ToolMetadata

logger = logging.getLogger(__name__)


class BaseReActAgent:
    """
    統一的 ReAct Agent 基類。

    子類只需實現：
    - name: agent 名稱

    可選覆寫：
    - _get_system_prompt(): 自定義系統提示詞
    - _get_tools(): 過濾或添加 tools

    自動處理：
    - 從 tool_registry 獲取該 agent 的 tools
    - 創建 LangChain agent with ReAct loop
    - 執行直到得出最終答案
    """

    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 名稱，用於 tool_registry 和 logging。"""
        pass

    def execute(self, task: SubTask) -> AgentResult:
        """
        執行 agent 任務。

        使用 LangChain create_agent 實現完整的 ReAct 循環：
        1. LLM 根據 tool descriptions 決定是否調用工具
        2. 執行工具，結果反饋給 LLM
        3. LLM 決定繼續調用工具或給出最終答案
        4. 循環直到完成
        """
        # 防禦性編程：確保 context 是 dict
        context = task.context or {}
        if isinstance(context, str):
            context = {}
        language = context.get("language", "zh-TW")

        # 獲取該 agent 專用的 tools
        tool_metas = self._get_tool_metas()
        tools = [meta.handler for meta in tool_metas if hasattr(meta.handler, "name")]

        if not tools:
            # 沒有 tools，直接用 LLM 回答
            return self._execute_without_tools(task, language)

        if self._requires_tool_execution(task):
            forced_result = self._execute_with_required_tool(task, tool_metas, language)
            if forced_result is not None:
                return forced_result

        # 使用 create_agent 執行 ReAct 循環
        return self._execute_with_agent(task, tools, language)

    def _get_tool_metas(self) -> List[ToolMetadata]:
        """
        從 tool_registry 獲取該 agent 可用的 tools。

        子類可以 override 來過濾或添加 tools。
        """
        return self.tool_registry.list_for_agent(self.name)

    def _get_tools(self) -> List:
        return [meta.handler for meta in self._get_tool_metas() if hasattr(meta.handler, "name")]

    def _get_system_prompt(self, language: str) -> str:
        """
        獲取系統提示詞。

        子類應該 override 來提供特定的提示詞。
        """
        try:
            return PromptRegistry.render(f"{self.name}_agent", "system", language=language, include_time=True)
        except Exception:
            # 默認提示詞
            if language == "zh-TW":
                return "你是專業助手。根據工具描述自動決定是否調用工具及參數。"
            else:
                return "You are a professional assistant. Automatically decide whether to call tools based on their descriptions."

    def _execute_with_agent(self, task: SubTask, tools: List, language: str) -> AgentResult:
        """使用 LangGraph create_react_agent 執行完整的 ReAct 循環。"""
        try:
            # 創建 agent - 使用 LangGraph 的 create_react_agent
            system_prompt = self._get_system_prompt(language)

            # 獲取底層 LLM（如果是 LanguageAwareLLM 包裝器）
            llm = getattr(self.llm, '_llm', self.llm)

            agent = create_react_agent(
                model=llm,
                tools=tools,
                prompt=system_prompt,
            )

            # 執行 agent
            result = agent.invoke({
                "messages": [HumanMessage(content=task.description)]
            })

            # 提取最終消息 - 防禦性編程：確保 result 是 dict
            if isinstance(result, str):
                # agent.invoke 返回了字串而非字典
                reply = result
                return AgentResult(
                    success=True,
                    message=reply,
                    agent_name=self.name,
                )
            messages = result.get("messages", [])
            if messages:
                final_message = messages[-1]
                reply = final_message.content if hasattr(final_message, 'content') else str(final_message)
            else:
                reply = "No response generated."

            return AgentResult(
                success=True,
                message=reply,
                agent_name=self.name,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Agent execution failed: {e}")
            return self._error_result(str(e), language)

    def _requires_tool_execution(self, task: SubTask) -> bool:
        """結構化判定：已解析出市場實體時，至少先執行一次工具。

        例外：如果用戶明確詢問新聞、資訊等，不強制執行價格查詢工具，
        讓 ReAct 循環自然選擇適當的工具。
        """
        context = task.context or {}
        if not isinstance(context, dict):
            return False

        # 檢查是否有 tool_required 標記
        if not context.get("tool_required"):
            return False

        # 如果用戶明確詢問新聞/資訊，不強制執行預設工具
        query_lower = task.description.lower()
        news_keywords = ["新聞", "news", "消息", "資訊", "訊息", "資訊", "動態"]
        if any(keyword in query_lower for keyword in news_keywords):
            return False

        return True

    def _execute_with_required_tool(self, task: SubTask, tool_metas: List[ToolMetadata], language: str) -> Optional[AgentResult]:
        """先強制執行一次最合適的 lookup 工具，再由 LLM 整理結果。"""
        tool_meta = self._select_required_tool(task, tool_metas)
        if tool_meta is None:
            return None

        tool_kwargs = self._build_required_tool_kwargs(tool_meta, task)
        if not tool_kwargs:
            return None

        try:
            tool = tool_meta.handler
            if hasattr(tool, "invoke"):
                tool_result = tool.invoke(tool_kwargs)
            else:
                tool_result = tool(**tool_kwargs)
        except Exception as e:
            logger.warning(f"[{self.name}] Required tool execution failed: {e}")
            return None

        return self._summarize_required_tool_result(task, tool_meta, tool_result, language)

    def _select_required_tool(self, task: SubTask, tool_metas: List[ToolMetadata]) -> Optional[ToolMetadata]:
        """依工具 metadata 選擇查詢工具，不從名稱或描述做關鍵字猜測。"""
        candidates = []
        for meta in tool_metas:
            if meta.role != "market_lookup":
                continue
            if not self._build_required_tool_kwargs(meta, task):
                continue
            candidates.append(meta)

        if not candidates:
            return None

        candidates.sort(key=lambda meta: (-meta.priority, meta.name))
        return candidates[0]

    def _build_required_tool_kwargs(self, tool_meta: ToolMetadata, task: SubTask) -> Optional[dict]:
        """依工具 schema 自動填入 symbol/ticker/code 類參數。"""
        context = task.context if isinstance(task.context, dict) else {}
        symbols = context.get("symbols") or {}
        resolved_symbol = next((value for value in symbols.values() if value), None)
        if not resolved_symbol:
            return None

        args = tool_meta.input_schema or {}
        if "symbol" in args:
            return {"symbol": resolved_symbol.replace(".TW", "")}
        if "ticker" in args:
            return {"ticker": resolved_symbol.replace(".TW", "")}
        if "code" in args:
            return {"code": resolved_symbol.replace(".TW", "")}
        return None

    def _summarize_required_tool_result(self, task: SubTask, tool_meta: ToolMetadata, tool_result: Any, language: str) -> AgentResult:
        """將強制工具查詢結果整理成最終對用戶可讀的回答。"""
        if isinstance(tool_result, str):
            reply = tool_result
        else:
            system_prompt = self._get_system_prompt(language)
            tool_name = tool_meta.name
            serialized = json.dumps(tool_result, ensure_ascii=False, default=str)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=(
                        f"用戶問題：{task.description}\n"
                        f"已執行工具：{tool_name}\n"
                        f"工具結果：{serialized}\n\n"
                        "請直接根據工具結果回答，不要忽略工具結果，也不要改口說自己無法提供即時資料。"
                    )
                ),
            ]
            response = self.llm.invoke(messages)
            reply = response.content

        return AgentResult(
            success=True,
            message=reply,
            agent_name=self.name,
        )

    def _execute_without_tools(self, task: SubTask, language: str) -> AgentResult:
        """沒有 tools 時，直接用 LLM 回答。"""
        try:
            system_prompt = self._get_system_prompt(language)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=task.description),
            ]
            response = self.llm.invoke(messages)
            reply = response.content
        except Exception as e:
            logger.error(f"[{self.name}] LLM invocation failed: {e}")
            return self._error_result(str(e), language)

        return AgentResult(
            success=True,
            message=reply,
            agent_name=self.name,
        )

    def _error_result(self, error: str, language: str) -> AgentResult:
        """生成錯誤結果。"""
        if language == "zh-TW":
            msg = f"抱歉，處理時發生錯誤：{error}"
        elif language == "zh-CN":
            msg = f"抱歉，处理时发生错误：{error}"
        else:
            msg = f"Sorry, an error occurred: {error}"

        return AgentResult(
            success=False,
            message=msg,
            agent_name=self.name,
        )
