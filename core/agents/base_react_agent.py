"""
BaseReActAgent - 統一的 LangChain Agent 基類

所有 sub-agent 繼承此類，使用 create_agent 實現 ReAct 循環。
LLM 自動決定：是否調用工具、調用哪個工具、傳入什麼參數。
"""
import logging
from abc import abstractmethod
from typing import List

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from .models import SubTask, AgentResult
from .prompt_registry import PromptRegistry

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
        tools = self._get_tools()

        if not tools:
            # 沒有 tools，直接用 LLM 回答
            return self._execute_without_tools(task, language)

        # 使用 create_agent 執行 ReAct 循環
        return self._execute_with_agent(task, tools, language)

    def _get_tools(self) -> List:
        """
        從 tool_registry 獲取該 agent 可用的 tools。

        子類可以 override 來過濾或添加 tools。
        """
        allowed_metas = self.tool_registry.list_for_agent(self.name)
        tools = []
        for meta in allowed_metas:
            if hasattr(meta.handler, "name"):
                tools.append(meta.handler)
        return tools

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
        """使用 create_agent 執行完整的 ReAct 循環。"""
        try:
            # 創建 agent
            system_prompt = self._get_system_prompt(language)
            agent = create_agent(
                self.llm,
                tools=tools,
                system_prompt=system_prompt,
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
