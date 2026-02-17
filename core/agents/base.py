"""
Agent V4 — Base SubAgent

Abstract base class for all sub-agents. Provides quality assessment,
tool invocation (via @tool functions), and HITL integration.
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Any
from dataclasses import dataclass, field

from .models import SubTask, AgentResult, CollaborationRequest
from .hitl import HITLManager


@dataclass
class ToolResult:
    """Wrapper for @tool invocation results — keeps agent code compatible."""
    success: bool
    data: Any = None
    error: Optional[str] = None


class SubAgent(ABC):
    def __init__(self, llm_client, tools: list, hitl: HITLManager):
        """
        Args:
            llm_client: LLM client for inference
            tools: list of @tool decorated functions this agent can use
            hitl: HITL manager for user interaction
        """
        self.llm = llm_client
        self.tools = {t.name: t for t in tools}  # name → @tool function
        self.hitl = hitl
        self.hitl_fn: Optional[callable] = None  # injected by Manager before execute()

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def execute(self, task: SubTask) -> AgentResult:
        ...

    def _use_tool(self, name: str, params: dict) -> ToolResult:
        """Invoke a @tool by name. Returns ToolResult for compatibility."""
        tool_fn = self.tools.get(name)
        if not tool_fn:
            return ToolResult(success=False, error=f"Tool '{name}' not available for {self.name}")
        try:
            result = tool_fn.invoke(params)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _assess_result_quality(self, result_text: str, task: SubTask) -> Tuple[str, Optional[str]]:
        """
        Assess quality of agent output using shared prompt.
        Returns ("pass", None) or ("fail", "reason text").
        On LLM error: defaults to ("pass", None) with warning.
        """
        try:
            from .prompt_registry import PromptRegistry
            from langchain_core.messages import HumanMessage

            history = "無"
            if hasattr(task, "context") and task.context and "history" in task.context:
                history = task.context["history"]

            prompt = PromptRegistry.render(
                "shared", "quality_assessment",
                task_description=task.description,
                history=history[:1000],  # truncate history for quality check
                agent_name=self.name,
                result_text=result_text[:2000],
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            if content.upper().startswith("PASS"):
                return ("pass", None)
            elif content.upper().startswith("FAIL"):
                reason = content[5:].strip().lstrip(":").strip()
                return ("fail", reason or "Quality check failed")
            else:
                print(f"[{self.name}] quality assessment unrecognized: {content[:80]}")
                return ("pass", None)

        except Exception as e:
            print(f"[{self.name}] quality assessment error (defaulting PASS): {e}")
            return ("pass", None)

    def _handle_fail(self, reason: Optional[str], task: SubTask) -> AgentResult:
        """
        Decision tree for quality failures:
        - user-related → ask user → return failure
        - needs collaboration → return with CollaborationRequest
        - data/api error → return failure
        - otherwise → default PASS with warning
        """
        reason_lower = (reason or "").lower()

        if any(kw in reason_lower for kw in ["使用者", "更多資訊", "不確定", "用戶"]):
            if self.hitl:
                extra = self.hitl.ask(f"Agent 需要更多資訊：{reason}")
                return AgentResult(
                    success=False,
                    message=f"需要更多資訊。使用者回覆：{extra}",
                    agent_name=self.name,
                    quality="fail",
                    quality_fail_reason=reason,
                )
            return AgentResult(
                success=False, message=reason or "需要更多資訊",
                agent_name=self.name, quality="fail", quality_fail_reason=reason,
            )

        if any(kw in reason_lower for kw in ["新聞", "其他來源", "collaboration"]):
            return AgentResult(
                success=False, message=reason or "需要其他 Agent 協助",
                agent_name=self.name, quality="fail", quality_fail_reason=reason,
                needs_collaboration=CollaborationRequest(
                    requesting_agent=self.name,
                    needed_agent="news" if "新聞" in reason_lower else "technical",
                    context=reason or "",
                    priority="optional",
                ),
            )

        if any(kw in reason_lower for kw in ["無資料", "api失敗", "超時", "no data", "timeout"]):
            return AgentResult(
                success=False, message=reason or "資料取得失敗",
                agent_name=self.name, quality="fail", quality_fail_reason=reason,
            )

        print(f"[{self.name}] _handle_fail defaulting to PASS: {reason}")
        return AgentResult(
            success=True, message="（品質檢查無法判斷，預設通過）",
            agent_name=self.name, quality="pass",
        )

    def _ask_user(self, question: str, options: list = None) -> Optional[str]:
        """Call HITL callback (injected by Manager). Returns None if no HITL available."""
        if self.hitl_fn:
            return self.hitl_fn(question, options)
        return None

    def ask_user(self, question: str) -> str:
        return self.hitl.ask(question) if self.hitl else ""
