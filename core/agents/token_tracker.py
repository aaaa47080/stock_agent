"""Token usage tracking and budget management."""

import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class TokenUsage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: float = field(default_factory=time.time)

    @property
    def estimated_cost_usd(self) -> float:
        COST_PER_1K = {
            "gpt-5-mini": 0.00015,
            "gpt-5.2-pro": 0.015,
            "gemini-3.1-flash-preview": 0.000075,
        }
        rate = COST_PER_1K.get(self.model, 0.001)
        return (self.total_tokens / 1000) * rate


class TokenTracker:
    def __init__(self, max_budget_usd: float = 10.0):
        self._usage_history: List[TokenUsage] = []
        self._max_budget = max_budget_usd

    def record(self, usage: TokenUsage) -> None:
        self._usage_history.append(usage)

    def total_cost(self) -> float:
        return sum(u.estimated_cost_usd for u in self._usage_history)

    def is_over_budget(self) -> bool:
        return self.total_cost() >= self._max_budget
