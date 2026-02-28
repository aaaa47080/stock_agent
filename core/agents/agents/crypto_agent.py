"""
Agent V4 — Crypto Agent (ReAct)

Dynamic tool-calling agent for crypto analysis.
LLM decides which tools to call based on the query — no fixed pipeline.
Supports multi-language responses.
"""
import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class CryptoAgent:
    MAX_TOOL_ROUNDS = 5

    def __init__(self, llm_client, tool_registry):
        self.llm           = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "crypto"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute crypto analysis via ReAct tool-calling loop."""
        history = (task.context or {}).get("history", "")
        language = (task.context or {}).get("language", "zh-TW")  # 獲取用戶語言偏好
        symbol  = self._extract_symbol(task.description, history=history, language=language)

        # Collect available LangChain @tool objects from registry
        allowed_metas = self.tool_registry.list_for_agent(self.name)
        tools = []
        for meta in allowed_metas:
            if hasattr(meta.handler, "name"):
                tools.append(meta.handler)

        if not tools:
            # No tools registered — LLM-only fallback
            try:
                resp = self.llm.invoke([HumanMessage(content=task.description)])
                return AgentResult(
                    success=True, message=resp.content,
                    agent_name=self.name, quality="pass",
                )
            except Exception as e:
                return AgentResult(
                    success=False, message=f"分析失敗：{e}",
                    agent_name=self.name,
                )

        # Bind tools — LanguageAwareLLM.bind_tools() preserves language injection
        llm_with_tools = self.llm.bind_tools(tools)

        system_prompt = PromptRegistry.get("crypto_agent", "system", language)
        messages: List = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"[標的參考：{symbol}]\n\n{task.description}"),
        ]

        last_response = None
        for _ in range(self.MAX_TOOL_ROUNDS):
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            last_response = response

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break  # LLM gave a final answer — stop loop

            # Execute each tool call and feed results back
            for tc in tool_calls:
                result = self._run_tool(tc["name"], tc.get("args") or {})
                messages.append(ToolMessage(
                    content=str(result)[:2000],
                    tool_call_id=tc["id"],
                ))

        final_text = (last_response.content if last_response else "") or "（無分析結果）"
        
        # 根據語言選擇回應前綴
        prefix_map = {
            "zh-TW": "🔐 **{symbol} 加密貨幣分析**",
            "zh-CN": "🔐 **{symbol} 加密货币分析**",
            "en": "🔐 **{symbol} Cryptocurrency Analysis**",
        }
        prefix = prefix_map.get(language, prefix_map["zh-TW"]).format(symbol=symbol)
        
        return AgentResult(
            success=True,
            message=f"{prefix}\n\n{final_text}",
            agent_name=self.name,
            data={"symbol": symbol},
            quality="pass",
        )

    def _run_tool(self, tool_name: str, args: dict):
        """Execute a single tool call from the registry."""
        meta = self.tool_registry.get(tool_name, caller_agent=self.name)
        if not meta:
            return f"[Tool '{tool_name}' not available]"
        try:
            return meta.handler.invoke(args)
        except Exception as e:
            return f"[Tool '{tool_name}' error: {e}]"

    def _extract_symbol(self, description: str, history: str = "", language: str = "zh-TW") -> str:
        """Extract crypto ticker from description, using history for pronoun resolution."""
        import re

        # Fast path: explicit prefix "[BTC] ..." injected by _plan_node
        prefix_match = re.match(r'^\[([A-Z]{1,10})\]', description.strip())
        if prefix_match:
            return prefix_match.group(1)

        # LLM as primary extractor — handles any language, pronouns, abbreviations
        try:
            history_hint = f"\n\n近期對話歷史：\n{history[-400:]}" if history else ""
            prompt_text = PromptRegistry.get(self.name + "_agent", "extract_symbol", language).format(
                description=description,
                history_hint=history_hint
            )
            response = self.llm.invoke([HumanMessage(content=prompt_text)])
            result = response.content.strip().upper().split()[0]
            if result != "NONE":
                return result
        except Exception:
            pass

        return "BTC"
