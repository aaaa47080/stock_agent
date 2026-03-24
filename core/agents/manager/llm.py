"""
Manager Agent - LLM Routing and Invocation

Contains LLM invocation and model routing:
- _llm_invoke: Invoke LLM with task_type routing
- _get_routed_llm: Get appropriate LLM for task type
- _create_model_instance: Create new LLM instance for a model name
- _parse_json_response: Parse and validate JSON response
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from cachetools import TTLCache
from langchain_core.messages import HumanMessage

from api.utils import logger
from core.agents.context_budget import CONTEXT_CHAR_BUDGET
from core.agents.prompt_guard import parse_and_validate_json_response
from utils.user_client_factory import explain_llm_exception

from .mixin_base import ManagerAgentMixin


class LLMInvokeMixin(ManagerAgentMixin):
    """LLM routing and invocation for ManagerAgent."""

    async def _llm_invoke(self, prompt: str, task_type: Optional[str] = None) -> str:
        """調用 LLM，支援根據 task_type 路由到不同模型。

        Args:
            prompt: The prompt to send to the LLM.
            task_type: Optional task type for model routing (e.g. "simple_qa",
                "deep_analysis"). When provided, ModelRouter selects the
                appropriate model. Falls back to self.llm when routing fails.
        """
        # Resolve the LLM to use based on task_type
        llm = self._get_routed_llm(task_type) if task_type else self.llm

        messages = [HumanMessage(content=prompt)]
        try:
            if hasattr(llm, "ainvoke"):
                response = await llm.ainvoke(messages)
            else:
                response = await asyncio.to_thread(llm.invoke, messages)
            content = response.content
            if len(content) >= CONTEXT_CHAR_BUDGET * 0.95:
                logger.warning(
                    f"[Manager] Response near context budget: {len(content)} chars (budget: {CONTEXT_CHAR_BUDGET})"
                )

            # 記錄 token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                from ..token_tracker import TokenUsage
                from ._main import _extract_model_name_for_manager

                usage = response.usage_metadata
                model_name = _extract_model_name_for_manager(llm)
                self._token_tracker.record(
                    TokenUsage(
                        model=model_name,
                        prompt_tokens=usage.get("input_tokens", 0),
                        completion_tokens=usage.get("output_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                    )
                )
            if self._token_tracker.is_over_budget():
                logger.warning(
                    f"[Manager] Token budget exceeded: ${self._token_tracker.total_cost():.4f}"
                )

            return content
        except Exception as e:
            raise RuntimeError(explain_llm_exception(e)) from e

    def _get_routed_llm(self, task_type: str):
        """Return an LLM instance appropriate for the given task type.

        Uses ModelRouter.resolve_model() for cost-aware routing with tier
        gating and budget enforcement. Falls back to get_model() for
        backward compatibility.
        """
        from ..model_router import ModelRouter

        try:
            target_model = ModelRouter.resolve_model(
                task_type=task_type,
                user_tier=getattr(self, "user_tier", "free"),
                user_preference=getattr(self, "_user_model_preference", None),
                spent_usd=getattr(self._token_tracker, "total_cost", 0.0),
            )
        except Exception:
            target_model = ModelRouter.get_model(task_type)

        # Resolve the current underlying model name
        inner_llm = getattr(self.llm, "_llm", self.llm)
        current_model = (
            getattr(inner_llm, "model_name", None)
            or getattr(inner_llm, "model", None)
            or ""
        )

        if target_model == current_model:
            return self.llm

        # Need a different model — create or retrieve cached instance
        if not hasattr(self, "_routed_llm_cache"):
            self._routed_llm_cache: Dict[str, Any] = TTLCache(maxsize=10, ttl=600)

        cached = self._routed_llm_cache.get(target_model)
        if cached is not None:
            return cached

        try:
            routed = self._create_model_instance(target_model, inner_llm)
            # Wrap with the same LanguageAwareLLM to preserve language injection
            lang_msg = getattr(self.llm, "_lang_msg", None)
            if lang_msg:
                from ..bootstrap import LanguageAwareLLM

                routed = LanguageAwareLLM(routed)
                routed._lang_msg = lang_msg

            self._routed_llm_cache[target_model] = routed
            logger.info(
                f"[Manager] Model routed: task_type={task_type} → {target_model}"
            )
            return routed
        except Exception as e:
            logger.warning(
                f"[Manager] Model routing failed for {target_model}: {e}, "
                f"falling back to default model"
            )
            return self.llm

    @staticmethod
    def _create_model_instance(model_name: str, reference_llm: Any) -> Any:
        """Create a new LLM instance with *model_name* using config from *reference_llm*.

        This infers the provider and credentials from the existing LLM so the
        caller does not need to know about provider-specific setup.
        """
        from langchain.chat_models import init_chat_model

        kwargs: dict = {"model": model_name, "temperature": 0.5}

        # Infer provider — prefer model_provider attribute
        provider = getattr(reference_llm, "model_provider", None)
        if provider:
            kwargs["model_provider"] = provider
        else:
            # Fallback: infer from class name
            cls_name = type(reference_llm).__name__.lower()
            if "gemini" in cls_name or "google" in cls_name:
                kwargs["model_provider"] = "google_genai"
            else:
                kwargs["model_provider"] = "openai"

        # Copy credentials
        for attr in ("openai_api_key", "api_key", "google_api_key"):
            key = getattr(reference_llm, attr, None)
            if key:
                kwargs[attr] = key

        return init_chat_model(**kwargs)

    def _parse_json_response(
        self,
        response: str,
        context: str = "intent",
        fallback_query: str = "",
    ) -> dict:
        """
        解析 JSON 回應並進行 schema 驗證。

        委派給 prompt_guard.parse_and_validate_json_response，
        確保返回的 dict 包含必要欄位，失敗時回傳安全預設值。
        """
        return parse_and_validate_json_response(
            response, context=context, fallback_query=fallback_query
        )
