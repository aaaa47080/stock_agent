"""
BaseReActAgent - 統一的 LangGraph Agent 基類

所有 sub-agent 繼承此類，使用 LangGraph create_react_agent 實現 ReAct 循環。
LLM 自動決定：是否調用工具、調用哪個工具、傳入什麼參數。
"""
import logging
import json
from abc import abstractmethod
from typing import List, Optional, Any, Tuple

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

from .models import SubTask, AgentResult
from .analysis_policy import AnalysisPolicyResolver
from .prompt_registry import PromptRegistry
from .tool_registry import ToolMetadata
from core.database.tools import get_allowed_tools, normalize_membership_tier

logger = logging.getLogger(__name__)
_TIER_LEVELS = {"free": 0, "premium": 1}
_ANALYSIS_POLICY = AnalysisPolicyResolver()


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

    def __init__(self, llm_client, tool_registry, user_tier: str = "free", user_id: Optional[str] = None):
        self.llm = llm_client
        self.tool_registry = tool_registry
        self.user_tier = normalize_membership_tier(user_tier)
        self.user_id = user_id

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
        tool_metas = self._get_tool_metas(task)
        tools = [meta.handler for meta in tool_metas if hasattr(meta.handler, "name")]

        if not tools:
            verified_fallback = self._handle_verified_missing_tools(task, language)
            if verified_fallback is not None:
                return verified_fallback
            # 沒有 tools，直接用 LLM 回答
            return self._execute_without_tools(task, language)

        if self._requires_tool_execution(task):
            forced_result = self._execute_with_required_tool(task, tool_metas, language)
            if forced_result is not None:
                return forced_result

        # 使用 create_agent 執行 ReAct 循環
        return self._execute_with_agent(task, tools, language)

    def _resolve_user_scope(self, task: Optional[SubTask] = None) -> Tuple[str, Optional[str]]:
        context = task.context if task and isinstance(task.context, dict) else {}
        user_tier = normalize_membership_tier(context.get("user_tier", self.user_tier))
        user_id = context.get("user_id", self.user_id)
        return user_tier, user_id

    def _get_tool_metas(self, task: Optional[SubTask] = None) -> List[ToolMetadata]:
        """
        從 tool_registry 獲取該 agent 可用的 tools。

        子類可以 override 來過濾或添加 tools。
        """
        all_tools = self.tool_registry.list_for_agent(self.name)
        context = task.context if task and isinstance(task.context, dict) else {}
        context_allowed_tools = context.get("allowed_tools")
        if isinstance(context_allowed_tools, list):
            allowed_tool_names = {name for name in context_allowed_tools if isinstance(name, str)}
            return [meta for meta in all_tools if meta.name in allowed_tool_names]

        user_tier, user_id = self._resolve_user_scope(task)

        try:
            allowed_tools = set(get_allowed_tools(self.name, user_tier=user_tier, user_id=user_id))
            return [meta for meta in all_tools if meta.name in allowed_tools]
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to load DB tool permissions: {e}")

        user_tier_level = _TIER_LEVELS.get(user_tier, 0)
        return [
            meta for meta in all_tools
            if _TIER_LEVELS.get(normalize_membership_tier(meta.required_tier), 0) <= user_tier_level
        ]

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

    def _build_runtime_metadata(
        self,
        task: SubTask,
        *,
        verification_status: Optional[str] = None,
        policy_path: Optional[str] = None,
    ) -> dict:
        context = task.context if isinstance(task.context, dict) else {}
        metadata = context.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        market_resolution = metadata.get("market_resolution", {})
        if not isinstance(market_resolution, dict):
            market_resolution = {}

        query_profile = metadata.get("query_profile", {})
        if not isinstance(query_profile, dict):
            query_profile = {}

        matched_entities = market_resolution.get("matched_entities", {})
        if not isinstance(matched_entities, dict):
            matched_entities = {}

        if not matched_entities:
            symbols = context.get("symbols", {})
            if isinstance(symbols, dict):
                matched_entities = {
                    market: value for market, value in symbols.items()
                    if value
                }

        resolved_markets = [market for market, value in matched_entities.items() if value]
        resolved_market = None
        if len(resolved_markets) == 1:
            resolved_market = resolved_markets[0]
        elif len(resolved_markets) > 1:
            resolved_market = "ambiguous"

        runtime_metadata = {
            "analysis_mode": context.get("analysis_mode", "quick"),
            "query_type": query_profile.get("query_type", "general"),
            "resolved_market": resolved_market,
        }

        if verification_status:
            runtime_metadata["verification_status"] = verification_status
        if policy_path:
            runtime_metadata["policy_path"] = policy_path

        return runtime_metadata

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
        """Decide whether this task must go through a required-tool path first."""
        context = task.context if isinstance(task.context, dict) else {}
        if context.get("tool_required"):
            return True

        policy = _ANALYSIS_POLICY.resolve(context)
        return bool(policy.required_tool_role)

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
        """選擇最合適的查詢工具。

        優先級順序：
        1. role="market_lookup" 且優先級最高的工具（價格查詢）
        2. 如果沒有 market_lookup 工具，返回 None 讓 ReAct 自然選擇

        設計理念：不要在這裡做複雜的意圖判斷，讓 ReAct 循環處理複雜查詢。
        """
        context = task.context if isinstance(task.context, dict) else {}
        policy = _ANALYSIS_POLICY.resolve(context)
        if policy.required_tool_role == "discovery_lookup":
            discovery_candidates = [
                meta for meta in tool_metas
                if meta.role == "discovery_lookup" and self._build_required_tool_kwargs(meta, task)
            ]
            if discovery_candidates:
                discovery_candidates.sort(key=lambda meta: (-meta.priority, meta.name))
                return discovery_candidates[0]

        candidates = []
        for meta in tool_metas:
            # 只選擇 market_lookup 角色的工具（價格、行情等快速查詢）
            if meta.role != "market_lookup":
                continue
            if not self._build_required_tool_kwargs(meta, task):
                continue
            candidates.append(meta)

        if not candidates:
            # 沒有合適的 market_lookup 工具，讓 ReAct 自然選擇
            return None

        candidates.sort(key=lambda meta: (-meta.priority, meta.name))
        return candidates[0]

    def _build_required_tool_kwargs(self, tool_meta: ToolMetadata, task: SubTask) -> Optional[dict]:
        """依工具 schema 自動填入 symbol/ticker/code 類參數。"""
        context = task.context if isinstance(task.context, dict) else {}
        args = tool_meta.input_schema or {}
        if "query" in args:
            return {
                "query": task.description,
                "purpose": "resolve_market_context",
            }

        symbols = context.get("symbols") or {}
        resolved_symbol = next((value for value in symbols.values() if value), None)
        if not resolved_symbol:
            return None

        if "symbol" in args:
            return {"symbol": resolved_symbol.replace(".TW", "")}
        if "ticker" in args:
            return {"ticker": resolved_symbol.replace(".TW", "")}
        if "code" in args:
            return {"code": resolved_symbol.replace(".TW", "")}
        return None

    def _summarize_required_tool_result(self, task: SubTask, tool_meta: ToolMetadata, tool_result: Any, language: str) -> AgentResult:
        """將強制工具查詢結果整理成最終對用戶可讀的回答。"""
        context = task.context if isinstance(task.context, dict) else {}
        metadata = {
            **self._build_runtime_metadata(
                task,
                verification_status=(
                    "verified"
                    if context.get("analysis_mode") == "verified"
                    else "standard"
                ),
                policy_path=tool_meta.role or "required_tool",
            ),
            "used_tools": [tool_meta.name],
        }
        if isinstance(tool_result, dict):
            data_as_of = tool_result.get("timestamp") or tool_result.get("as_of") or tool_result.get("date")
            if data_as_of:
                metadata["data_as_of"] = data_as_of

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
            data=metadata,
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

    def _handle_verified_missing_tools(self, task: SubTask, language: str) -> Optional[AgentResult]:
        context = task.context if isinstance(task.context, dict) else {}
        policy = _ANALYSIS_POLICY.resolve(context)
        if not policy.fail_reason:
            return None

        if language == "zh-TW":
            if policy.fail_reason == "verified_discovery_tool_unavailable":
                message = "目前無法先確認這個代號屬於哪個市場，因為此模式下沒有可用的探索工具。請啟用相關工具後再試。"
            else:
                message = "目前無法驗證這個即時查詢，因為此模式下沒有可用的資料工具。請啟用相關工具後再試。"
        else:
            message = (
                "I cannot verify this time-sensitive request right now because no eligible "
                "data tools are available in verified mode."
            )

        return AgentResult(
            success=False,
            message=message,
            agent_name=self.name,
            data=self._build_runtime_metadata(
                task,
                verification_status="unverified",
                policy_path=policy.required_tool_role or "verified_guardrail",
            ),
            quality="fail",
            quality_fail_reason=policy.fail_reason,
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
