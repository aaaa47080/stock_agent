"""Cost-aware model routing strategy — select model by task complexity and budget."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelInfo:
    """Immutable metadata for cost estimation and tier gating."""

    name: str
    provider: str  # "openai", "google_genai"
    cost_per_1k_input: float  # USD per 1K input tokens
    cost_per_1k_output: float  # USD per 1K output tokens
    tier: str  # "free", "premium"
    quality: int  # 1-10, higher is better


# Reference costs (approximate, for budget estimation)
_MODEL_COSTS: dict[str, ModelInfo] = {
    "gemini-3.1-flash-preview": ModelInfo(
        name="gemini-3.1-flash-preview",
        provider="google_genai",
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        tier="free",
        quality=6,
    ),
    "gpt-5-mini": ModelInfo(
        name="gpt-5-mini",
        provider="openai",
        cost_per_1k_input=0.15,
        cost_per_1k_output=0.60,
        tier="free",
        quality=7,
    ),
    "gpt-4o": ModelInfo(
        name="gpt-4o",
        provider="openai",
        cost_per_1k_input=0.25,
        cost_per_1k_output=1.00,
        tier="premium",
        quality=8,
    ),
    "gpt-5.2-pro": ModelInfo(
        name="gpt-5.2-pro",
        provider="openai",
        cost_per_1k_input=2.50,
        cost_per_1k_output=10.00,
        tier="premium",
        quality=9,
    ),
    "gemini-3.1-pro-preview": ModelInfo(
        name="gemini-3.1-pro-preview",
        provider="google_genai",
        cost_per_1k_input=1.25,
        cost_per_1k_output=5.00,
        tier="premium",
        quality=8,
    ),
}

# Pre-compute a list of free-tier model names for fast lookup
_FREE_TIER_MODELS: list[str] = [
    name for name, info in _MODEL_COSTS.items() if info.tier == "free"
]

# Default budget per request (USD)
DEFAULT_BUDGET_USD = 0.50


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ModelRouter:
    """Cost-aware model router — select model by task complexity and budget.

    All methods are ``@classmethod`` so callers never need to instantiate.
    The original ``get_model`` signature is preserved for backward
    compatibility with ``manager/llm.py``.
    """

    # Primary routing table: task_type → model
    TASK_MODEL_MAP: dict[str, str] = {
        "simple_qa": "gemini-3.1-flash-preview",
        "market_data": "gpt-5-mini",
        "deep_analysis": "gpt-5.2-pro",
        "research": "gpt-5.2-pro",
    }

    # Cheaper fallback when budget is exhausted
    BUDGET_FALLBACK: dict[str, str] = {
        "deep_analysis": "gpt-5-mini",
        "research": "gpt-5-mini",
        "market_data": "gemini-3.1-flash-preview",
    }

    DEFAULT_MODEL = "gpt-5-mini"

    # ---- original API (backward-compatible) ----

    @classmethod
    def get_model(cls, task_type: str, user_preference: Optional[str] = None) -> str:
        """Return model name for *task_type*.

        Signature is **unchanged** — ``manager/llm.py`` calls this directly.
        """
        if user_preference:
            return user_preference
        return cls.TASK_MODEL_MAP.get(task_type, cls.DEFAULT_MODEL)

    # ---- cost-aware extensions ----

    @classmethod
    def get_model_info(cls, model_name: str) -> ModelInfo:
        """Return cost and metadata for *model_name*.

        Returns ``DEFAULT_MODEL`` info for unknown models so callers always
        get a valid ``ModelInfo`` without extra error handling.
        """
        info = _MODEL_COSTS.get(model_name)
        if info is None:
            logger.warning(
                "Unknown model %r — falling back to %r",
                model_name,
                cls.DEFAULT_MODEL,
            )
            return _MODEL_COSTS[cls.DEFAULT_MODEL]
        return info

    @classmethod
    def check_budget(
        cls,
        model_name: str,
        spent_usd: float,
        budget_usd: float = DEFAULT_BUDGET_USD,
    ) -> bool:
        """Return ``True`` if one more call to *model_name* fits the budget.

        Estimates ~2K input tokens as a conservative single-call cost.
        """
        info = cls.get_model_info(model_name)
        estimated_cost = info.cost_per_1k_input * 2  # ~2K input tokens
        fits = (spent_usd + estimated_cost) <= budget_usd
        if not fits:
            logger.info(
                "Budget check failed: spent=%.4f + est=%.4f > budget=%.4f",
                spent_usd,
                estimated_cost,
                budget_usd,
            )
        return fits

    @classmethod
    def get_budget_fallback(cls, task_type: str) -> Optional[str]:
        """Return a cheaper model for *task_type* when budget is tight.

        Returns ``None`` when no fallback is defined.
        """
        return cls.BUDGET_FALLBACK.get(task_type)

    @classmethod
    def get_model_for_tier(cls, task_type: str, user_tier: str) -> str:
        """Select model respecting the user's membership tier.

        * **free** users — only flash/free-tier models.  Premium models are
          downgraded to the best available free model.
        * **premium** users — same as ``get_model()`` (all models available).
        """
        if user_tier == "free":
            target = cls.TASK_MODEL_MAP.get(task_type, cls.DEFAULT_MODEL)
            info = cls.get_model_info(target)
            if info.tier == "free":
                return target
            # Downgrade to best free model
            if _FREE_TIER_MODELS:
                logger.info(
                    "Free user tier downgrade: %s → %s",
                    target,
                    _FREE_TIER_MODELS[0],
                )
                return _FREE_TIER_MODELS[0]
            return cls.DEFAULT_MODEL
        # Premium (or any other tier) — full access
        return cls.get_model(task_type)

    @classmethod
    def estimate_cost(
        cls,
        model_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> float:
        """Estimate USD cost for a model given token counts."""
        info = cls.get_model_info(model_name)
        return info.cost_per_1k_input * (
            input_tokens / 1000
        ) + info.cost_per_1k_output * (output_tokens / 1000)

    @classmethod
    def resolve_model(
        cls,
        task_type: str,
        user_tier: str = "free",
        user_preference: Optional[str] = None,
        spent_usd: float = 0.0,
        budget_usd: float = DEFAULT_BUDGET_USD,
    ) -> str:
        """High-level resolver that applies tier gating → preference → budget.

        This is the recommended entry point for new code.  Order of priority:

        1. ``user_preference`` — if set, use it verbatim.
        2. Tier-appropriate model via ``get_model_for_tier``.
        3. Budget check — if over budget, apply ``BUDGET_FALLBACK``.
        """
        # 1. User preference wins
        if user_preference:
            return user_preference

        # 2. Tier-gated model selection
        model = cls.get_model_for_tier(task_type, user_tier)

        # 3. Budget enforcement
        if not cls.check_budget(model, spent_usd, budget_usd):
            fallback = cls.get_budget_fallback(task_type)
            if fallback:
                logger.info(
                    "Budget fallback for %s: %s → %s",
                    task_type,
                    model,
                    fallback,
                )
                model = fallback

        return model
